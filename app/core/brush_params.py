"""Structured surface of the Brush parameters, on top of the engine allowlist.

Goal: give the UI (Entraînement step, Brush module) and preset saving structured
fields (Max Splats, Densification group, Checkpoints group) rather than a
free-text ``custom_args`` string.

**Security contract unchanged**: this module only produces the *flat dict* that
``BrushEngine.build_command()`` already consumes. It touches neither
``ALLOWED_FLAGS`` nor ``build_command``: for the same values, the generated
tokens stay strictly identical to the existing ones. Flags not handled natively
by ``build_command`` (``--save-iterations``, ``--eval-every``, ``--refine-pose``)
are folded into ``custom_args``, where the allowlist filters them as it does
today.
"""

from dataclasses import asdict, dataclass, fields

# Flags promoted to structured fields but NOT handled natively by build_command:
# we fold them into custom_args (the engine allowlist filters them). Fixed order
# for deterministic token output.
_CUSTOM_ARG_FLAGS = (
    ("save_iterations", "--save-iterations"),
    ("eval_every", "--eval-every"),
    ("refine_pose", "--refine-pose"),
)


@dataclass
class BrushParams:
    """Structured Brush training parameters.

    ``None`` values mean "unset" → the matching flag is omitted, exactly like a
    flat dict without the key.
    """

    # ── Essentials ────────────────────────────────────────────────────────────
    total_steps: int | None = None
    sh_degree: int | None = None
    max_splats: int | None = None
    device: str | None = None

    # ── Advanced ──────────────────────────────────────────────────────────────
    max_resolution: int | None = None
    with_viewer: bool = False
    build_mode: str | None = None
    custom_args: str = ""

    # ── Densification (already handled natively by build_command) ─────────────
    start_iter: int | None = None
    refine_every: int | None = None
    growth_grad_threshold: float | None = None
    growth_select_fraction: float | None = None
    growth_stop_iter: int | None = None
    refine_pose: str | None = None  # folded into custom_args

    # ── Checkpoints ───────────────────────────────────────────────────────────
    # checkpoint_interval defaults to 7000: reproduces build_command's default
    # (which always emits --export-every 7000 unless set to 0).
    checkpoint_interval: int = 7000
    save_iterations: str | None = None  # folded into custom_args
    eval_every: str | None = None       # folded into custom_args

    # ── Mode ──────────────────────────────────────────────────────────────────
    refine_mode: bool = False  # True = resume an existing training run

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BrushParams":
        """Build from a dict, ignoring unknown keys (old presets / configs saved
        by an earlier version).
        """
        if not isinstance(data, dict):
            return cls()
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid})

    def to_engine_params(self) -> dict:
        """Produce the flat dict consumed by ``BrushEngine.build_command()``.

        Fields not handled natively are appended to ``custom_args`` (filtered by
        the allowlist on the engine side). No flag outside the allowlist is
        introduced.
        """
        native_keys = (
            "total_steps", "sh_degree", "max_splats", "device",
            "max_resolution", "with_viewer", "build_mode",
            "start_iter", "refine_every", "growth_grad_threshold",
            "growth_select_fraction", "growth_stop_iter", "checkpoint_interval",
            "refine_mode",
        )
        params = {k: getattr(self, k) for k in native_keys if getattr(self, k) is not None}

        extra_tokens: list[str] = []
        for attr, flag in _CUSTOM_ARG_FLAGS:
            value = getattr(self, attr)
            if value is not None and str(value) != "":
                extra_tokens.extend([flag, str(value)])

        custom = self.custom_args.strip()
        if extra_tokens:
            custom = (custom + " " + " ".join(extra_tokens)).strip() if custom else " ".join(extra_tokens)
        if custom:
            params["custom_args"] = custom
        return params
