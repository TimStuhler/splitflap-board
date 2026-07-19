# PBR materials for the board. The SF_* naming is part of the app contract.

import bpy

from .charset import hex_to_linear


def _principled(name: str, base_hex: str, rough: float, metallic: float = 0.0,
                spec: float = 0.5):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = hex_to_linear(base_hex)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    for key in ("Specular IOR Level", "Specular"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = spec
            break
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat, bsdf, nt


def get_materials(atlas_path: str) -> dict:
    """Creates/updates all materials; returns a dict keyed by short name."""
    # flap front/back: atlas texture
    face, bsdf, nt = _principled("SF_Flap_Face", "#101010", 0.42, spec=0.30)
    img = None
    try:
        img = bpy.data.images.load(atlas_path, check_existing=True)
    except RuntimeError:
        pass
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.location = (-420, 0)
    if img:
        tex.image = img
        img.colorspace_settings.name = "sRGB"
        tex.extension = "EXTEND"
        tex.interpolation = "Linear"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

    edge, _, _ = _principled("SF_Flap_Edge", "#080808", 0.55, spec=0.30)
    plate, _, _ = _principled("SF_Plate", "#030303", 0.90, spec=0.20)
    case, _, _ = _principled("SF_Case", "#0C0C0C", 0.50, spec=0.35)
    pin, _, _ = _principled("SF_Pin", "#1A1A1A", 0.45, metallic=0.9, spec=0.4)

    return {"face": face, "edge": edge, "plate": plate, "case": case, "pin": pin}
