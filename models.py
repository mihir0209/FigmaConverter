from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, RootModel


class FrameBasicInfo(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    type: Optional[str] = None
    dimensions: Dict[str, float] = Field(default_factory=dict)


class FrameLayout(BaseModel):
    layout_mode: Optional[str] = None             # NONE | HORIZONTAL | VERTICAL
    padding: Dict[str, float] = Field(default_factory=dict)  # top/right/bottom/left
    gap: Optional[float] = None                    # itemSpacing
    alignment: Dict[str, str] = Field(default_factory=dict)  # primary_axis / counter_axis
    primary_axis_align_items: Optional[str] = None  # MIN | CENTER | MAX | SPACE_BETWEEN
    counter_axis_align_items: Optional[str] = None  # MIN | CENTER | MAX | BASELINE
    sizing_horizontal: Optional[str] = None         # FIXED | FILL | HUG
    sizing_vertical: Optional[str] = None           # FIXED | FILL | HUG
    layout_grow: Optional[float] = 0                # flex grow factor
    layout_align: Optional[str] = None              # MIN | CENTER | MAX | STRETCH | INHERIT
    layout_wrap: Optional[str] = None               # NO_WRAP | WRAP


class TextElement(BaseModel):
    id: str = ""
    text: str = ""
    font_family: str = ""
    font_size: float = 0
    font_weight: int = 400
    color: str = ""
    position: Dict[str, float] = Field(default_factory=dict)
    alignment: str = ""
    line_height: float = 0


class ImageElement(BaseModel):
    id: str = ""
    image_ref: str = ""
    position: Dict[str, float] = Field(default_factory=dict)
    alt_text: str = ""


class ContainerElement(BaseModel):
    id: str = ""
    name: str = ""
    element_type: str = ""
    position: Dict[str, float] = Field(default_factory=dict)
    background_color: Optional[str] = None
    border_radius: Optional[float] = None
    children_count: int = 0


class FrameContent(BaseModel):
    texts: List[TextElement] = Field(default_factory=list)
    images: List[ImageElement] = Field(default_factory=list)
    containers: List[ContainerElement] = Field(default_factory=list)
    interactive_elements: List[Dict[str, Any]] = Field(default_factory=list)


class ComprehensiveFrameData(BaseModel):
    basic_info: FrameBasicInfo = Field(default_factory=FrameBasicInfo)
    layout: FrameLayout = Field(default_factory=FrameLayout)
    content: FrameContent = Field(default_factory=FrameContent)
    design_system: Dict[str, Any] = Field(default_factory=dict)
    structure: Dict[str, Any] = Field(default_factory=dict)
    component_count: int = 0
    complexity_score: float = 0.0


class ComponentRecord(BaseModel):
    type: str = ""
    path: str = ""
    original_name: str = ""
    dimensions: Dict[str, float] = Field(default_factory=dict)

    # Legacy shape (list-based component collector)
    id: Optional[str] = None
    name: Optional[str] = None
    safe_name: Optional[str] = None
    styles: Dict[str, Any] = Field(default_factory=dict)
    assets: Dict[str, str] = Field(default_factory=dict)


class ComponentsResult(BaseModel):
    total_components: int = 0
    components: Union[Dict[str, ComponentRecord], List[ComponentRecord]] = Field(default_factory=dict)


class DependencySuggestions(BaseModel):
    required: List[str] = Field(default_factory=list)
    additional_suggestions: List[str] = Field(default_factory=list)
    reasoning: str = ""


class ComponentGenerationResponse(BaseModel):
    component_name: str = ""
    content: str = ""
    file_path: str = ""
    dependencies: DependencySuggestions = Field(default_factory=DependencySuggestions)
    styling: Optional[Dict[str, Any]] = None
    props: Optional[List[Dict[str, Any]]] = None


class MainAppEntry(BaseModel):
    content: str = ""
    file_path: str = ""


class MainAppGenerationResponse(BaseModel):
    main_app: MainAppEntry = Field(default_factory=MainAppEntry)
    routing: Optional[MainAppEntry] = None
    entry_point: Optional[MainAppEntry] = None
    global_styles: Optional[MainAppEntry] = None


class FrameworkStructure(BaseModel):
    component_extension: str = ""
    main_file: str = ""
    config_files: List[str] = Field(default_factory=list)
    folder_structure: Dict[str, List[str]] = Field(default_factory=dict)


class FrameworkDiscoveryResponse(BaseModel):
    framework: str = ""
    version: str = ""
    structure: FrameworkStructure = Field(default_factory=FrameworkStructure)
    styling: Optional[Dict[str, Any]] = None
    routing: Optional[Dict[str, Any]] = None
    build_tool: Optional[str] = None
    package_manager: Optional[str] = None


class TechnologyStack(BaseModel):
    primary: str = ""
    styling: str = ""
    build_tool: str = ""
    package_manager: str = ""


class ProjectStructure(BaseModel):
    root_folders: List[str] = Field(default_factory=list)
    component_location: str = ""
    assets_location: str = ""
    main_file: str = ""
    config_files: List[str] = Field(default_factory=list)


class FileConventions(BaseModel):
    component_extension: str = ""
    style_extension: str = ""
    naming_convention: str = ""


class FrameworkDependencies(BaseModel):
    core: List[str] = Field(default_factory=list)
    build: List[str] = Field(default_factory=list)
    styling: List[str] = Field(default_factory=list)


class FrameworkDetectionResult(BaseModel):
    success: bool = False
    framework: str = ""
    framework_name: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    detection_method: str = ""
    timestamp: str = ""
    technology_stack: TechnologyStack = Field(default_factory=TechnologyStack)
    project_structure: ProjectStructure = Field(default_factory=ProjectStructure)
    file_conventions: FileConventions = Field(default_factory=FileConventions)
    dependencies: Optional[FrameworkDependencies] = None
    special_instructions: str = ""


class PackageJsonDeps(BaseModel):
    dependencies: Dict[str, str] = Field(default_factory=dict)
    devDependencies: Dict[str, str] = Field(default_factory=dict)


class DependencyResolutionResponse(BaseModel):
    dependencies: Optional[Dict[str, PackageJsonDeps]] = None
    file_updates: Optional[Dict[str, Dict[str, Any]]] = None
    missing_dependencies: List[str] = Field(default_factory=list)
    framework_specific: Optional[Dict[str, Dict[str, Any]]] = None
    resolution_summary: Optional[Dict[str, int]] = None


class FrameDependencySuggestion(BaseModel):
    frame_name: str = ""
    suggestions: DependencySuggestions = Field(default_factory=DependencySuggestions)


class ArchitectureRoute(BaseModel):
    path: str = ""
    component: str = ""
    is_default: bool = False


class AppArchitecture(BaseModel):
    app_architecture: Dict[str, Any] = Field(default_factory=dict)
    frame_connections: List[Dict[str, Any]] = Field(default_factory=list)
    shared_components: List[str] = Field(default_factory=list)
    route_structure: List[ArchitectureRoute] = Field(default_factory=list)
    app_state: Dict[str, Any] = Field(default_factory=dict)


class PreliminaryDependencies(BaseModel):
    dependencies: Dict[str, PackageJsonDeps] = Field(default_factory=dict)


class FinalCodeResult(BaseModel):
    framework: str = ""
    files: Dict[str, str] = Field(default_factory=dict)
    main_file: str = ""
    framework_structure: Dict[str, Any] = Field(default_factory=dict)
    dependency_resolution: Dict[str, Any] = Field(default_factory=dict)
    dependency_suggestions: List[FrameDependencySuggestion] = Field(default_factory=list)


class OrchestratorFrameResult(BaseModel):
    files: Dict[str, str] = Field(default_factory=dict)
    dependency_suggestions: DependencySuggestions = Field(default_factory=DependencySuggestions)
    frame_name: str = ""


class RefinementRequest(BaseModel):
    prompt: str = Field(..., max_length=2000)
    target_files: Optional[List[str]] = None  # None = all files


class RefinementEntry(BaseModel):
    iteration: int = 0
    prompt: str = ""
    changed_files: List[str] = Field(default_factory=list)
    summary: str = ""
    timestamp: str = ""


class RefinementResponse(BaseModel):
    updated_files: Dict[str, str] = Field(default_factory=dict)
    changed_files: List[str] = Field(default_factory=list)
    summary: str = ""
    iteration: int = 0
    refinement_count: int = 0


# ---------------------------------------------------------------------------
# Design tokens (Plan 003)
# ---------------------------------------------------------------------------


class ColorToken(BaseModel):
    name: str = ""
    value: str = ""
    description: str = ""
    source: str = "figma_variable"  # figma_variable | hex_literal


class TypographyToken(BaseModel):
    name: str = ""
    font_family: str = ""
    font_size: str = ""
    font_weight: int = 400
    line_height: Optional[str] = None


class SpacingToken(BaseModel):
    name: str = ""
    value: str = ""  # e.g. "16px"


class RadiusToken(BaseModel):
    name: str = ""
    value: str = ""


class ShadowToken(BaseModel):
    name: str = ""
    value: str = ""  # e.g. "0 2px 4px rgba(0, 0, 0, 0.1)"


class TokenCollection(BaseModel):
    colors: List[ColorToken] = Field(default_factory=list)
    typography: List[TypographyToken] = Field(default_factory=list)
    spacing: List[SpacingToken] = Field(default_factory=list)
    radius: List[RadiusToken] = Field(default_factory=list)
    shadows: List[ShadowToken] = Field(default_factory=list)
    source: str = ""  # 'figma_variables' | 'extracted_fallback' | 'mixed'
    token_count: int = 0

    def has_tokens(self) -> bool:
        return any(
            [self.colors, self.typography, self.spacing, self.radius, self.shadows]
        )
