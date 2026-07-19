# Look-dev: wall, camera, studio lighting - kept separate from the export (collection SF_LookDev).

import math

import bpy
from mathutils import Vector

from .charset import hex_to_linear
from .params import BoardParams

COLL = "SF_LookDev"


def _aim(obj, target=(0, 0, 0)):
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def setup(p: BoardParams = None):
    p = p or BoardParams()
    coll = bpy.data.collections.get(COLL)
    if coll:
        for ob in list(coll.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
    else:
        coll = bpy.data.collections.new(COLL)
        bpy.context.scene.collection.children.link(coll)

    # wall behind the board
    me = bpy.data.meshes.new("SF_Wall")
    w, h = 3.0, 2.2
    y = p.case_depth + 0.0006
    me.from_pydata([(-w / 2, y, -h / 2), (w / 2, y, -h / 2),
                    (w / 2, y, h / 2), (-w / 2, y, h / 2)], [], [(0, 1, 2, 3)])
    me.update()
    mat = bpy.data.materials.get("SF_WallMat") or bpy.data.materials.new("SF_WallMat")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = hex_to_linear("#E8E4DC")
        bsdf.inputs["Roughness"].default_value = 0.9
    me.materials.append(mat)
    wall = bpy.data.objects.new("SF_Wall", me)
    coll.objects.link(wall)

    # camera slightly off to the side
    cam_data = bpy.data.cameras.new("SF_Cam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("SF_Cam", cam_data)
    cam.location = (-0.38, -1.30, 0.0)
    coll.objects.link(cam)
    _aim(cam)
    bpy.context.scene.camera = cam

    # Key / Fill
    def area(name, size_x, size_y, loc, watt, color):
        data = bpy.data.lights.new(name, "AREA")
        data.shape = "RECTANGLE"
        data.size = size_x
        data.size_y = size_y
        data.energy = watt
        data.color = color
        ob = bpy.data.objects.new(name, data)
        ob.location = loc
        coll.objects.link(ob)
        _aim(ob)
        return ob

    area("SF_Key", 0.7, 0.45, (-0.7, -1.15, 0.65), 130, (1.0, 0.97, 0.92))
    area("SF_Fill", 0.6, 0.6, (0.9, -0.95, 0.05), 25, (0.92, 0.96, 1.0))

    # world + render settings
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.02, 0.02, 0.022, 1)
        bg.inputs[1].default_value = 1.0

    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue
    if hasattr(sc, "eevee"):
        try:
            sc.eevee.taa_render_samples = 64
        except AttributeError:
            pass
    sc.render.resolution_x = 1600
    sc.render.resolution_y = 1000
    sc.render.resolution_percentage = 100
    return {"camera": cam.name}
