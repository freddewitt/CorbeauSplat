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
    """SOLID-SRP : persiste le dernier projet (état du panneau Source — chemins
    source/sortie, nom de projet, options associées) dans ``config.json``, sous
    la clé ``"last_project"``.

    ``config.json`` est partagé avec ``LanguageManager`` (clé ``"language"``,
    cf. ``app/core/i18n.py``) : toute écriture ici lit d'abord le fichier
    existant, ne modifie que sa propre clé, puis réécrit l'ensemble — jamais de
    remplacement complet du fichier, pour ne pas écraser les autres clés.
    """

    CONFIG_KEY = "last_project"

    def __init__(self, main_window):
        self.mw = main_window
        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._do_save)

    def get_session_file(self) -> Path:
        return resolve_project_root() / "config.json"

    def save(self, immediate=False):
        """Optimisation Perf-IO : Debounce de la sauvegarde JSON pour ne pas geler l'UI"""
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
        self._write_merged(panel.get_state())

    def _write_merged(self, project_state):
        """Lit ``config.json`` existant, met à jour uniquement ``CONFIG_KEY``,
        réécrit — même principe de fusion que ``LanguageManager.save_config``."""
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
        if not project_state:
            return

        panel = self._source_panel()
        if panel is not None and hasattr(panel, "set_state"):
            panel.set_state(project_state)


class AppLifecycle:
    """SOLID-SRP : Responsable du redemarrage OS et processus externes"""
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
