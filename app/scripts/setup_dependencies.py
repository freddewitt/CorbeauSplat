"""Setup dependencies — orchestrates engine installation.

This module re-exports all classes and functions from app.scripts.installers
for backward compatibility. External code that imports from
``app.scripts.setup_dependencies`` continues to work unchanged.
"""
import sys
from pathlib import Path

# ── Re-export all classes and functions for backward compatibility ──────────
from app.scripts.installers.base import (
    EngineDependency,
    PipEngine,
    DependencyManager,
)
from app.scripts.installers.brush import BrushEngineDep
from app.scripts.installers.sharp import SharpEngineDep
from app.scripts.installers.mapping import ColmapBrewDep, GlomapEngineDep
from app.scripts.installers.supersplat import SuperSplatEngineDep
from app.scripts.installers.extractor_360 import Extractor360EngineDep
from app.scripts.installers.upscayl import UpscaylEngineDep
from app.scripts.installers.spz import SpzEngineDep
from app.scripts.installers.splat_transform import SplatTransformEngineDep
from app.scripts.installers.tools import (
    load_config,
    relax_requirements,
    get_remote_version,
    get_local_version,
    save_local_version,
    check_cargo,
    check_brew,
    check_node,
    check_cmake_ninja,
    check_xcode_tools,
    install_node_js,
    install_build_tools,
    install_rust_toolchain,
    install_system_dependencies,
)

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
    from app.core.system import resolve_project_root
    root = resolve_project_root()
    if sys.platform == "win32":
        return root / ".venv_360" / "Scripts" / "python.exe"
    return root / ".venv_360" / "bin" / "python"


# resolve_project_root is imported from app.core.system
from app.core.system import resolve_project_root


# ── Main entry point ──────────────────────────────────────────────────────

def main():
    root = Path(__file__).resolve().parent.parent.parent
    engines_dir = root / "engines"
    engines_dir.mkdir(parents=True, exist_ok=True)

    manager = DependencyManager(engines_dir)
    manager.register(ColmapBrewDep())
    manager.register(GlomapEngineDep())
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
