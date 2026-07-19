# Font-atlas bake: renders the 64 flap cards to a PNG (emission on black) in a
# temporary scene with an ortho camera. Runs inside the interactive instance.

import math
import os

import bpy

from . import charset

ATLAS_W = 2.048   # world extent of the atlas plane (x), 1 unit = 1000 px
ATLAS_H = 4.096
CELL_W = ATLAS_W / charset.ATLAS_COLS   # 0.256
CELL_H = ATLAS_H / charset.ATLAS_ROWS   # 0.512

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)

TARGET_CAP = 0.62 * CELL_H   # target cap height (62 % of the card height, as on the original)
CONDENSE = 0.62              # narrow, split-flap style
MAX_GLYPH_W = CELL_W * 0.80


def _cell_center(i: int):
    col = i % charset.ATLAS_COLS
    row = i // charset.ATLAS_COLS
    cx = -ATLAS_W / 2 + (col + 0.5) * CELL_W
    cz = ATLAS_H / 2 - (row + 0.5) * CELL_H
    return cx, cz


def _measure_world_z(ob):
    """(z_min, z_max) of the bounding box in world coordinates."""
    bpy.context.view_layer.update()
    from mathutils import Vector
    zs = [(ob.matrix_world @ Vector(c)).z for c in ob.bound_box]
    return min(zs), max(zs)


def _emission_mat(name: str, rgba):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = rgba
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def _set_engine(scene):
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        try:
            scene.render.engine = eng
            return eng
        except TypeError:
            continue
    return scene.render.engine


def build_atlas(params, out_path: str) -> dict:
    font_path = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)
    if font_path is None:
        raise RuntimeError("No font found (Liberation/DejaVu)")
    font = bpy.data.fonts.load(font_path, check_existing=True)

    old = bpy.data.scenes.get("SF_AtlasBake")
    if old:
        bpy.data.scenes.remove(old)
    sc = bpy.data.scenes.new("SF_AtlasBake")

    # Activate the bake scene: required so the depsgraph / bounding boxes of the
    # measurement objects are evaluated (and for rendering anyway).
    win = bpy.context.window
    prev_scene = win.scene if win else None
    if win:
        win.scene = sc

    world = bpy.data.worlds.new("SF_AtlasWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0, 0, 0, 1)
        bg.inputs[1].default_value = 0.0
    sc.world = world

    white = _emission_mat("SF_AtlasGlyph", (1, 1, 1, 1))
    trash_objs = []

    # Measure the font metrics instead of assuming: reference "X" fixes size + baseline.
    ref_cu = bpy.data.curves.new("SF_glyph_ref", "FONT")
    ref_cu.body = "X"
    ref_cu.font = font
    ref_cu.size = 1.0
    ref_cu.align_x = "CENTER"
    ref = bpy.data.objects.new("SF_glyph_ref", ref_cu)
    ref.rotation_euler = (math.radians(90), 0, 0)
    ref.scale = (CONDENSE, 1, 1)
    sc.collection.objects.link(ref)
    z0, z1 = _measure_world_z(ref)
    glyph_size = TARGET_CAP / (z1 - z0)          # size for the target cap height
    ref_cu.size = glyph_size
    z0, z1 = _measure_world_z(ref)
    center_off = (z0 + z1) / 2.0                 # cap centre relative to the baseline
    bpy.data.objects.remove(ref, do_unlink=True)
    bpy.data.curves.remove(ref_cu)

    # place glyphs + chips
    for i, flap in enumerate(charset.FLAPS):
        if flap == " ":
            continue
        cx, cz = _cell_center(i)
        if flap.startswith("chip:"):
            me = bpy.data.meshes.new(f"SF_chip_{i}")
            hw, hh = CELL_W / 2, CELL_H / 2
            me.from_pydata(
                [(-hw, 0, -hh), (hw, 0, -hh), (hw, 0, hh), (-hw, 0, hh)],
                [], [(0, 1, 2, 3)])
            me.update()
            mat = _emission_mat(f"SF_AtlasChip_{flap}",
                                charset.hex_to_linear(charset.CHIP_COLORS[flap]))
            me.materials.append(mat)
            ob = bpy.data.objects.new(f"SF_chip_{i}", me)
            ob.location = (cx, 0, cz)
            sc.collection.objects.link(ob)
            trash_objs.append(ob)
        else:
            cu = bpy.data.curves.new(f"SF_glyph_{i}", "FONT")
            cu.body = flap
            cu.font = font
            cu.size = glyph_size
            cu.align_x = "CENTER"
            cu.materials.append(white)
            ob = bpy.data.objects.new(f"SF_glyph_{i}", cu)
            # shared baseline: cap glyphs sit exactly centred on the split line
            ob.location = (cx, 0, cz - center_off)
            ob.rotation_euler = (math.radians(90), 0, 0)
            ob.scale = (CONDENSE, 1, 1)
            sc.collection.objects.link(ob)
            trash_objs.append(ob)

    # width fit for outliers (@, %, W ...)
    bpy.context.view_layer.update()
    for ob in trash_objs:
        if ob.type != "FONT":
            continue
        w = ob.dimensions.x
        if w > MAX_GLYPH_W and w > 0:
            ob.scale.x *= MAX_GLYPH_W / w

    # ortho camera exactly on the atlas plane
    cam_data = bpy.data.cameras.new("SF_AtlasCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ATLAS_H
    cam_data.sensor_fit = "VERTICAL"
    cam = bpy.data.objects.new("SF_AtlasCam", cam_data)
    cam.location = (0, -5, 0)
    cam.rotation_euler = (math.radians(90), 0, 0)
    sc.collection.objects.link(cam)
    sc.camera = cam

    engine = _set_engine(sc)
    if hasattr(sc, "eevee"):
        try:
            sc.eevee.taa_render_samples = 16
        except AttributeError:
            pass
    px_w, px_h = 2048, 4096
    sc.render.resolution_x = px_w
    sc.render.resolution_y = px_h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.filepath = out_path
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"

    # Suppress render metadata: Blender otherwise writes the .blend's absolute
    # path, hostname and timestamps into the PNG's tEXt chunks, which then also
    # end up embedded in the exported GLB.
    sc.render.use_stamp = False
    for flag in ("use_stamp_date", "use_stamp_time", "use_stamp_render_time",
                 "use_stamp_frame", "use_stamp_frame_range", "use_stamp_memory",
                 "use_stamp_hostname", "use_stamp_camera", "use_stamp_lens",
                 "use_stamp_scene", "use_stamp_marker", "use_stamp_filename",
                 "use_stamp_sequencer_strip", "use_stamp_note"):
        if hasattr(sc.render, flag):
            setattr(sc.render, flag, False)

    # render, then switch back to the previous scene
    try:
        bpy.ops.render.render(write_still=True)
    finally:
        if win and prev_scene:
            win.scene = prev_scene

    bpy.data.scenes.remove(sc)
    for blk in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                bpy.data.cameras, bpy.data.worlds):
        for it in list(blk):
            if it.name.startswith(("SF_Atlas", "SF_glyph_", "SF_chip_")) and it.users == 0:
                blk.remove(it)

    return {"engine": engine, "out": out_path, "px": [px_w, px_h]}
