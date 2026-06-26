"""Scripts package — dependency management and utilities for CorbeauSplat."""
# Re-exports from installers/ for package-level convenience.
# External code should import from app.scripts.installers.* or
# app.scripts.setup_dependencies directly to avoid import ordering warnings.
from app.scripts.installers.base import (
    EngineDependency,
    PipEngine,
    DependencyManager,
)
from app.scripts.installers.brush import BrushEngineDep
from app.scripts.installers.mapping import ColmapEngineDep, FfmpegEngineDep, GlomapEngineDep
from app.scripts.installers.supersplat import SuperSplatEngineDep
from app.scripts.installers.extractor_360 import Extractor360EngineDep
from app.scripts.installers.upscayl import UpscaylEngineDep
