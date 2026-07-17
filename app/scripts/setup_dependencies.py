"""Setup dependencies — orchestrates engine installation.

This module re-exports all classes and functions from app.scripts.installers
for backward compatibility. External code that imports from
``app.scripts.setup_dependencies`` continues to work unchanged.
"""
import sys
from pathlib import Path

from app.core.system import resolve_project_root

# ── Re-export all classes and functions for backward compatibility ──────────
from app.scripts.installers.base import (
    DependencyManager,
    EngineDependency,
    PipEngine,
)
from app.scripts.installers.brush import BrushEngineDep
from app.scripts.installers.extractor_360 import Extractor360EngineDep
from app.scripts.installers.mapping import ColmapBrewDep
from app.scripts.installers.sharp import SharpEngineDep
from app.scripts.installers.splat_transform import SplatTransformEngineDep
from app.scripts.installers.spz import SpzEngineDep
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
    "BrushEngineDep",
    "ColmapBrewDep",
    "DependencyManager",
    "EngineDependency",
    "Extractor360EngineDep",
    "PipEngine",
    "SharpEngineDep",
    "SplatTransformEngineDep",
    "SpzEngineDep",
    "SuperSplatEngineDep",
    "UpscaylEngineDep",
    "check_brew",
    "check_cargo",
    "check_cmake_ninja",
    "check_node",
    "check_xcode_tools",
    "get_local_version",
    "get_remote_version",
    "install_build_tools",
    "install_extractor_360",
    "install_node_js",
    "install_rust_toolchain",
    "install_sharp",
    "install_system_dependencies",
    "install_upscale",
    "load_config",
    "relax_requirements",
    "save_local_version",
    "uninstall_extractor_360",
    "uninstall_sharp",
    "uninstall_upscale",
]

# ── Compatibility wrappers (used by external modules) ──────────────────────

def uninstall_sharp():
    return SharpEngineDep().uninstall()

def install_sharp(engines_dir=None, version_file=None):
    # Compatibility wrapper
    dep = SharpEngineDep()
    dep.install()
    return dep.is_installed()

def uninstall_upscale():
    return UpscaylEngineDep().uninstall()

def install_upscale():
    dep = UpscaylEngineDep()
    dep.install()
    return dep.is_installed()

def uninstall_extractor_360():
    return Extractor360EngineDep().uninstall()

def install_extractor_360():
    dep = Extractor360EngineDep()
    dep.install()
    return dep.is_installed()

def get_venv_360_python():
    """Returns path to python executable in .venv_360"""
    root = resolve_project_root()
    if sys.platform == "win32":
        return root / ".venv_360" / "Scripts" / "python.exe"
    return root / ".venv_360" / "bin" / "python"


# resolve_project_root is imported from app.core.system


# ── Main entry point ──────────────────────────────────────────────────────

def main():
    root = Path(__file__).resolve().parent.parent.parent
    engines_dir = root / "engines"
    engines_dir.mkdir(parents=True, exist_ok=True)

    manager = DependencyManager(engines_dir)
    manager.register(ColmapBrewDep())
    manager.register(BrushEngineDep())
    manager.register(SharpEngineDep())
    manager.register(SuperSplatEngineDep())
    manager.register(Extractor360EngineDep())
    manager.register(UpscaylEngineDep())
    manager.register(SpzEngineDep())
    manager.register(SplatTransformEngineDep())

    check_only = "--check" in sys.argv
    startup = "--startup" in sys.argv
    manager.main_install(check_only=check_only, startup=startup)

if __name__ == "__main__":
    main()
