"""Pipeline run planning (conditional chaining), isolated from Qt.

Decides, based on the mode (Gsplat / Sharp / 4DGS) and ``RunState`` flags, the
ordered list of steps to run when clicking "Launch". Pure logic, hence
testable under the mocked PySide6 (the Batch 3 prompt explicitly asks for
this conditional chaining to be tested).

Rules:
- **Extraction 360**: inserted right after Source if ``source_360`` — it
  converts an equirectangular source into a *new* folder of planar images,
  which the following steps consume in place of the source.
- **Upscale**: inserted between Source and Reconstruction if
  ``upscaler_avant`` (it enlarges the images *before* COLMAP reads them),
  regardless of mode.
- **Gsplat**: Source → Reconstruction (COLMAP), then Training (Brush) if
  ``entrainement_apres``; the post-steps follow their own toggles.
- **Sharp**: Source → Reconstruction (Sharp inference, no Training), then
  post-steps based on toggles.
- **4DGS**: truncated at Source → (Extraction 360) → (Upscale) →
  Reconstruction (no usable .ply output).
"""

_MODES = ("gsplat", "sharp", "4dgs")


def plan_pipeline(mode, run_state):
    """Return the ordered list of step keys to run."""
    if mode not in _MODES:
        mode = "gsplat"

    # Optional pre-step: it must precede Reconstruction, otherwise COLMAP
    # would already have consumed the original images.
    pre_steps = ["source"]
    # Order imposed by the data: 360 extraction produces the folder of planar
    # images that upscale then enlarges, and that COLMAP reads.
    if run_state.source_360:
        pre_steps.append("extraction360")
    if run_state.upscaler_avant:
        pre_steps.append("upscale")

    if mode == "4dgs":
        return [*pre_steps, "reconstruction"]

    steps = [*pre_steps, "reconstruction"]

    # Training: Gsplat only, and only if requested.
    if mode == "gsplat" and run_state.entrainement_apres:
        steps.append("entrainement")

    # Optional post-steps, shared by Gsplat/Sharp, driven by their toggles.
    if run_state.nettoyer_apres:
        steps.append("nettoyage")
    if run_state.exporter_apres:
        steps.append("export")
    if run_state.visualiser_apres:
        steps.append("visualiser")

    return steps
