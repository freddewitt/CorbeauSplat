"""Installers package — engine dependency management for CorbeauSplat (Windows/CUDA)."""
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
from app.scripts.installers.tools import (
    load_config,
    relax_requirements,
    get_remote_version,
    get_local_version,
    save_local_version,
    check_cargo,
    check_winget,
    check_node,
    check_cmake_ninja,
    install_node_js,
    install_build_tools,
    install_rust_toolchain,
    install_system_dependencies,
)

__all__ = [
    # Base classes
    "EngineDependency",
    "PipEngine",
    "DependencyManager",
    # Engine dependencies
    "BrushEngineDep",
    "ColmapEngineDep",
    "FfmpegEngineDep",
    "GlomapEngineDep",
    "SuperSplatEngineDep",
    "Extractor360EngineDep",
    "UpscaylEngineDep",
    # Utility functions
    "load_config",
    "relax_requirements",
    "get_remote_version",
    "get_local_version",
    "save_local_version",
    "check_cargo",
    "check_winget",
    "check_node",
    "check_cmake_ninja",
    "install_node_js",
    "install_build_tools",
    "install_rust_toolchain",
    "install_system_dependencies",
]
