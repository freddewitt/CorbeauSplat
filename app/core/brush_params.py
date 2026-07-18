"""Surface structurée des paramètres Brush, au-dessus de l'allowlist du moteur.

But : offrir à l'UI (étape Entraînement, module Brush) et à la sauvegarde de
presets des champs structurés (Max Splats, groupe Densification, groupe
Checkpoints) plutôt qu'une chaîne ``custom_args`` en texte libre.

**Contrat de sécurité inchangé** : ce module ne fait que produire le *dict plat*
que ``BrushEngine.build_command()`` consomme déjà. Il ne touche ni à
``ALLOWED_FLAGS`` ni à ``build_command`` : les tokens générés restent strictement
identiques à ceux de l'existant pour les mêmes valeurs. Les flags non gérés
nativement par ``build_command`` (``--save-iterations``, ``--eval-every``,
``--refine-pose``) sont repliés dans ``custom_args``, où l'allowlist les filtre
comme aujourd'hui.
"""

from dataclasses import asdict, dataclass, fields

# Flags promus en champs structurés mais NON gérés nativement par build_command :
# on les replie dans custom_args (l'allowlist du moteur les filtre). Ordre fixe
# pour un rendu de tokens déterministe.
_CUSTOM_ARG_FLAGS = (
    ("save_iterations", "--save-iterations"),
    ("eval_every", "--eval-every"),
    ("refine_pose", "--refine-pose"),
)


@dataclass
class BrushParams:
    """Paramètres d'entraînement Brush structurés.

    Les valeurs ``None`` signifient « non défini » → le flag correspondant est
    omis, exactement comme un dict plat sans la clé.
    """

    # ── Essentiels ────────────────────────────────────────────────────────────
    total_steps: int | None = None
    sh_degree: int | None = None
    max_splats: int | None = None
    device: str | None = None

    # ── Avancé ────────────────────────────────────────────────────────────────
    max_resolution: int | None = None
    with_viewer: bool = False
    build_mode: str | None = None
    custom_args: str = ""

    # ── Densification (déjà géré nativement par build_command) ────────────────
    start_iter: int | None = None
    refine_every: int | None = None
    growth_grad_threshold: float | None = None
    growth_select_fraction: float | None = None
    growth_stop_iter: int | None = None
    refine_pose: str | None = None  # replié dans custom_args

    # ── Checkpoints ───────────────────────────────────────────────────────────
    # checkpoint_interval défaut 7000 : reproduit le défaut de build_command
    # (qui émet toujours --export-every 7000 sauf si mis à 0).
    checkpoint_interval: int = 7000
    save_iterations: str | None = None  # replié dans custom_args
    eval_every: str | None = None       # replié dans custom_args

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BrushParams":
        """Construit depuis un dict, en ignorant les clés inconnues (presets
        anciens / configs sauvegardées d'une version antérieure)."""
        if not isinstance(data, dict):
            return cls()
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid})

    def to_engine_params(self) -> dict:
        """Produit le dict plat consommé par ``BrushEngine.build_command()``.

        Les champs non gérés nativement sont ajoutés à ``custom_args`` (filtrés
        par l'allowlist côté moteur). Aucun flag hors allowlist n'est introduit.
        """
        native_keys = (
            "total_steps", "sh_degree", "max_splats", "device",
            "max_resolution", "with_viewer", "build_mode",
            "start_iter", "refine_every", "growth_grad_threshold",
            "growth_select_fraction", "growth_stop_iter", "checkpoint_interval",
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
