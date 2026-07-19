# Split-flap board generator for Blender (runs inside a running Blender
# instance, not as a standalone CLI script).

from importlib import reload as _reload
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]

from . import params, charset, atlas, materials, board, demo, lookdev  # noqa: E402


def reload_all():
    """Reload submodules in dependency order (for iteration)."""
    for m in (params, charset, atlas, materials, board, demo, lookdev):
        _reload(m)


def build_all(p=None, with_atlas=False, initial_rows=None):
    pp = p or params.BoardParams()
    out = {}
    if with_atlas:
        out["atlas"] = atlas.build_atlas(
            pp, str(PROJECT_DIR / "assets/atlas/flap_atlas.png"))
    out["board"] = board.build(pp, initial_rows=initial_rows)
    out["lookdev"] = lookdev.setup(pp)
    return out
