"""
Figma-to-Code Converter - Main FastAPI Application
Web interface for converting Figma designs to code with real-time updates
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import uvicorn
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import dotenv
from pydantic import BaseModel

# Import our custom modules
from enhanced_figma_processor import EnhancedFigmaProcessor
from ai_engine import AI_engine
from framework_generators import generate_framework_code
from component_collector import ComponentCollector
from project_assembler import ProjectAssembler

# Load environment variables
dotenv.load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Figma-to-Code Converter",
    description="Convert Figma designs to production-ready code",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Global instances
ai_engine = AI_engine(verbose=True)
processor = EnhancedFigmaProcessor()

# In-memory storage for processing jobs
processing_jobs: Dict[str, Dict[str, Any]] = {}

# Pydantic models
class ConversionRequest(BaseModel):
    figma_url: str
    pat_token: Optional[str] = None
    target_framework: str = "react"
    include_components: bool = True

class ProcessingStatus(BaseModel):
    job_id: str
    status: str
    progress: float
    message: str
    result: Optional[Dict[str, Any]] = None

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main web interface"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/convert")
async def start_conversion(request: ConversionRequest, background_tasks: BackgroundTasks):
    """Start a new conversion job"""
    try:
        # Generate unique job ID
        job_id = str(uuid.uuid4())

        # Initialize job status
        processing_jobs[job_id] = {
            "status": "starting",
            "progress": 0.0,
            "message": "Initializing conversion...",
            "start_time": datetime.now(),
            "result": None
        }

        # Start background processing
        background_tasks.add_task(
            process_conversion,
            job_id,
            request.figma_url,
            request.pat_token,
            request.target_framework,
            request.include_components
        )

        return {"job_id": job_id, "status": "started"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start conversion: {str(e)}")

@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a conversion job"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = processing_jobs[job_id]
    return ProcessingStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        result=job.get("result")
    )

@app.get("/api/download/{job_id}")
async def download_result(job_id: str):
    """Download the conversion result as ZIP"""
    if job_id not in processing_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = processing_jobs[job_id]
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")

    result_path = job["result"]["output_path"]
    zip_path = Path(result_path) / "project.zip"

    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="Output file not found")

    return FileResponse(
        path=zip_path,
        filename=f"figma_conversion_{job_id}.zip",
        media_type="application/zip"
    )

async def process_conversion(
    job_id: str,
    figma_url: str,
    pat_token: Optional[str],
    target_framework: str,
    include_components: bool
):
    """Background task to process the conversion"""
    try:
        # Update status
        processing_jobs[job_id]["status"] = "processing"
        processing_jobs[job_id]["progress"] = 10.0
        processing_jobs[job_id]["message"] = "Initializing processor..."

        # Get PAT token (user provided or default)
        api_token = pat_token or os.getenv("FIGMA_API_TOKEN")
        if not api_token:
            raise ValueError("No Figma API token provided. Please provide a PAT token or set FIGMA_API_TOKEN in environment variables.")

        processing_jobs[job_id]["progress"] = 20.0
        processing_jobs[job_id]["message"] = f"Using API token: {'User provided' if pat_token else 'Default'}"

        # Initialize processor with API token
        processor_with_token = EnhancedFigmaProcessor(api_token=api_token)

        processing_jobs[job_id]["progress"] = 30.0
        processing_jobs[job_id]["message"] = "Processing design frames..."

        # Process the design with enhanced processor (frames with component collection if requested)
        processor_result = processor_with_token.process_frame_by_frame(figma_url, include_components)

        # Prepare design data for framework generation
        design_data = {
            "file_key": processor_result.get("design_info", {}).get("file_key", ""),
            "frames": processor_result.get("frames", []),
            "total_frames": processor_result.get("design_info", {}).get("total_frames", 0),
            "total_components": processor_result.get("design_info", {}).get("total_components", 0)
        }

        processing_jobs[job_id]["progress"] = 60.0
        processing_jobs[job_id]["message"] = f"Generating {target_framework} code..."

        # Generate code for the target framework
        code_result = generate_framework_code(
            design_data,
            target_framework,
            job_id
        )

        processing_jobs[job_id]["progress"] = 80.0
        processing_jobs[job_id]["message"] = "Preparing project assembly..."

        # Prepare components result from frame processing
        components_result = None
        if include_components:
            components_result = {
                "total_components": processor_result.get("design_info", {}).get("total_components", 0),
                "components": list(processor_result.get("component_references", {}).values()),
                "component_references": processor_result.get("component_references", {})
            }

        processing_jobs[job_id]["progress"] = 90.0
        processing_jobs[job_id]["message"] = "Assembling final project..."

        # Create final project structure (without waiting for components if they're being collected in background)
        final_result = await assemble_project(
            code_result,
            components_result,  # This will be None initially if components are being collected in background
            target_framework,
            job_id
        )

        # Mark as completed
        processing_jobs[job_id]["status"] = "completed"
        processing_jobs[job_id]["progress"] = 100.0
        processing_jobs[job_id]["message"] = "Conversion completed successfully!"
        processing_jobs[job_id]["result"] = final_result

    except Exception as e:
        # Mark as failed
        processing_jobs[job_id]["status"] = "failed"
        processing_jobs[job_id]["message"] = f"Conversion failed: {str(e)}"
        print(f"❌ Conversion failed for job {job_id}: {e}")

def generate_framework_code(design_result: Dict, framework: str, job_id: str) -> Dict[str, Any]:
    """Generate code for the specified framework"""
    try:
        from pathlib import Path
        output_dir = Path(f"output/job_{job_id}")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Use the framework generators module function
        from framework_generators import generate_framework_code as generate_code
        result = generate_code(design_result, framework, output_dir)

        print(f"✅ Generated {framework} code with {result['total_files']} files")
        return result

    except Exception as e:
        print(f"❌ Framework code generation failed: {e}")
        # Fallback to basic structure
        return {
            "framework": framework,
            "files": {},
            "main_file": "index.html",
            "error": str(e)
        }

async def collect_components(design_result: Dict, job_id: str) -> Dict[str, Any]:
    """Collect and organize components"""
    try:
        # Extract nodes data from design result
        nodes_data = []
        if 'frames' in design_result:
            # Extract nodes from frames
            for frame in design_result['frames']:
                if 'component_references' in frame:
                    # Add component nodes to collection
                    for comp_id, comp_data in frame['component_references'].items():
                        nodes_data.append({
                            'id': comp_id,
                            'name': comp_data.get('name', 'Unknown Component'),
                            'type': comp_data.get('type', 'COMPONENT'),
                            'dimensions': comp_data.get('dimensions', {})
                        })

        # Initialize component collector
        collector = ComponentCollector(api_token=os.getenv("FIGMA_API_TOKEN"))

        # Extract file key for asset downloads
        file_key = design_result.get('file_key', '')

        # Collect components
        collection_result = collector.collect_components_from_design(file_key, nodes_data)

        print(f"📦 Collected {collection_result['total_components']} components")
        return collection_result

    except Exception as e:
        print(f"❌ Component collection failed: {e}")
        return {
            "total_components": 0,
            "components": [],
            "error": str(e)
        }

async def assemble_project(code_result: Dict, components_result: Dict, framework: str, job_id: str) -> Dict[str, Any]:
    """Assemble the final project structure"""
    try:
        # Initialize project assembler
        assembler = ProjectAssembler()

        # Generate project name
        project_name = f"figma_converted_{framework}_{job_id}"

        # Assemble complete project
        assembly_result = assembler.assemble_project(
            code_result,
            components_result,
            framework,
            job_id,
            project_name
        )

        print(f"📦 Project assembly complete: {assembly_result.get('files_created', 0)} files")

        return {
            "output_path": assembly_result["project_dir"],
            "zip_path": assembly_result.get("zip_path"),
            "project_name": project_name,
            "framework": framework,
            "files_generated": assembly_result.get("files_created", 0),
            "components_collected": assembly_result.get("components_added", 0),
            "assembly_result": assembly_result
        }

    except Exception as e:
        print(f"❌ Project assembly failed: {e}")
        return {
            "output_path": f"output/job_{job_id}",
            "error": str(e)
        }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )