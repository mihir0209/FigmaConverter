# Enhanced Figma Processor

A robust Python-based tool for processing Figma designs frame-by-frame with intelligent component export and AI-ready referencing.

## Features

- **Frame-by-Frame Processing**: Handles large designs (70k+ lines) by processing one frame at a time
- **Intelligent Component Export**: Automatically extracts and organizes images, vectors, and other assets
- **Component Referencing**: Creates structured references for AI code generation
- **File System Organization**: Organizes components by type in clean folder structure
- **AI Integration Ready**: Formats component data for seamless AI prompt integration

## Project Structure

```
FigmaConverter/
├── enhanced_figma_processor.py    # Main processing engine
├── test_enhanced_processor.py     # Test and demonstration script
├── config.env.example            # Configuration template
├── components/                   # Auto-generated component storage
│   ├── images/                  # Exported images (PNG)
│   ├── vectors/                 # Exported vectors (SVG)
│   ├── icons/                   # Exported icons
│   ├── videos/                  # Exported videos
│   └── metadata/                # Component manifests and references
├── output/                      # Processing results and logs
└── progress.md                  # Development progress tracking
```

## Setup

1. **Install Dependencies**
   ```bash
   pip install requests python-dotenv
   ```

2. **Configure API Tokens**
   ```bash
   # Copy the example config
   cp config.env.example config.env

   # Edit config.env with your API tokens
   # Required: FIGMA_API_TOKEN
   # Optional: AI provider API keys
   ```

3. **Set Environment Variables**
   ```bash
   # Windows
   set FIGMA_API_TOKEN=your_token_here

   # Linux/Mac
   export FIGMA_API_TOKEN=your_token_here
   ```

## Usage

### Basic Processing

```python
from enhanced_figma_processor import EnhancedFigmaProcessor

# Initialize processor
processor = EnhancedFigmaProcessor()

# Process a Figma design
result = processor.process_frame_by_frame(
    "https://www.figma.com/design/YOUR_FILE_KEY/YOUR_FILE_NAME"
)

print(f"Processed {result['design_info']['total_frames']} frames")
print(f"Exported {result['design_info']['total_components']} components")
```

### Component Reference for AI

```python
# Get component reference for AI prompts
component_ref = processor.get_component_reference_for_ai(component_id)

# Example output:
{
    'id': '123:456',
    'type': 'image',
    'path': 'components/images/frame1_logo_456.png',
    'name': 'Logo',
    'width': 200,
    'height': 100
}
```

### Running Tests

```bash
# Run the test script
python test_enhanced_processor.py
```

## Component Export Structure

The processor automatically creates this folder structure:

```
components/
├── images/
│   ├── frameName_componentName_componentID.png
│   └── ...
├── vectors/
│   ├── frameName_componentName_componentID.svg
│   └── ...
├── metadata/
│   └── manifest.json
└── ...
```

## Component Manifest

The `manifest.json` file contains:

```json
{
  "generated_at": "2024-01-15T10:30:00",
  "total_components": 25,
  "components": {
    "123:456": {
      "type": "image",
      "path": "components/images/frame1_logo_456.png",
      "original_name": "Logo",
      "dimensions": {
        "width": 200,
        "height": 100,
        "x": 50,
        "y": 25
      }
    }
  }
}
```

## Processing Flow

1. **URL Parsing**: Extract file key from Figma URL
2. **Design Fetch**: Download complete design data from Figma API
3. **Frame Identification**: Identify all frames in the design
4. **Frame-by-Frame Processing**:
   - Extract components from each frame
   - Export component assets (images, vectors)
   - Generate component references
5. **Component Organization**: Save assets to organized folder structure
6. **Manifest Generation**: Create component manifest for referencing

## Error Handling

The processor includes comprehensive error handling for:

- Invalid Figma URLs
- API rate limits
- Network timeouts
- Missing API tokens
- File system permissions
- Component export failures

## Integration with AI Engine

The component references are formatted specifically for AI code generation:

```python
# Example AI prompt integration
ai_prompt = f"""
Generate HTML/CSS for this component:
- Image: {component_ref['path']}
- Dimensions: {component_ref['width']}x{component_ref['height']}
- Name: {component_ref['name']}
"""
```

## Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_FRAME_SIZE` | 5000 | Maximum frame dimension for processing |
| `COMPONENT_EXPORT_QUALITY` | 2 | Export quality multiplier (1x, 2x, 3x) |
| `TIMEOUT_SECONDS` | 30 | API request timeout |
| `OUTPUT_DIR` | ./output | Output directory for results |
| `LOG_LEVEL` | INFO | Logging verbosity |

## Troubleshooting

### Common Issues

1. **"FIGMA_API_TOKEN not found"**
   - Set the environment variable: `export FIGMA_API_TOKEN=your_token`

2. **"Could not extract file key from URL"**
   - Ensure the Figma URL is in the correct format
   - URL should contain `/design/` or `/file/`

3. **"Could not fetch design data"**
   - Verify the Figma file is public or you have access
   - Check your API token permissions

4. **Large files causing memory issues**
   - The frame-by-frame processing handles this automatically
   - Each frame is processed individually

### Getting Figma API Token

1. Go to Figma Settings
2. Navigate to Account → Personal access tokens
3. Create a new token
4. Copy and store securely

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
