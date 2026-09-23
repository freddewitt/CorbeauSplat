import json
import logging
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.core.system import resolve_project_root

logger = logging.getLogger(__name__)

class SessionManager:
    """SOLID-SRP: persists the last project (state of the Source panel —
    source/output paths, project name, associated options) in ``config.json``,
    under the ``"last_project"`` key.

    ``config.json`` is shared with ``LanguageManager`` (``"language"`` key, cf.
    ``app/core/i18n.py``): every write here first reads the existing file,
    changes only its own key, then rewrites the whole — never a full
    replacement of the file, so the other keys are not lost.
    """

    CONFIG_KEY = "last_project"
    # L5-05: the chaining flags (RunState) used to be dropped entirely by
    # autosave/load — a sibling top-level key, not nested inside CONFIG_KEY,
    # so ``config["last_project"]`` keeps holding exactly ``get_state()``
    # (existing tests compare it verbatim).
    FLAGS_KEY = "last_project_flags"

    def __init__(self, main_window):
        self.mw = main_window
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save)

    def get_session_file(self) -> Path:
        return resolve_project_root() / "config.json"

    def save(self, immediate=False):
        """Perf-IO optimisation: debounce the JSON save so the UI does not freeze"""
        if immediate:
            self._save_timer.stop()
            self._do_save()
        else:
            self._save_timer.start(1500) # Debounce 1.5s

    def _source_panel(self):
        return self.mw.panels.get("source") if hasattr(self.mw, "panels") else None

    def _do_save(self):
        panel = self._source_panel()
        if panel is None or not hasattr(panel, "get_state"):
            return
        self._write_merged(panel.get_state(), self._collect_flags())

    def _collect_flags(self):
        """``RunState.to_dict()`` when available (L5-05), or ``None``.

        Guarded with an ``isinstance`` check rather than a bare ``hasattr``:
        under the mocked-``main_window`` test fixtures ``run_state`` is a
        ``MagicMock`` too, and ``to_dict()`` on it returns another
        ``MagicMock`` — not JSON-serialisable — which would otherwise crash
        ``json.dump`` in tests that never set up a real ``run_state``.
        """
        run_state = getattr(self.mw, "run_state", None)
        if run_state is None or not hasattr(run_state, "to_dict"):
            return None
        flags = run_state.to_dict()
        return flags if isinstance(flags, dict) else None

    def _write_merged(self, project_state, flags=None):
        """Read the existing ``config.json``, update ``CONFIG_KEY`` (and
        ``FLAGS_KEY`` when ``flags`` is given), rewrite — same merge principle
        as ``LanguageManager.save_config``."""
        session_file = self.get_session_file()
        config = {}
        if session_file.exists():
            try:
                with open(session_file, encoding="utf-8") as f:
                    existing = json.load(f)
                    if isinstance(existing, dict):
                        config = existing
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("Session: config.json illisible, fusion prudente: %s", e)

        config[self.CONFIG_KEY] = project_state
        if flags is not None:
            config[self.FLAGS_KEY] = flags
        try:
            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except OSError as e:
            logger.error("Erreur sauvegarde session: %s", e)

    def load(self):
        session_file = self.get_session_file()
        if not session_file.exists():
            return

        try:
            with open(session_file, encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Erreur chargement session: %s", e)
            return

        if not isinstance(config, dict):
            return
        project_state = config.get(self.CONFIG_KEY)
        if project_state:
            panel = self._source_panel()
            if panel is not None and hasattr(panel, "set_state"):
                panel.set_state(project_state)

        # L5-05: restore the chaining flags saved alongside the project.
        flags = config.get(self.FLAGS_KEY)
        if flags:
            run_state = getattr(self.mw, "run_state", None)
            if run_state is not None and hasattr(run_state, "load_dict"):
                run_state.load_dict(flags)


class AppLifecycle:
    """SOLID-SRP: responsible for restarting the OS process and external ones"""
    @staticmethod
    def restart(save_callback=None):
        if save_callback:
            try:
                save_callback()
            except Exception as e:
                logger.warning("Error saving session before restart: %s", e)

        root_dir = resolve_project_root()
        python = sys.executable
        main_py = root_dir / "main.py"

        engines_dir = root_dir / "engines"
        needs_setup = not (engines_dir / "brush").exists()

        if needs_setup and sys.platform != "win32":
            logger.info("Reinstall detected: running setup before relaunch...")
            # Build safe argv: whitelist known flags only
            safe_argv = [a for a in sys.argv[1:] if a in ("--gui", "--debug", "--reset")]
            # FIX(AUDIT): use direct subprocess calls instead of bash -c
            # to prevent command injection via f-string interpolation.
            subprocess.run(
                [python, "-m", "app.scripts.setup_dependencies", "--startup"],
                cwd=str(root_dir)
            )
            subprocess.Popen(
                [python, str(main_py)] + safe_argv,
                cwd=str(root_dir), start_new_session=True
            )
            QApplication.quit()
            sys.exit(0)

        # Relance normale
        args = [python, str(main_py)] + sys.argv[1:]
        logger.info("Relaunching via execv: %s", args)

        if sys.platform != "win32":
            try:
                os.execv(python, args)
            except OSError as e:
                logger.warning("execv failed: %s. Falling back to Popen.", e)

        kwargs = {}
        if sys.platform != "win32":
            kwargs["start_new_session"] = True

        subprocess.Popen(args, cwd=str(root_dir), **kwargs)
        QApplication.quit()
        sys.exit(0)

    @staticmethod
    def reset_factory(deep=False):
        QApplication.quit()

        root_dir = resolve_project_root().resolve()
        run_cmd = root_dir / "CorbeauSplat.command"

        # Collect deletion targets (relative names only)
        targets_rel = [".venv", ".venv_sharp", ".venv_360"]

        if deep:
            targets_rel.append("engines")
            targets_rel.append("config.json")

        logger.info("Reset Factory %s initié sur: %s", "DEEP" if deep else "LIGHT", root_dir)

        # Validate containment: every target must resolve inside project root
        import shutil as _shutil
        for rel in list(targets_rel):
            target = (root_dir / rel).resolve()
            try:
                target.relative_to(root_dir)
            except ValueError:
                logger.warning("Reset blocked: path outside project root — %s", target)
                targets_rel.remove(rel)
            else:
                # Remove the target if it exists
                if not target.exists():
                    continue
                try:
                    logger.warning("Reset: removing %s", target)
                    if target.is_dir():
                        _shutil.rmtree(target, ignore_errors=False)
                    else:
                        target.unlink()
                except OSError as e:
                    logger.warning("Reset: could not remove %s — %s", target, e)

        # Also clean deep sync-conflict files
        if deep:
            for p in root_dir.glob("config.sync-conflict-*"):
                try:
                    p.relative_to(root_dir)
                    logger.warning("Reset: removing %s", p)
                    p.unlink()
                except (ValueError, OSError):
                    pass

        # Relaunch via CorbeauSplat.command
        if run_cmd.exists():
            logger.info("Reset: relaunching via %s", run_cmd)
            subprocess.Popen(["open", str(run_cmd)], start_new_session=True)
        else:
            logger.warning("Reset: launcher not found at %s, relaunching main.py", run_cmd)
            subprocess.Popen([sys.executable, str(root_dir / "main.py"), "--gui"], start_new_session=True)
        sys.exit(0)
