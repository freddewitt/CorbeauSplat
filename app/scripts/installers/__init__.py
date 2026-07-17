"""Installers package — engine dependency management for CorbeauSplat."""
from app.scripts.installers.base import (
    DependencyManager,
    EngineDependency,
    PipEngine,
)
from app.scripts.installers.brush import BrushEngineDep
from app.scripts.installers.extractor_360 import Extractor360EngineDep
from app.scripts.installers.mapping import ColmapBrewDep
from app.scripts.installers.sharp import SharpEngineDep
from app.scripts.installers.supersplat import SuperSplatEngineDep
from app.scripts.installers.tools import (
    check_brew,
    check_cargo,
    check_cmake_ninja,
    check_node,
    check_xcode_tools,
    get_local_version,
    get_remote_version,
    install_build_tools,
    install_node_js,
    install_rust_toolchain,
    install_system_dependencies,
    load_config,
    relax_requirements,
    save_local_version,
)
from app.scripts.installers.upscayl import UpscaylEngineDep

__all__ = [
    # Base classes
    "EngineDependency",
    "PipEngine",
    "DependencyManager",
    # Engine dependencies
    "BrushEngineDep",
    "SharpEngineDep",
    "ColmapBrewDep",
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
    "check_brew",
    "check_node",
    "check_cmake_ninja",
    "check_xcode_tools",
    "install_node_js",
    "install_build_tools",
    "install_rust_toolchain",
    "install_system_dependencies",
]
