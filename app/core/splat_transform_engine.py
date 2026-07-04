"""SplatTransformEngine — wraps the PlayCanvas splat-transform CLI.

Security decisions (consistent with audit v0.99.3):
- HTTP/HTTPS inputs are explicitly rejected; only local paths validated by
  validate_path() are accepted. splat-transform accepts URL inputs natively,
  but exposing that would create an SSRF surface.
- All arguments are passed as a list; shell=True is never used.
- Only flags in ALLOWED_FLAGS are forwarded; arbitrary user strings are rejected.
"""
import shutil
from pathlib import Path
from typing import Optional, Callable, Dict, Any

from .base_engine import BaseEngine
from .system import resolve_project_root


class SplatTransformEngine(BaseEngine):
    """Engine for running PlayCanvas splat-transform conversions and filters.

    Supports format conversion (PLY ↔ SPZ ↔ GLB ↔ compressed PLY …) and
    a curated set of data-cleaning operations exposed via ALLOWED_FLAGS.
    """

    # Flags that take no value
    ALLOWED_FLAGS_BOOLEAN = {
        "--filter-nan",    # Remove NaN/degenerate splats (closest to "filterFloaters")
        "--morton-order",  # Optimize spatial ordering
        "--quiet",
        "--overwrite",
        "--summary",
    }

    # Flags that take exactly one value argument
    ALLOWED_FLAGS_VALUE = {
        "--filter-harmonics",  # 0|1|2|3 — strip SH bands
        "--decimate",          # n or n% — reduce point count
        "--gpu",               # n|cpu — GPU device selection
    }

    def __init__(self, logger_callback: Optional[Callable] = None) -> None:
        super().__init__("SplatTransform", logger_callback)
        self._bin = self._resolve_bin()

    def _resolve_bin(self) -> Optional[str]:
        root = resolve_project_root()
        local_bin = (
            root / "engines" / "splat-transform"
            / "node_modules" / ".bin" / "splat-transform"
        )
        if local_bin.exists():
            return str(local_bin)
        return shutil.which("splat-transform")

    def is_available(self) -> bool:
        return self._bin is not None and Path(self._bin).exists()

    def transform(
        self,
        input_path: str,
        output_path: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Run splat-transform on a local file.

        Parameters
        ----------
        input_path:
            Source file (PLY, SPZ, …). HTTP/HTTPS rejected.
        output_path:
            Destination file. The output format is inferred from the extension.
        params:
            Dict of options. Boolean flags: set value to True. Value flags: set
            to the desired string/number. Example:
            {"--filter-nan": True, "--filter-harmonics": "1", "--decimate": "50%"}

        Returns
        -------
        int
            Return code (0 = success).
        """
        if not self.is_available():
            self.log("SplatTransform binary not found. Install via dependency setup.")
            return -1

        # Reject URL inputs explicitly (SSRF prevention)
        if str(input_path).startswith(("http://", "https://")):
            self.log("SECURITY: URL inputs are not accepted. Provide a local file path.")
            return -1

        safe_in = self.validate_path(input_path)
        safe_out = self.validate_path(output_path)

        # Output may not exist yet — validate the parent directory instead
        if safe_out is None:
            out_parent = Path(output_path).parent
            safe_parent = self.validate_path(str(out_parent))
            if safe_parent is None:
                self.log(f"Invalid or insecure output path: {output_path}")
                return -1
            safe_out = safe_parent / Path(output_path).name

        if safe_in is None:
            self.log(f"Invalid or insecure input path: {input_path}")
            return -1

        # Build command: [bin, input, <transform_flags>, output]
        cmd = [self._bin, str(safe_in)]
        cmd.extend(self._build_flags(params or {}))
        cmd.append(str(safe_out))

        self.log(f"SplatTransform: {safe_in.name} → {safe_out.name}")
        return self._execute_command(cmd)

    def _build_flags(self, params: Dict[str, Any]) -> list:
        flags = []
        for key, val in params.items():
            if key in self.ALLOWED_FLAGS_BOOLEAN:
                if val:
                    flags.append(key)
            elif key in self.ALLOWED_FLAGS_VALUE:
                if val is not None and str(val) != "":
                    flags.extend([key, str(val)])
            else:
                self.log(f"Avertissement de sécurité: flag non autorisé ignoré ({key})")
        return flags
