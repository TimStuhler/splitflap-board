# Parametric board generator. Builds the enclosure, front plate, axle pins and,
# per cell, FlapTop/FlapBot/Rotor (sharing one card mesh) with UV-warp drivers.
#
# App contract:
#   - node names: SplitflapBoard, BoardPlate, BoardCase, AxlePins,
#     Cell_r{r}_c{cc}, FlapTop_..., FlapBot_..., Rotor_...
#   - card UVs sit on atlas cell 0; the displayed index comes from custom
#     properties uv_index (static) resp. uv_front/uv_back (rotor):
#     du = (i % 8)/8, dv = -(i // 8)/8
#   - rotor pivot = split axis (X rotation), rest -5deg, landing +175deg.

import json
import math

import bpy
from mathutils import Vector

from . import charset, materials
from .params import BoardParams

COLL = "Splitflap"
CELLS_COLL = "SF_Cells"

# UV region of atlas cell 0 (top left), with an edge inset against bleeding
_U0, _U1 = 0.0, 1.0 / charset.ATLAS_COLS
_V0, _V1 = 1.0 - 1.0 / charset.ATLAS_ROWS, 1.0
_VM = (_V0 + _V1) / 2.0          # split line (card centre)
_IU, _IV = 0.004, 0.002


class _Acc:
    """Collects faces with un-shared vertices (flat shading, simple UVs)."""

    def __init__(self):
        self.verts, self.faces, self.mats, self.uvs = [], [], [], []

    def quad(self, corners, mat=0, uv=None, want_normal=None):
        corners = [Vector(c) for c in corners]
        if want_normal is not None:
            n = (corners[1] - corners[0]).cross(corners[2] - corners[1])
            if n.dot(Vector(want_normal)) < 0:
                corners = list(reversed(corners))
                if uv:
                    uv = list(reversed(uv))
        b = len(self.verts)
        self.verts += corners
        self.faces.append((b, b + 1, b + 2, b + 3))
        self.mats.append(mat)
        self.uvs.append(uv)

    def tri(self, corners, mat=0, want_normal=None):
        corners = [Vector(c) for c in corners]
        if want_normal is not None:
            n = (corners[1] - corners[0]).cross(corners[2] - corners[1])
            if n.dot(Vector(want_normal)) < 0:
                corners = list(reversed(corners))
        b = len(self.verts)
        self.verts += corners
        self.faces.append((b, b + 1, b + 2))
        self.mats.append(mat)
        self.uvs.append(None)

    def to_mesh(self, name, mats):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in self.verts], [], self.faces)
        for m in mats:
            me.materials.append(m)
        for p, mi in zip(me.polygons, self.mats):
            p.material_index = mi
        layer = me.uv_layers.new(name="UVMap")
        for p, fuv in zip(me.polygons, self.uvs):
            if fuv:
                for k in range(p.loop_total):
                    layer.data[p.loop_start + k].uv = fuv[k]
        me.validate()
        me.update()
        return me


def _clear():
    coll = bpy.data.collections.get(COLL)
    if coll:
        for obj in list(coll.all_objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for ch in list(coll.children):
            bpy.data.collections.remove(ch)
    else:
        coll = bpy.data.collections.new(COLL)
        bpy.context.scene.collection.children.link(coll)
    for me in list(bpy.data.meshes):
        if me.users == 0 and me.name.startswith(("SF_", "Board", "AxlePins")):
            bpy.data.meshes.remove(me)
    cells = bpy.data.collections.new(CELLS_COLL)
    coll.children.link(cells)
    return coll, cells


def _link(coll, name, mesh):
    ob = bpy.data.objects.new(name, mesh)
    coll.objects.link(ob)
    return ob


def _build_plate(p: BoardParams, mats):
    a = _Acc()
    ch = p.chamfer
    x_lo, x_hi = -p.board_w / 2 + ch, p.board_w / 2 - ch
    z_lo, z_hi = -p.board_h / 2 + ch, p.board_h / 2 - ch

    # strip grid (avoids booleans): alternating web / opening
    xs = [x_lo]
    for c in range(p.cols):
        cx, _ = p.cell_center(0, c)
        xs += [cx - p.hole_w / 2, cx + p.hole_w / 2]
    xs.append(x_hi)
    zs = [z_lo]
    for r in range(p.rows - 1, -1, -1):
        _, cz = p.cell_center(r, 0)
        zs += [cz - p.hole_h / 2, cz + p.hole_h / 2]
    zs.append(z_hi)

    for ix in range(len(xs) - 1):
        for iz in range(len(zs) - 1):
            if ix % 2 == 1 and iz % 2 == 1:
                continue  # cell opening
            a.quad([(xs[ix], 0, zs[iz]), (xs[ix + 1], 0, zs[iz]),
                    (xs[ix + 1], 0, zs[iz + 1]), (xs[ix], 0, zs[iz + 1])],
                   mat=0, want_normal=(0, -1, 0))

    # per cell: opening walls, dark rear wall, flap-stack bulges
    for r in range(p.rows):
        for c in range(p.cols):
            cx, cz = p.cell_center(r, c)
            hl, hr = cx - p.hole_w / 2, cx + p.hole_w / 2
            hb, ht = cz - p.hole_h / 2, cz + p.hole_h / 2
            d = p.cavity
            a.quad([(hl, 0, hb), (hl, d, hb), (hl, d, ht), (hl, 0, ht)],
                   mat=0, want_normal=(1, 0, 0))
            a.quad([(hr, 0, hb), (hr, d, hb), (hr, d, ht), (hr, 0, ht)],
                   mat=0, want_normal=(-1, 0, 0))
            a.quad([(hl, 0, ht), (hr, 0, ht), (hr, d, ht), (hl, d, ht)],
                   mat=0, want_normal=(0, 0, -1))
            a.quad([(hl, 0, hb), (hr, 0, hb), (hr, d, hb), (hl, d, hb)],
                   mat=0, want_normal=(0, 0, 1))
            a.quad([(hl, d, hb), (hr, d, hb), (hr, d, ht), (hl, d, ht)],
                   mat=0, want_normal=(0, -1, 0))

            # flap-stack bulge: hint at the roll of cards (matte dark)
            bx0, bx1 = hl + 0.001, hr - 0.001
            yc = p.flap_y + 0.0055
            for sign in (1, -1):
                zc = (ht - 0.0055) if sign > 0 else (hb + 0.0055)
                pts = []
                for s in range(p.bulge_segs + 1):
                    ang = math.radians(10 + 90 * s / p.bulge_segs)
                    pts.append((yc - p.bulge_r * math.cos(ang),
                                zc + sign * p.bulge_r * math.sin(ang)))
                for s in range(p.bulge_segs):
                    (y0, zz0), (y1, zz1) = pts[s], pts[s + 1]
                    am = math.radians(10 + 90 * (s + 0.5) / p.bulge_segs)
                    n = (0, -math.cos(am), sign * math.sin(am))
                    a.quad([(bx0, y0, zz0), (bx1, y0, zz0),
                            (bx1, y1, zz1), (bx0, y1, zz1)],
                           mat=0, want_normal=n)

    return a.to_mesh("BoardPlate", [mats["plate"], mats["edge"]])


def _build_case(p: BoardParams, mats):
    a = _Acc()
    W, H, D, ch = p.board_w, p.board_h, p.case_depth, p.chamfer
    xi, zi = W / 2 - ch, H / 2 - ch

    # chamfer all round (plate -> outer edge), plus corner patches
    a.quad([(xi, 0, -zi), (W / 2, ch, -zi), (W / 2, ch, zi), (xi, 0, zi)],
           mat=0, want_normal=(1, -1, 0))
    a.quad([(-xi, 0, -zi), (-W / 2, ch, -zi), (-W / 2, ch, zi), (-xi, 0, zi)],
           mat=0, want_normal=(-1, -1, 0))
    a.quad([(-xi, 0, zi), (-xi, ch, H / 2), (xi, ch, H / 2), (xi, 0, zi)],
           mat=0, want_normal=(0, -1, 1))
    a.quad([(-xi, 0, -zi), (-xi, ch, -H / 2), (xi, ch, -H / 2), (xi, 0, -zi)],
           mat=0, want_normal=(0, -1, -1))
    for sx in (1, -1):
        for sz in (1, -1):
            a.quad([(sx * xi, 0, sz * zi), (sx * W / 2, ch, sz * zi),
                    (sx * W / 2, ch, sz * H / 2), (sx * xi, ch, sz * H / 2)],
                   mat=0, want_normal=(sx, -1, sz))

    # side walls + back panel
    a.quad([(W / 2, ch, -H / 2), (W / 2, D, -H / 2), (W / 2, D, H / 2), (W / 2, ch, H / 2)],
           mat=0, want_normal=(1, 0, 0))
    a.quad([(-W / 2, ch, -H / 2), (-W / 2, D, -H / 2), (-W / 2, D, H / 2), (-W / 2, ch, H / 2)],
           mat=0, want_normal=(-1, 0, 0))
    a.quad([(-W / 2, ch, H / 2), (-W / 2, D, H / 2), (W / 2, D, H / 2), (W / 2, ch, H / 2)],
           mat=0, want_normal=(0, 0, 1))
    a.quad([(-W / 2, ch, -H / 2), (-W / 2, D, -H / 2), (W / 2, D, -H / 2), (W / 2, ch, -H / 2)],
           mat=0, want_normal=(0, 0, -1))
    a.quad([(-W / 2, D, -H / 2), (-W / 2, D, H / 2), (W / 2, D, H / 2), (W / 2, D, -H / 2)],
           mat=0, want_normal=(0, 1, 0))
    return a.to_mesh("BoardCase", [mats["case"]])


def _build_pins(p: BoardParams, mats):
    a = _Acc()
    for r in range(p.rows):
        for c in range(p.cols):
            cx, cz = p.cell_center(r, c)
            for side in (-1, 1):
                x0 = cx + side * p.hole_w / 2
                x1 = x0 - side * p.pin_len
                ring0, ring1 = [], []
                for s in range(p.pin_segs):
                    ang = 2 * math.pi * s / p.pin_segs
                    y = p.flap_y + p.pin_r * math.cos(ang)
                    z = cz + p.pin_r * math.sin(ang)
                    ring0.append((x0, y, z))
                    ring1.append((x1, y, z))
                for s in range(p.pin_segs):
                    s2 = (s + 1) % p.pin_segs
                    mid_y = (ring0[s][1] + ring0[s2][1]) / 2 - p.flap_y
                    mid_z = (ring0[s][2] + ring0[s2][2]) / 2 - cz
                    a.quad([ring0[s], ring1[s], ring1[s2], ring0[s2]],
                           mat=0, want_normal=(0, mid_y, mid_z))
                    a.tri([(x1, p.flap_y, cz), ring1[s], ring1[s2]],
                          mat=0, want_normal=(-side, 0, 0))
    return a.to_mesh("AxlePins", [mats["pin"]])


def _build_card_mesh(p: BoardParams, mats, name="SF_Card"):
    """One half-card, origin = split axis. Front = upper half of the card,
    back = lower half (v-flipped) -> serves all three flap roles."""
    a = _Acc()
    hw = p.flap_w / 2
    z0, z1 = p.axis_gap / 2, p.axis_gap / 2 + p.card_h
    y1 = -p.card_lift            # back
    y0 = y1 - p.flap_t           # front
    u0, u1 = _U0 + _IU, _U1 - _IU
    # front (normal -y): upper half of the atlas cell
    a.quad([(-hw, y0, z0), (hw, y0, z0), (hw, y0, z1), (-hw, y0, z1)],
           mat=0,
           uv=[(u0, _VM), (u1, _VM), (u1, _V1 - _IV), (u0, _V1 - _IV)],
           want_normal=(0, -1, 0))
    # back (normal +y): lower half, v-flipped (reads upright after the 180deg flip)
    a.quad([(-hw, y1, z0), (hw, y1, z0), (hw, y1, z1), (-hw, y1, z1)],
           mat=0,
           uv=[(u0, _VM), (u1, _VM), (u1, _V0 + _IV), (u0, _V0 + _IV)],
           want_normal=(0, 1, 0))
    # edges (edge material, UVs irrelevant)
    a.quad([(-hw, y0, z0), (hw, y0, z0), (hw, y1, z0), (-hw, y1, z0)],
           mat=1, want_normal=(0, 0, -1))
    a.quad([(-hw, y0, z1), (hw, y0, z1), (hw, y1, z1), (-hw, y1, z1)],
           mat=1, want_normal=(0, 0, 1))
    a.quad([(-hw, y0, z0), (-hw, y0, z1), (-hw, y1, z1), (-hw, y1, z0)],
           mat=1, want_normal=(-1, 0, 0))
    a.quad([(hw, y0, z0), (hw, y0, z1), (hw, y1, z1), (hw, y1, z0)],
           mat=1, want_normal=(1, 0, 0))
    return a.to_mesh(name, [mats["face"], mats["edge"]])


def _add_uv_prop(obj, name, value):
    obj[name] = int(value)
    ui = obj.id_properties_ui(name)
    ui.update(min=0, max=len(charset.FLAPS) - 1)


def _drive_uvwarp(obj, mod_name, prop, vgroup=None):
    mod = obj.modifiers.new(mod_name, "UV_WARP")
    mod.uv_layer = "UVMap"
    if vgroup:
        mod.vertex_group = vgroup
    for axis, expr in ((0, "(i % 8) / 8"), (1, "-floor(i / 8) / 8")):
        fc = obj.driver_add(f'modifiers["{mod.name}"].offset', axis)
        drv = fc.driver
        drv.type = "SCRIPTED"
        var = drv.variables.new()
        var.name = "i"
        var.type = "SINGLE_PROP"
        var.targets[0].id = obj
        var.targets[0].data_path = f'["{prop}"]'
        drv.expression = expr
    return mod


def build(p: BoardParams = None, initial_rows=None) -> dict:
    p = p or BoardParams()
    if initial_rows is None:
        initial_rows = ["", "AND NOW THAT YOU", "DON'T HAVE TO BE",
                        "PERFECT, YOU CAN", "BE GOOD", ""]
    grid = charset.rows_to_indices(initial_rows, p.rows, p.cols)

    coll, cells_coll = _clear()
    from . import PROJECT_DIR
    mats = materials.get_materials(str(PROJECT_DIR / "assets/atlas/flap_atlas.png"))

    root = bpy.data.objects.new("SplitflapBoard", None)
    root.empty_display_size = 0.05
    coll.objects.link(root)
    root["sf_params"] = json.dumps(p.to_dict())
    root["sf_rows"], root["sf_cols"] = p.rows, p.cols

    for name, mesh in (("BoardPlate", _build_plate(p, mats)),
                       ("BoardCase", _build_case(p, mats)),
                       ("AxlePins", _build_pins(p, mats))):
        ob = _link(coll, name, mesh)
        ob.parent = root

    card = _build_card_mesh(p, mats, "SF_Card")
    card_rotor = _build_card_mesh(p, mats, "SF_CardRotor")

    tilt = math.radians(p.rest_tilt_deg)
    for r in range(p.rows):
        for c in range(p.cols):
            cx, cz = p.cell_center(r, c)
            suffix = f"r{r}_c{c:02d}"
            cell = bpy.data.objects.new(f"Cell_{suffix}", None)
            cell.empty_display_size = 0.004
            cell.location = (cx, p.flap_y, cz)
            cell.parent = root
            cells_coll.objects.link(cell)

            idx = grid[r][c]
            top = bpy.data.objects.new(f"FlapTop_{suffix}", card)
            top.rotation_euler = (-tilt, 0, 0)
            bot = bpy.data.objects.new(f"FlapBot_{suffix}", card)
            bot.rotation_euler = (math.pi - tilt, 0, 0)
            rot = bpy.data.objects.new(f"Rotor_{suffix}", card_rotor)
            rot.rotation_euler = (-tilt, 0, 0)
            rot.location = (0, -0.0003, 0)
            rot.hide_viewport = True
            rot.hide_render = True

            for ob in (top, bot, rot):
                ob.parent = cell
                cells_coll.objects.link(ob)

            _add_uv_prop(top, "uv_index", idx)
            _add_uv_prop(bot, "uv_index", idx)
            _add_uv_prop(rot, "uv_front", idx)
            _add_uv_prop(rot, "uv_back", idx)
            _drive_uvwarp(top, "SF_UV", "uv_index")
            _drive_uvwarp(bot, "SF_UV", "uv_index")

            # vertex groups live on the (shared) mesh: create them ONCE
            if rot.vertex_groups.get("vg_front") is None:
                vgf = rot.vertex_groups.new(name="vg_front")
                vgb = rot.vertex_groups.new(name="vg_back")
                vgf.add([0, 1, 2, 3], 1.0, "REPLACE")
                vgb.add([4, 5, 6, 7], 1.0, "REPLACE")
            _drive_uvwarp(rot, "SF_UVF", "uv_front", "vg_front")
            _drive_uvwarp(rot, "SF_UVB", "uv_back", "vg_back")

    bpy.context.view_layer.update()
    tris = sum(len(me.polygons) * 2 for me in
               (bpy.data.meshes["BoardPlate"], bpy.data.meshes["BoardCase"],
                bpy.data.meshes["AxlePins"]))
    return {
        "cells": p.rows * p.cols,
        "objects": len(coll.all_objects),
        "board_size_m": [round(p.board_w, 4), round(p.board_h, 4), p.case_depth],
        "static_tris_approx": tris,
        "card_tris": len(card.polygons) * 2,
    }
