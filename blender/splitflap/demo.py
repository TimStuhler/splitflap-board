# Demo animation: "spell text" - sequential flips with a falling character.
# Blender-side only (custom properties + rotor rotation); the export stays untouched.

import math

import bpy

from . import charset
from .params import BoardParams

TILT = math.radians(5.0)
REST = -TILT                 # rest position, top
LAND = math.pi - TILT        # landing, bottom (+175deg)


def _cells():
    root = bpy.data.objects.get("SplitflapBoard")
    if root is None:
        raise RuntimeError("No SplitflapBoard in the scene - run board.build() first")
    rows, cols = root["sf_rows"], root["sf_cols"]
    out = {}
    for r in range(rows):
        for c in range(cols):
            sfx = f"r{r}_c{c:02d}"
            out[(r, c)] = (bpy.data.objects[f"FlapTop_{sfx}"],
                           bpy.data.objects[f"FlapBot_{sfx}"],
                           bpy.data.objects[f"Rotor_{sfx}"])
    return rows, cols, out


def _fcurves(obj):
    """FCurve container across legacy (<4.4) and layered-action (5.x) APIs."""
    ad = obj.animation_data
    fcs = getattr(ad.action, "fcurves", None)
    if fcs is not None:
        return fcs
    strip = ad.action.layers[0].strips[0]
    return strip.channelbag(ad.action_slot, ensure=True).fcurves


def _key(obj, path, frame, interp="CONSTANT"):
    obj.keyframe_insert(data_path=path, frame=frame)
    fc = _fcurves(obj).find(path)
    if fc:
        fc.keyframe_points[-1].interpolation = interp


def _key_prop(obj, prop, value, frame):
    obj[prop] = int(value)
    _key(obj, f'["{prop}"]', frame)


def _key_rot(obj, value, frame, interp="LINEAR", easing="AUTO"):
    obj.rotation_euler.x = value
    obj.keyframe_insert(data_path="rotation_euler", index=0, frame=frame)
    fc = _fcurves(obj).find("rotation_euler", index=0)
    if fc:
        kp = fc.keyframe_points[-1]
        kp.interpolation = interp
        kp.easing = easing


def _key_hide(obj, hidden, frame):
    obj.hide_viewport = hidden
    obj.hide_render = hidden
    _key(obj, "hide_viewport", frame)
    _key(obj, "hide_render", frame)


def set_text(rows_text=None, grid=None):
    """Sets the board state WITHOUT animation (baseline for the next spell)."""
    rows, cols, cells = _cells()
    if grid is None:
        grid = charset.rows_to_indices(rows_text or [], rows, cols)
    for (r, c), (top, bot, rot) in cells.items():
        idx = int(grid[r][c])
        top["uv_index"] = idx
        bot["uv_index"] = idx
        rot["uv_front"] = idx
        rot["uv_back"] = idx
    bpy.context.view_layer.update()


def clear_animation():
    """Removes actions only - NEVER animation_data_clear(), that would
    delete the UV-warp drivers along with them."""
    _, _, cells = _cells()
    for top, bot, rot in cells.values():
        for ob in (top, bot, rot):
            ad = ob.animation_data
            if ad and ad.action:
                ad.action = None
        rot.hide_viewport = rot.hide_render = True
        rot.rotation_euler.x = REST


def spell(rows_text=None, grid=None, frame_start: int = 1,
          flip_frames: int = 4, bounce_frames: int = 4, fps: int = 60) -> dict:
    """Animates the board from its current state to the target text.
    All cells start together; each stops at its target glyph (cascade)."""
    rows, cols, cells = _cells()
    if grid is None:
        grid = charset.rows_to_indices(rows_text or [], rows, cols)

    sc = bpy.context.scene
    sc.render.fps = fps
    n_flaps = len(charset.FLAPS)
    max_end = frame_start

    for (r, c), (top, bot, rot) in cells.items():
        cur = int(top["uv_index"])
        target = int(grid[r][c])
        steps = (target - cur) % n_flaps
        if steps == 0:
            continue

        f = frame_start
        _key_hide(rot, False, f)
        for s in range(steps):
            k = (cur + s) % n_flaps
            nxt = (k + 1) % n_flaps
            # static top card already shows the next glyph (hidden behind the rotor)
            _key_prop(top, "uv_index", nxt, f)
            _key_prop(rot, "uv_front", k, f)
            _key_prop(rot, "uv_back", nxt, f)
            # interpolation acts from a key to the NEXT one: the acceleration of the
            # final fall belongs on the start key (gravity feel).
            if s == steps - 1:
                _key_rot(rot, REST, f, "QUAD", "EASE_IN")
            else:
                _key_rot(rot, REST, f, "LINEAR")
            _key_rot(rot, LAND, f + flip_frames, "BEZIER")
            # lower card changes underneath the landed rotor
            _key_prop(bot, "uv_index", nxt, f + flip_frames)
            f += flip_frames

        # bounce: the card rebounds briefly off the stop
        _key_rot(rot, LAND - math.radians(3.0), f + bounce_frames / 2, "BEZIER")
        _key_rot(rot, LAND, f + bounce_frames, "BEZIER")
        _key_hide(rot, True, f + bounce_frames)
        max_end = max(max_end, int(f + bounce_frames))

    sc.frame_start = max(1, frame_start - 10)
    sc.frame_end = max_end + 30
    return {"frame_end": max_end, "fps": fps}
