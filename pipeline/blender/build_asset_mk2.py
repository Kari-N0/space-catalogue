"""build_asset_mk2.py — asset 002: Blue Moon Mk2 crewed lander (remodel v2).

bpy script (ML-free), run headless on Windows Blender:
    pipeline/blender/blender-win.sh -b --python pipeline/blender/build_asset_mk2.py -- \
        --kit <gn_kit_v003.blend> --out <mk2_v002.blend>

Modeled to the official NASA/Blue Origin render
(ref/blue_moon_mk2_crewed/NASA_2_HLS_(cropped)_Blue_Moon_MK2.webp.png), 16.0 m
datum (gate-approved). Stack, ground up:
  gold-MLI base skirt over recessed 3x BE-7 / crew cabin with two canted
  emissive windows, circular EVA porthole, flag + name plates, downlights /
  exposed MLI tank lobes in a diagonal truss cage / flared upper shroud with
  recessed MLI trapezoid (meatball + feather decals) / segmented dome crown
  with blue ring band, twin dish antennas, top fixtures. Four tall gold
  MLI-wrapped legs attach at cabin-top level, wide stance; deployable stair
  gantry with platform + handrails on +Y (access face).
Proportions [UNCONFIRMED — render-derived]; height exact 16.0.

Importable: build_mk2(kit_blend, out_path) -> None
"""

import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

R_BODY = 3.2
H = 16.0
BASE_Z0, BASE_Z1 = 0.9, 1.9      # gold MLI base skirt
CAB_Z0, CAB_Z1 = 1.9, 5.4        # crew cabin
TANK_Z0, TANK_Z1 = 5.4, 7.8      # exposed tanks + truss cage
SHR_Z0, SHR_Z1 = 7.8, 12.2       # upper shroud (flared hem)
DOME_Z0 = 12.2                   # crown to 16.0
LEG_PAD_R = 5.3                  # stance radius [UNCONFIRMED]


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


class B:
    def __init__(self, coll, mats):
        self.coll, self.mats = coll, mats

    def _fin(self, name, mat, smooth=False):
        ob = bpy.context.object
        ob.name = f"mk2_{name}"
        ob.data.materials.append(self.mats[mat])
        if smooth:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
        for c in ob.users_collection:
            c.objects.unlink(ob)
        self.coll.objects.link(ob)
        return ob

    def cyl(self, name, mat, r, depth, loc, rot=(0, 0, 0), verts=48, smooth=None):
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, location=loc, rotation=rot, vertices=verts)
        return self._fin(name, mat, smooth if smooth is not None else r > 0.8)

    def cone(self, name, mat, r1, r2, depth, loc, rot=(0, 0, 0), verts=48, smooth=None):
        bpy.ops.mesh.primitive_cone_add(radius1=r1, radius2=r2, depth=depth, location=loc, rotation=rot, vertices=verts)
        return self._fin(name, mat, smooth if smooth is not None else r1 > 0.8)

    def between(self, name, mat, r, a, b, verts=12):
        a, b = Vector(a), Vector(b)
        d = b - a
        bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=d.length, location=(a + b) / 2, vertices=verts)
        ob = self._fin(name, mat)
        ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
        return ob

    def box(self, name, mat, size, loc, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
        ob = self._fin(name, mat)
        ob.scale = size
        bpy.ops.object.transform_apply(scale=True)
        return ob

    def sphere(self, name, mat, r, loc, scale=(1, 1, 1), smooth=True):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=48, ring_count=24)
        ob = self._fin(name, mat, smooth)
        ob.scale = scale
        bpy.ops.object.transform_apply(scale=True)
        return ob

    def torus(self, name, mat, major, minor, loc, smooth=True):
        bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, location=loc)
        return self._fin(name, mat, smooth)


def _mli(ob, mats, amplitude=0.035, scale=6.0):
    ob["procedural_ok"] = 1
    mod = ob.modifiers.new("mli", "NODES")
    mod.node_group = bpy.data.node_groups["GN_mli_wrap"]
    ids = {it.name: it.identifier for it in mod.node_group.interface.items_tree
           if it.item_type == "SOCKET" and it.in_out == "INPUT"}
    mod[ids["Material"]] = ob.data.materials[0]
    mod[ids["Amplitude"]] = amplitude
    mod[ids["Crinkle Scale"]] = scale


def build_mk2(kit_blend: str, out_path: str) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    bpy.ops.wm.append(directory=os.path.join(kit_blend, "NodeTree") + os.sep, filename="GN_mli_wrap")

    coll = bpy.data.collections.new("AST_mk2")
    scene.collection.children.link(coll)
    mats = {
        "hull": _mat("M_mk2_hull", (0.68, 0.69, 0.71, 1), 0.45, metallic=0.85),
        "shroud": _mat("M_mk2_shroud", (0.75, 0.76, 0.78, 1), 0.5, metallic=0.7),
        "mli_gold": _mat("M_mk2_mli_gold", (0.75, 0.55, 0.28, 1), 0.25, metallic=1.0),
        "mli_silver": _mat("M_mk2_mli_silver", (0.8, 0.8, 0.82, 1), 0.2, metallic=1.0),
        "truss": _mat("M_mk2_truss", (0.25, 0.25, 0.27, 1), 0.5, metallic=0.9),
        "engine": _mat("M_mk2_engine", (0.06, 0.06, 0.07, 1), 0.45, metallic=0.8),
        "window": _mat("M_mk2_window", (0.02, 0.02, 0.03, 1), 0.1, emission=((1.0, 0.8, 0.55, 1), 12.0)),
        "light": _mat("M_mk2_light", (1, 1, 1, 1), 0.3, emission=((1, 0.97, 0.9, 1), 40.0)),
        "band": _mat("M_mk2_band", (0.03, 0.07, 0.22, 1), 0.4),
        "decal_b": _mat("M_mk2_decal_blue", (0.02, 0.09, 0.35, 1), 0.6),
        "decal_w": _mat("M_mk2_decal_white", (0.9, 0.9, 0.9, 1), 0.6),
        "plate": _mat("M_mk2_plate", (0.18, 0.18, 0.19, 1), 0.7),
    }
    b = B(coll, mats)

    # ---- base: gold MLI skirt + recessed engines ----
    skirt = b.cyl("base_skirt", "mli_gold", R_BODY + 0.05, BASE_Z1 - BASE_Z0, (0, 0, (BASE_Z0 + BASE_Z1) / 2))
    _mli(skirt, mats, amplitude=0.05, scale=4.0)
    b.cyl("base_deck", "hull", R_BODY + 0.1, 0.12, (0, 0, BASE_Z1))
    for i in range(3):
        az = math.radians(120 * i + 60)
        b.cone(f"engine_bell_{i}", "engine", 0.5, 0.16, 0.9, (math.sin(az) * 1.5, math.cos(az) * 1.5, 0.75), smooth=True)

    # ---- crew cabin ----
    b.cyl("cabin", "hull", R_BODY, CAB_Z1 - CAB_Z0, (0, 0, (CAB_Z0 + CAB_Z1) / 2), verts=64)
    b.torus("cabin_hem", "hull", R_BODY, 0.08, (0, 0, CAB_Z0 + 0.05))
    # two large canted windows on +Y (access face), warm interiors
    for i, sx in enumerate((-0.75, 0.75)):
        ang = sx / R_BODY
        cant = math.radians(8) * (1 if sx > 0 else -1)
        b.box(f"window_{i}", "window", (1.0, 0.08, 1.35),
              (math.sin(ang) * (R_BODY + 0.02), math.cos(ang) * (R_BODY + 0.02), 3.9),
              rot=(0, cant, -ang))
        b.box(f"window_frame_{i}", "plate", (1.15, 0.06, 1.5),
              (math.sin(ang) * (R_BODY + 0.0), math.cos(ang) * (R_BODY + 0.0), 3.9),
              rot=(0, cant, -ang))
        b.box(f"downlight_{i}", "light", (0.25, 0.12, 0.08),
              (math.sin(ang) * (R_BODY + 0.08), math.cos(ang) * (R_BODY + 0.08), 4.8), rot=(0, 0, -ang))
    # circular EVA porthole hatch, left of the windows
    haz = math.radians(-42)
    hpos = Vector((math.sin(haz) * (R_BODY + 0.04), math.cos(haz) * (R_BODY + 0.04), 3.7))
    b.cyl("eva_hatch", "shroud", 0.78, 0.1, hpos, rot=(math.pi / 2, 0, -haz), verts=40, smooth=True)
    b.torus("eva_ring", "plate", 0.82, 0.06, hpos)
    bpy.data.objects["mk2_eva_ring"].rotation_euler = (math.pi / 2, 0, -haz)
    # flag + name plates right of windows
    faz = math.radians(38)
    b.box("plate_flag", "decal_w", (0.55, 0.03, 0.35),
          (math.sin(faz) * (R_BODY + 0.02), math.cos(faz) * (R_BODY + 0.02), 4.1), rot=(0, 0, -faz))
    b.box("plate_name", "plate", (0.6, 0.03, 0.25),
          (math.sin(faz) * (R_BODY + 0.02), math.cos(faz) * (R_BODY + 0.02), 3.5), rot=(0, 0, -faz))
    # panel seams
    for i in range(12):
        az = math.radians(30 * i + 15)
        b.box(f"cabin_seam_{i}", "plate", (0.03, 0.03, CAB_Z1 - CAB_Z0 - 0.3),
              (math.sin(az) * (R_BODY + 0.01), math.cos(az) * (R_BODY + 0.01), (CAB_Z0 + CAB_Z1) / 2), rot=(0, 0, -az))

    # ---- exposed tank lobes + truss cage ----
    for name, z, rr in (("tank_lobe_a", TANK_Z0 + 0.7, 2.75), ("tank_lobe_b", TANK_Z1 - 0.6, 2.6)):
        lobe = b.sphere(name, "mli_silver", 1.0, (0, 0, z), scale=(rr, rr, 0.95))
        _mli(lobe, mats, amplitude=0.06, scale=3.0)
    b.torus("tank_ring", "hull", R_BODY + 0.05, 0.07, (0, 0, (TANK_Z0 + TANK_Z1) / 2))
    n_bays = 12
    for i in range(n_bays):
        a0 = math.radians(360 / n_bays * i)
        a1 = math.radians(360 / n_bays * (i + 1))
        p_low0 = (math.sin(a0) * R_BODY, math.cos(a0) * R_BODY, TANK_Z0 + 0.05)
        p_low1 = (math.sin(a1) * R_BODY, math.cos(a1) * R_BODY, TANK_Z0 + 0.05)
        p_top0 = (math.sin(a0) * R_BODY, math.cos(a0) * R_BODY, TANK_Z1 - 0.05)
        p_top1 = (math.sin(a1) * R_BODY, math.cos(a1) * R_BODY, TANK_Z1 - 0.05)
        b.between(f"truss_x_{i}a", "truss", 0.035, p_low0, p_top1)
        b.between(f"truss_x_{i}b", "truss", 0.035, p_low1, p_top0)
        b.between(f"truss_post_{i}", "truss", 0.045, p_low0, p_top0)

    # ---- upper shroud (flared hem) + recessed MLI trapezoid + decals ----
    b.cone("shroud", "shroud", R_BODY + 0.25, R_BODY - 0.15, SHR_Z1 - SHR_Z0, (0, 0, (SHR_Z0 + SHR_Z1) / 2), verts=64)
    b.torus("shroud_hem", "shroud", R_BODY + 0.28, 0.09, (0, 0, SHR_Z0 + 0.05))
    # trapezoid recess on +Y: plane reshaped, solidified
    bpy.ops.mesh.primitive_plane_add(size=1.0)
    trap = bpy.context.object
    trap.name = "mk2_shroud_mli_panel"
    vs = trap.data.vertices
    vs[0].co = (-0.65, 0, SHR_Z0 + 0.5 - 10.0)   # local coords; object placed below
    vs[1].co = (0.65, 0, SHR_Z0 + 0.5 - 10.0)
    vs[2].co = (-1.35, 0, SHR_Z1 - 0.4 - 10.0)
    vs[3].co = (1.35, 0, SHR_Z1 - 0.4 - 10.0)
    trap.location = (0, R_BODY + 0.02, 10.0)
    sol = trap.modifiers.new("solid", "SOLIDIFY")
    sol.thickness = 0.07
    trap.data.materials.append(mats["mli_silver"])
    _mli(trap, mats, amplitude=0.03, scale=5.0)
    for c in trap.users_collection:
        c.objects.unlink(trap)
    coll.objects.link(trap)
    b.cyl("decal_meatball", "decal_b", 0.62, 0.03, (0, R_BODY + 0.12, 10.9), rot=(math.pi / 2, 0, 0), verts=40, smooth=False)
    b.cyl("decal_feather", "decal_w", 0.28, 0.03, (0, R_BODY + 0.10, 9.6), rot=(math.pi / 2, 0, 0), verts=32, smooth=False)

    # ---- dome crown: gores + blue band + dishes + fixtures ----
    # dome kept smooth — the render's gore seams are subtle lines, better done
    # as bump/texture in the art pass than as geometry
    b.sphere("dome", "shroud", 1.0, (0, 0, DOME_Z0), scale=(R_BODY + 0.15, R_BODY + 0.15, H - DOME_Z0))
    b.torus("dome_band", "band", R_BODY + 0.17, 0.1, (0, 0, DOME_Z0 + 0.15))
    b.cyl("dock_hatch", "hull", 0.8, 0.1, (0, 0, H - 0.05), verts=32)
    b.box("top_box", "hull", (0.7, 0.5, 0.4), (0.3, 0.2, H - 0.35))
    for i, s in enumerate((-1, 1)):  # twin dish antennas on masts at the crown rim
        base = Vector((s * (R_BODY - 0.4), -0.6, DOME_Z0 + 2.2))
        tip = base + Vector((s * 0.5, -0.3, 1.1))
        b.between(f"dish_mast_{i}", "truss", 0.04, base, tip)
        b.cone(f"dish_{i}", "decal_w", 0.42, 0.05, 0.25, tip + Vector((0, 0, 0.1)),
               rot=(math.radians(55), 0, s * math.radians(40)), verts=32, smooth=True)
    for i in range(4):  # crown downlights
        az = math.radians(90 * i + 45)
        b.box(f"crown_light_{i}", "light", (0.2, 0.1, 0.08),
              (math.sin(az) * (R_BODY - 0.15), math.cos(az) * (R_BODY - 0.15), DOME_Z0 + 1.1), rot=(0, 0, -az))

    # ---- legs: tall gold A-frames, attach at cabin top, wide stance ----
    for i in range(4):
        az = math.radians(45 + 90 * i)
        od = Vector((math.sin(az), math.cos(az), 0))
        pad = od * LEG_PAD_R + Vector((0, 0, 0.1))
        p = b.cyl(f"leg_pad_{i}", "mli_gold", 0.55, 0.2, pad, verts=24)
        main = b.between(f"leg_main_{i}", "mli_gold", 0.17, od * (R_BODY * 0.95) + Vector((0, 0, CAB_Z1)), pad + Vector((0, 0, 0.08)), verts=16)
        _mli(main, mats, amplitude=0.03, scale=8.0)
        for s in (-1, 1):
            side = Vector((math.sin(az + s * 0.4), math.cos(az + s * 0.4), 0))
            sec = b.between(f"leg_strut_{i}{'ab'[s > 0]}", "mli_gold", 0.09,
                            side * (R_BODY * 0.92) + Vector((0, 0, BASE_Z1 - 0.4)), pad + Vector((0, 0, 0.08)), verts=12)
            _mli(sec, mats, amplitude=0.02, scale=10.0)

    # ---- stair gantry on +Y: flight + platform + handrails ----
    plat_z, plat_y = 2.35, R_BODY + 0.55
    b.box("stair_platform", "plate", (1.3, 1.0, 0.06), (0, plat_y + 0.1, plat_z))
    foot = Vector((0, plat_y + 3.2, 0.05))
    top = Vector((0, plat_y + 0.6, plat_z))
    for sx in (-0.55, 0.55):
        b.between("stair_stringer", "plate", 0.05, (sx, foot.y, foot.z), (sx, top.y, top.z))
    n_steps = 8
    for k in range(n_steps):
        t = (k + 0.5) / n_steps
        pos = foot.lerp(top, t)
        b.box(f"stair_step_{k}", "plate", (1.05, 0.28, 0.04), pos)
    for sx in (-0.6, 0.6):
        b.between("stair_rail", "plate", 0.035, (sx, foot.y, foot.z + 0.95), (sx, top.y, top.z + 0.95))
        for t in (0.15, 0.5, 0.85):
            p = foot.lerp(top, t)
            b.between("stair_post", "plate", 0.025, (sx, p.y, p.z), (sx, p.y, p.z + 0.95))
        b.between("plat_rail", "plate", 0.035, (sx, plat_y - 0.35, plat_z + 0.95), (sx, plat_y + 0.55, plat_z + 0.95))
        b.between("plat_post", "plate", 0.025, (sx, plat_y + 0.5, plat_z), (sx, plat_y + 0.5, plat_z + 0.95))
    # cabin access door behind the platform
    b.box("stair_door", "plate", (0.95, 0.08, 1.4), (0, R_BODY + 0.01, plat_z + 0.85))

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
