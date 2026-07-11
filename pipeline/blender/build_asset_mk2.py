"""build_asset_mk2.py — asset 002: Blue Moon Mk2 crewed lander (draft, hero exterior).

bpy script (ML-free), run headless on Windows Blender:
    pipeline/blender/blender-win.sh -b --python pipeline/blender/build_asset_mk2.py -- \
        --kit <gn_kit_v003.blend> --out <mk2_v001.blend>

Per assets/mk2/BRIEF.md (gate-approved: 16.0 m datum, emissive windows, no
interior). Stack, ground up: 4 legs + pads / recessed 3x BE-7 engine section /
~5 m boxy crew cabin with EVA hatch, ladder, handrails, windows, RCS quads /
ribbed LOX midsection / LH2 barrel with 4 radiator panels + dome crown to
exactly Z=16.0 with flush docking hatch. Decals are flat placeholder discs.
Asset frame: pad-contact = Z0, origin at footprint center, +Y = ladder face.
Body dia 6.4 m ([UNCONFIRMED] within the 7 m New Glenn fairing); leg footprint
~10 m [UNCONFIRMED — render-derived]. Materials M_mk2_*; MLI areas use the
kit's GN_mli_wrap (procedural_ok).

Importable: build_mk2(kit_blend, out_path) -> None
"""

import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

R_BODY = 3.2
H_TOTAL = 16.0
CABIN_Z0, CABIN_Z1 = 1.6, 6.6
LOX_Z1 = 9.6
LH2_Z1 = 14.2  # dome crown continues to 16.0


def _mat(name, rgba, rough, metallic=0.0, emission=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = rgba
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    if emission:
        b.inputs["Emission Color"].default_value = emission[0]
        b.inputs["Emission Strength"].default_value = emission[1]
    return m


class Builder:
    def __init__(self, coll, mats):
        self.coll, self.mats = coll, mats

    def _finish(self, name, mat):
        ob = bpy.context.object
        ob.name = f"mk2_{name}"
        ob.data.materials.append(self.mats[mat])
        for c in ob.users_collection:
            c.objects.unlink(ob)
        self.coll.objects.link(ob)
        return ob

    def cyl(self, name, mat, r, depth, loc, rot=(0, 0, 0), verts=48):
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc,
                                            rotation=rot, vertices=verts)
        if r > 0.8:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
        return self._finish(name, mat)

    def cyl_between(self, name, mat, r, a, b, verts=16):
        a, b = Vector(a), Vector(b)
        d = b - a
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length,
                                            location=(a + b) / 2, vertices=verts)
        ob = self._finish(name, mat)
        ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        return ob

    def box(self, name, mat, size, loc, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
        ob = self._finish(name, mat)
        ob.scale = size
        bpy.ops.object.transform_apply(scale=True)
        return ob

    def cone(self, name, mat, r1, r2, depth, loc, rot=(0, 0, 0), verts=32):
        bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=r2, depth=depth,
                                        location=loc, rotation=rot, vertices=verts)
        return self._finish(name, mat)

    def sphere(self, name, mat, r, loc, scale=(1, 1, 1)):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=48, ring_count=24)
        ob = self._finish(name, mat)
        ob.scale = scale
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.shade_smooth()
        return ob


def build_mk2(kit_blend: str, out_path: str) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    bpy.ops.wm.append(directory=os.path.join(kit_blend, "NodeTree") + os.sep, filename="GN_mli_wrap")

    coll = bpy.data.collections.new("AST_mk2")
    scene.collection.children.link(coll)
    mats = {
        "hull": _mat("M_mk2_hull", (0.72, 0.73, 0.75, 1), 0.35, metallic=1.0),
        "cabin": _mat("M_mk2_cabin", (0.55, 0.56, 0.58, 1), 0.5, metallic=0.9),
        "mli": _mat("M_mk2_mli", (0.71, 0.58, 0.36, 1), 0.22, metallic=1.0),
        "radiator": _mat("M_mk2_radiator", (0.92, 0.92, 0.94, 1), 0.65),
        "engine": _mat("M_mk2_engine", (0.06, 0.06, 0.07, 1), 0.45, metallic=0.8),
        "window": _mat("M_mk2_window", (0.02, 0.02, 0.03, 1), 0.1,
                       emission=((1.0, 0.85, 0.6, 1), 15.0)),
        "decal_b": _mat("M_mk2_decal_blue", (0.02, 0.09, 0.35, 1), 0.6),
        "decal_w": _mat("M_mk2_decal_white", (0.9, 0.9, 0.9, 1), 0.6),
    }
    b = Builder(coll, mats)

    # ---- legs x4 (azimuths 45/135/225/315 — radiators own the cardinals) ----
    for i in range(4):
        az = math.radians(45 + 90 * i)
        out_dir = Vector((math.sin(az), math.cos(az), 0))
        pad_pos = out_dir * 4.6 + Vector((0, 0, 0.12))
        b.cyl(f"leg_pad_{i}", "hull", 0.45, 0.24, pad_pos, verts=24)
        b.cyl_between(f"leg_main_{i}", "hull", 0.14,
                      out_dir * (R_BODY * 0.92) + Vector((0, 0, 3.4)), pad_pos + Vector((0, 0, 0.1)))
        for s in (-1, 1):
            side = Vector((math.sin(az + s * 0.45), math.cos(az + s * 0.45), 0))
            b.cyl_between(f"leg_strut_{i}{'ab'[s > 0]}", "hull", 0.07,
                          side * (R_BODY * 0.9) + Vector((0, 0, 1.9)), pad_pos + Vector((0, 0, 0.1)))

    # ---- engine section: skirt + MLI recess + 3x BE-7 ----
    b.cyl("skirt", "hull", R_BODY * 1.02, 0.8, (0, 0, 2.0))
    mli_ring = b.cyl("skirt_mli", "mli", R_BODY * 0.98, 0.9, (0, 0, 1.15))
    mli_ring["procedural_ok"] = 1
    mod = mli_ring.modifiers.new("mli", "NODES")
    mod.node_group = bpy.data.node_groups["GN_mli_wrap"]
    ids = {it.name: it.identifier for it in mod.node_group.interface.items_tree
           if it.item_type == "SOCKET" and it.in_out == "INPUT"}
    mod[ids["Material"]] = mats["mli"]
    mod[ids["Amplitude"]] = 0.02
    for i in range(3):
        az = math.radians(120 * i + 60)
        pos = (math.sin(az) * 1.6, math.cos(az) * 1.6, 0.95)
        b.cone(f"engine_bell_{i}", "engine", 0.55, 0.18, 1.1, pos)

    # ---- crew cabin (~5 m): core + boxy modules + hatch + ladder + rails ----
    b.cyl("cabin", "cabin", R_BODY, CABIN_Z1 - CABIN_Z0, (0, 0, (CABIN_Z0 + CABIN_Z1) / 2), verts=64)
    for i in range(6):
        az = math.radians(60 * i + 30)  # 30..330 deg — leaves the +Y hatch face clear
        pos = (math.sin(az) * (R_BODY + 0.35), math.cos(az) * (R_BODY + 0.35), 3.4)
        b.box(f"cabin_module_{i}", "cabin", (1.6, 0.7, 2.6), pos, rot=(0, 0, -az))
    b.box("hatch", "cabin", (1.0, 0.12, 1.3), (0, R_BODY + 0.02, 3.6))
    b.box("hatch_frame", "hull", (1.25, 0.08, 1.55), (0, R_BODY + 0.0, 3.6))
    # ladder: rails + rungs from hatch sill to first step height
    for sx in (-0.25, 0.25):
        b.cyl_between("ladder_rail", "hull", 0.03, (sx, R_BODY + 0.28, 0.25), (sx, R_BODY + 0.28, 3.0), verts=12)
    z = 0.4
    while z <= 2.95:
        b.cyl("ladder_rung", "hull", 0.025, 0.5, (0, R_BODY + 0.28, z), rot=(0, math.pi / 2, 0), verts=12)
        z += 0.27
    for sx in (-0.7, 0.7):  # hatch-side handrails
        b.cyl_between("handrail", "hull", 0.03, (sx, R_BODY + 0.18, 2.9), (sx, R_BODY + 0.18, 4.4), verts=12)
    # windows: 3 upper +Y, 2 on -X (emissive, no interior per brief)
    for i, wx in enumerate((-0.9, 0.0, 0.9)):
        ang = wx / R_BODY
        b.box(f"window_y{i}", "window", (0.55, 0.06, 0.55),
              (math.sin(ang) * (R_BODY + 0.01), math.cos(ang) * (R_BODY + 0.01), 5.6), rot=(0, 0, -ang))
    for i, wz in enumerate((4.4, 5.6)):
        b.box(f"window_x{i}", "window", (0.06, 0.55, 0.55), (-(R_BODY + 0.01), 0, wz))
    # RCS quads at cabin shoulder
    for i in range(4):
        az = math.radians(90 * i + 45)
        pos = Vector((math.sin(az) * (R_BODY + 0.15), math.cos(az) * (R_BODY + 0.15), 6.3))
        b.box(f"rcs_{i}", "engine", (0.35, 0.35, 0.35), pos)
        for j, d in enumerate(((0.25, 0, 0), (-0.25, 0, 0), (0, 0, -0.25))):
            b.cone(f"rcs_{i}_n{j}", "engine", 0.02, 0.07, 0.14,
                   pos + Vector(d), rot=(0, math.pi / 2 if d[2] == 0 else 0, 0), verts=12)

    # ---- LOX midsection with vertical ribs ----
    b.cyl("lox", "hull", R_BODY - 0.2, LOX_Z1 - CABIN_Z1, (0, 0, (CABIN_Z1 + LOX_Z1) / 2), verts=64)
    for i in range(24):
        az = math.radians(15 * i)
        b.box(f"lox_rib_{i}", "hull", (0.09, 0.09, LOX_Z1 - CABIN_Z1 - 0.2),
              (math.sin(az) * (R_BODY - 0.08), math.cos(az) * (R_BODY - 0.08), (CABIN_Z1 + LOX_Z1) / 2),
              rot=(0, 0, -az))

    # ---- LH2 barrel + dome crown to exactly 16.0 + radiators + top hatch ----
    b.cyl("lh2", "hull", R_BODY, LH2_Z1 - LOX_Z1, (0, 0, (LOX_Z1 + LH2_Z1) / 2), verts=64)
    b.sphere("dome", "hull", 1.0, (0, 0, LH2_Z1), scale=(R_BODY, R_BODY, H_TOTAL - LH2_Z1))
    b.cyl("dock_hatch", "hull", 0.85, 0.06, (0, 0, H_TOTAL - 0.03), verts=32)
    for i in range(4):
        az = math.radians(90 * i)
        pos = (math.sin(az) * (R_BODY + 0.35), math.cos(az) * (R_BODY + 0.35), 12.0)
        b.box(f"radiator_{i}", "radiator", (2.9, 0.14, 4.2), pos, rot=(0, 0, -az))
        b.cyl_between(f"radiator_arm_{i}", "hull", 0.06,
                      (math.sin(az) * R_BODY, math.cos(az) * R_BODY, 12.0),
                      (math.sin(az) * (R_BODY + 0.35), math.cos(az) * (R_BODY + 0.35), 12.0), verts=12)

    # ---- comms + decal placeholders ----
    b.cyl_between("dish_boom", "hull", 0.05, (2.4, -1.2, 13.2), (3.0, -1.6, 13.8), verts=12)
    b.cone("dish", "radiator", 0.45, 0.06, 0.3, (3.15, -1.7, 13.95), rot=(math.radians(60), 0, math.radians(-30)))
    b.cyl_between("antenna_a", "hull", 0.02, (-1.8, 1.8, 14.6), (-2.1, 2.1, 15.6), verts=8)
    b.cyl("decal_meatball", "decal_b", 0.5, 0.02, (0, -(R_BODY + 0.005), 12.0), rot=(math.pi / 2, 0, 0), verts=32)
    b.cyl("decal_feather", "decal_w", 0.4, 0.02, ((R_BODY + 0.005), 0, 11.0), rot=(0, math.pi / 2, 0), verts=32)

    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    print(f"MK2 SAVED: {out_path} ({len(coll.objects)} objects)")


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--kit", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    build_mk2(args.kit, args.out)


if __name__ == "__main__":
    main()
