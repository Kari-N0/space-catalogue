"""build_asset_pad.py — asset 001b: landing pad + berm on real terrain (draft).

bpy script (ML-free), run headless on Windows Blender:
    pipeline/blender/blender-win.sh -b --python pipeline/blender/build_asset_pad.py -- \
        --patch-exr <pad_patch.exr> --patch-meta <pad_patch.meta.json> \
        --kit <gn_kit_v001.blend> --out <pad_v001.blend>

Builds (SCENE-BIBLE.md §3 row 11: pad anatomy per the NTRS 2025 study):
  CTX_pad   pad_patch   — 500 m real-terrain patch (Site11 @ pad location),
                          leveled inside r26 m, blended out to r40 m
  AST_pad   pad_center  — r12 sintered dark center slab
            pad_ring    — r20 vitrified ring
            pad_apron   — r32 compacted apron
            pad_berm    — GN_regolith_berm r30, h2.5, corridor gap 40 deg on +Y
            pad_scatter — GN_surface_disturbance clods, ring 34..70 m

Asset frame: pad center = origin, ground = Z0; local +Y = corridor direction
(toward the habitat when placed in the scene). Berm/scatter/patch are
procedural-material objects (procedural_ok=1 — GN output has no UVs).

Importable: build_pad(patch_exr, patch_meta, kit_blend, out_path) -> None
"""

import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

FLAT_R = 26.0      # fully leveled inside this radius
BLEND_R = 40.0     # leveled..natural blend band ends here


def _mat(name, rgba, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = rgba
    b.inputs["Roughness"].default_value = rough
    return m


def _regolith_mat():
    m = bpy.data.materials.new("M_pad_regolith")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 1.0
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 8.0
    ramp = nt.nodes.new("ShaderNodeMix")
    ramp.data_type = "RGBA"
    ramp.inputs["A"].default_value = (0.10, 0.10, 0.105, 1)
    ramp.inputs["B"].default_value = (0.16, 0.155, 0.15, 1)
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Factor"])
    nt.links.new(ramp.outputs["Result"], b.inputs["Base Color"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.3
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def build_pad(patch_exr: str, patch_meta: str, kit_blend: str, out_path: str) -> None:
    with open(patch_meta) as fh:
        meta = json.load(fh)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"

    # bring in the kit generators
    for group in ("GN_regolith_berm", "GN_surface_disturbance"):
        bpy.ops.wm.append(directory=os.path.join(kit_blend, "NodeTree") + os.sep, filename=group)

    ast = bpy.data.collections.new("AST_pad")
    ctx = bpy.data.collections.new("CTX_pad")
    scene.collection.children.link(ast)
    scene.collection.children.link(ctx)

    def into(coll, ob):
        for c in ob.users_collection:
            c.objects.unlink(ob)
        coll.objects.link(ob)

    m_regolith = _regolith_mat()

    # ---- terrain patch: displace, evaluate, recenter, level the pad area ----
    size = meta["suggested_plane_size_m"]["x"]
    bpy.ops.mesh.primitive_plane_add(size=1.0)
    patch = bpy.context.object
    patch.scale = (size, meta["suggested_plane_size_m"]["y"], 1.0)
    bpy.ops.object.transform_apply(scale=True)
    sub = patch.modifiers.new("subdiv", "SUBSURF")
    sub.subdivision_type = "SIMPLE"
    sub.levels = sub.render_levels = 8
    img = bpy.data.images.load(patch_exr)
    img.colorspace_settings.name = "Non-Color"
    tex = bpy.data.textures.new("pad_patch_height", type="IMAGE")
    tex.image = img
    tex.extension = "EXTEND"
    disp = patch.modifiers.new("displace", "DISPLACE")
    disp.texture = tex
    disp.texture_coords = "UV"
    disp.strength = 1.0
    disp.mid_level = 0.0
    deps = bpy.context.evaluated_depsgraph_get()
    real = bpy.data.meshes.new_from_object(patch.evaluated_get(deps))
    old = patch.data
    patch.modifiers.clear()
    patch.data = real
    bpy.data.meshes.remove(old)
    patch.name = "pad_patch"
    patch["procedural_ok"] = 1

    # recenter: ground at pad center -> Z0
    z0 = min(v.co.z for v in real.vertices if v.co.xy.length < 6.0)
    for v in real.vertices:
        v.co.z -= z0
        r = v.co.xy.length
        if r < FLAT_R:
            v.co.z = 0.0
        elif r < BLEND_R:
            t = (r - FLAT_R) / (BLEND_R - FLAT_R)
            v.co.z *= t * t * (3 - 2 * t)  # smoothstep
    bpy.ops.object.shade_smooth()
    patch.data.materials.append(m_regolith)
    into(ctx, patch)

    # ---- pad slabs ----
    slabs = (
        ("pad_center", 12.0, 0.12, _mat("M_pad_sintered", (0.035, 0.04, 0.05, 1), 0.35)),
        ("pad_ring", 20.0, 0.10, _mat("M_pad_vitrified", (0.06, 0.065, 0.075, 1), 0.55)),
        ("pad_apron", 32.0, 0.05, _mat("M_pad_apron", (0.11, 0.11, 0.11, 1), 0.95)),
    )
    for name, radius, height, mat in slabs:
        bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=height, location=(0, 0, height / 2), vertices=96)
        ob = bpy.context.object
        ob.name = name
        ob.data.materials.append(mat)
        into(ast, ob)

    # ---- berm (GN) ----
    berm_mesh = bpy.data.meshes.new("pad_berm")
    berm = bpy.data.objects.new("pad_berm", berm_mesh)
    scene.collection.objects.link(berm)
    berm["procedural_ok"] = 1
    berm_mesh.materials.append(m_regolith)  # slot mirrors the GN Set Material (validator A007)
    mod = berm.modifiers.new("berm", "NODES")
    mod.node_group = bpy.data.node_groups["GN_regolith_berm"]
    mat_id = next(it.identifier for it in mod.node_group.interface.items_tree
                  if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.name == "Material")
    mod[mat_id] = m_regolith
    into(ast, berm)

    # ---- disturbance scatter on a patch-shaped host, ring 34..70 m ----
    scatter = bpy.data.objects.new("pad_scatter", real)
    scene.collection.objects.link(scatter)
    scatter["procedural_ok"] = 1
    smod = scatter.modifiers.new("disturbance", "NODES")
    smod.node_group = bpy.data.node_groups["GN_surface_disturbance"]
    ids = {it.name: it.identifier for it in smod.node_group.interface.items_tree
           if it.item_type == "SOCKET" and it.in_out == "INPUT"}
    smod[ids["Inner Radius"]] = 34.0
    smod[ids["Falloff Radius"]] = 70.0
    smod[ids["Density"]] = 0.15
    smod[ids["Material"]] = m_regolith
    # scatter rides natural terrain out to 70 m — site dressing, not the
    # linkable pad: lives in CTX (keeps AST bbox = pad+berm per asset_specs)
    into(ctx, scatter)

    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    print(f"PAD ASSET SAVED: {out_path} (patch {size:.0f} m, relief {meta['elevation_range_m']:.1f} m, "
          f"AST_pad objects: {len(ast.objects)})")


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--patch-exr", required=True)
    ap.add_argument("--patch-meta", required=True)
    ap.add_argument("--kit", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    build_pad(args.patch_exr, args.patch_meta, args.kit, args.out)


if __name__ == "__main__":
    main()
