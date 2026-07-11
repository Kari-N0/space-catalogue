"""build_asset_mk2.py — asset 002: Blue Moon Mk2 crewed lander (v3: detail + materials pass).

bpy script (ML-free), run headless on Windows Blender:
    pipeline/blender/blender-win.sh -b --python pipeline/blender/build_asset_mk2.py -- \
        --kit <gn_kit_v003.blend> --out <mk2_v003.blend>

References (ref/blue_moon_mk2_crewed/):
  - NASA_2_HLS official render (primary, courtesy Blue Origin)
  - Gemini 6-view turnaround sheet (Kari-supplied, AI-generated): switchback
    stair, tank-level catwalk, gold underside disc, two-tone legs, vertical
    BLUE ORIGIN lettering, blue crown pinstripes, warm painted-white finish.
    Where the AI sheet conflicts with NASA documentation, the document wins:
    3x BE-7 engines (NASA), not the sheet's 7 bells.
16.0 m datum (gate-approved); all proportions [UNCONFIRMED render-derived].

Materials are procedural PBR (noise-driven roughness/bump — no image
textures): warm matte paint, white + gold crinkle MLI, raw-aluminum access
structures, blue accents, warm emissive glass.

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
BASE_Z0, BASE_Z1 = 0.9, 1.9
CAB_Z0, CAB_Z1 = 1.9, 5.4
TANK_Z0, TANK_Z1 = 5.4, 7.8
SHR_Z0, SHR_Z1 = 7.8, 12.2
DOME_Z0 = 12.2
LEG_PAD_R = 5.3


# ---------------------------------------------------------------- materials
def _nodes(m):
    m.use_nodes = True
    return m.node_tree, m.node_tree.nodes["Principled BSDF"]


def _noise_bump(nt, bsdf, scale, strength, rough_base=None, rough_var=0.0):
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = scale
    noise.inputs["Detail"].default_value = 8.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    if rough_base is not None and rough_var > 0:
        ramp = nt.nodes.new("ShaderNodeMapRange")
        ramp.inputs["From Min"].default_value = 0.0
        ramp.inputs["From Max"].default_value = 1.0
        ramp.inputs["To Min"].default_value = rough_base - rough_var
        ramp.inputs["To Max"].default_value = rough_base + rough_var
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Value"])
        nt.links.new(ramp.outputs["Result"], bsdf.inputs["Roughness"])


def make_materials():
    mats = {}

    m = bpy.data.materials.new("M_mk2_paint")          # warm matte white paint
    nt, b = _nodes(m)
    b.inputs["Base Color"].default_value = (0.80, 0.78, 0.74, 1)
    b.inputs["Metallic"].default_value = 0.0
    _noise_bump(nt, b, scale=40.0, strength=0.03, rough_base=0.55, rough_var=0.08)
    mats["paint"] = m

    m = bpy.data.materials.new("M_mk2_mli_white")      # white-silver crinkle MLI
    nt, b = _nodes(m)
    b.inputs["Base Color"].default_value = (0.83, 0.83, 0.85, 1)
    b.inputs["Metallic"].default_value = 0.55
    _noise_bump(nt, b, scale=14.0, strength=0.35, rough_base=0.32, rough_var=0.12)
    mats["mli_white"] = m

    m = bpy.data.materials.new("M_mk2_mli_gold")       # gold kapton crinkle MLI
    nt, b = _nodes(m)
    b.inputs["Base Color"].default_value = (0.82, 0.58, 0.24, 1)
    b.inputs["Metallic"].default_value = 1.0
    _noise_bump(nt, b, scale=16.0, strength=0.4, rough_base=0.26, rough_var=0.1)
    mats["mli_gold"] = m

    m = bpy.data.materials.new("M_mk2_alu")            # raw aluminum (stairs, truss, rails)
    nt, b = _nodes(m)
    b.inputs["Base Color"].default_value = (0.75, 0.76, 0.78, 1)
    b.inputs["Metallic"].default_value = 1.0
    _noise_bump(nt, b, scale=60.0, strength=0.02, rough_base=0.45, rough_var=0.1)
    mats["alu"] = m

    m = bpy.data.materials.new("M_mk2_blue")           # Blue Origin accent blue
    _, b = _nodes(m)
    b.inputs["Base Color"].default_value = (0.03, 0.10, 0.42, 1)
    b.inputs["Roughness"].default_value = 0.5
    mats["blue"] = m

    m = bpy.data.materials.new("M_mk2_glass")          # warm-lit window glass
    _, b = _nodes(m)
    b.inputs["Base Color"].default_value = (0.02, 0.02, 0.03, 1)
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Metallic"].default_value = 0.4
    b.inputs["Emission Color"].default_value = (1.0, 0.82, 0.58, 1)
    b.inputs["Emission Strength"].default_value = 10.0
    mats["glass"] = m

    m = bpy.data.materials.new("M_mk2_light")
    _, b = _nodes(m)
    b.inputs["Emission Color"].default_value = (1, 0.97, 0.9, 1)
    b.inputs["Emission Strength"].default_value = 40.0
    mats["light"] = m

    m = bpy.data.materials.new("M_mk2_engine")         # engine bells, dark refractory
    nt, b = _nodes(m)
    b.inputs["Base Color"].default_value = (0.05, 0.05, 0.06, 1)
    b.inputs["Metallic"].default_value = 0.9
    _noise_bump(nt, b, scale=30.0, strength=0.08, rough_base=0.35, rough_var=0.1)
    mats["engine"] = m

    for name, rgba in (("decal_white", (0.88, 0.88, 0.88, 1)), ("decal_red", (0.6, 0.06, 0.08, 1)),
                       ("decal_blue", (0.04, 0.1, 0.38, 1)), ("plate", (0.2, 0.2, 0.21, 1))):
        m = bpy.data.materials.new(f"M_mk2_{name}")
        _, b = _nodes(m)
        b.inputs["Base Color"].default_value = rgba
        b.inputs["Roughness"].default_value = 0.6
        mats[name] = m
    return mats


# ---------------------------------------------------------------- builder
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

    def sphere(self, name, mat, r, loc, scale=(1, 1, 1)):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=loc, segments=48, ring_count=24)
        ob = self._fin(name, mat, smooth=True)
        ob.scale = scale
        bpy.ops.object.transform_apply(scale=True)
        return ob

    def torus(self, name, mat, major, minor, loc, rot=(0, 0, 0)):
        bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, location=loc, rotation=rot)
        return self._fin(name, mat, smooth=True)

    def text(self, name, mat, body, size, loc, rot, extrude=0.012):
        bpy.ops.object.text_add(location=loc, rotation=rot)
        ob = bpy.context.object
        ob.data.body = body
        ob.data.size = size
        ob.data.extrude = extrude
        ob.data.align_x = "CENTER"
        bpy.ops.object.convert(target="MESH")
        ob = bpy.context.object
        ob.name = f"mk2_{name}"
        ob["procedural_ok"] = 1  # converted text has no UVs
        ob.data.materials.append(self.mats[mat])
        for c in ob.users_collection:
            c.objects.unlink(ob)
        self.coll.objects.link(ob)
        return ob


def _mli(ob, amplitude=0.035, scale=6.0):
    ob["procedural_ok"] = 1
    mod = ob.modifiers.new("mli", "NODES")
    mod.node_group = bpy.data.node_groups["GN_mli_wrap"]
    ids = {it.name: it.identifier for it in mod.node_group.interface.items_tree
           if it.item_type == "SOCKET" and it.in_out == "INPUT"}
    mod[ids["Material"]] = ob.data.materials[0]
    mod[ids["Amplitude"]] = amplitude
    mod[ids["Crinkle Scale"]] = scale


def _flag(b, az, z):
    """US flag placeholder: white field, blue canton, 4 red stripe bars."""
    y = R_BODY + 0.02
    rot = (0, 0, -az)
    base = Vector((math.sin(az) * y, math.cos(az) * y, z))
    b.box("flag_field", "decal_white", (0.55, 0.03, 0.32), base, rot)
    b.box("flag_canton", "decal_blue", (0.22, 0.035, 0.16), base + Vector((math.cos(az) * -0.16, math.sin(az) * 0.16, 0.08)), rot)
    for k in range(4):
        b.box(f"flag_stripe_{k}", "decal_red", (0.55, 0.035, 0.025), base + Vector((0, 0, -0.12 + k * 0.075)), rot)


def build_mk2(kit_blend: str, out_path: str) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    bpy.ops.wm.append(directory=os.path.join(kit_blend, "NodeTree") + os.sep, filename="GN_mli_wrap")

    coll = bpy.data.collections.new("AST_mk2")
    scene.collection.children.link(coll)
    b = B(coll, make_materials())

    # ================= base: gold skirt, underside disc, engine bay, 3x BE-7
    skirt = b.cyl("base_skirt", "mli_gold", R_BODY + 0.05, BASE_Z1 - BASE_Z0, (0, 0, (BASE_Z0 + BASE_Z1) / 2))
    _mli(skirt, amplitude=0.05, scale=4.0)
    under = b.cyl("base_underdisc", "mli_gold", R_BODY - 0.3, 0.1, (0, 0, BASE_Z0))
    _mli(under, amplitude=0.04, scale=5.0)
    b.cyl("engine_bay", "plate", 1.9, 0.5, (0, 0, BASE_Z0 + 0.2), smooth=True)
    for i in range(3):  # NASA datum: 3x BE-7 (the AI sheet's 7 bells is wrong)
        az = math.radians(120 * i + 60)
        b.cone(f"engine_bell_{i}", "engine", 0.5, 0.16, 0.9, (math.sin(az) * 1.1, math.cos(az) * 1.1, 0.72), smooth=True)
        b.cyl(f"engine_neck_{i}", "engine", 0.14, 0.3, (math.sin(az) * 1.1, math.cos(az) * 1.1, 1.28), verts=16)

    # ================= crew cabin
    b.cyl("cabin", "paint", R_BODY, CAB_Z1 - CAB_Z0, (0, 0, (CAB_Z0 + CAB_Z1) / 2), verts=96)
    b.torus("cabin_hem", "paint", R_BODY, 0.07, (0, 0, CAB_Z0 + 0.05))
    b.torus("cabin_crown_ring", "paint", R_BODY, 0.06, (0, 0, CAB_Z1 - 0.06))
    for i, sx in enumerate((-0.75, 0.75)):           # canted windows + frames + downlights
        ang = sx / R_BODY
        cant = math.radians(8) * (1 if sx > 0 else -1)
        b.box(f"window_frame_{i}", "plate", (1.15, 0.07, 1.5),
              (math.sin(ang) * R_BODY, math.cos(ang) * R_BODY, 3.9), rot=(0, cant, -ang))
        b.box(f"window_{i}", "glass", (1.0, 0.09, 1.35),
              (math.sin(ang) * (R_BODY + 0.02), math.cos(ang) * (R_BODY + 0.02), 3.9), rot=(0, cant, -ang))
        b.box(f"downlight_{i}", "light", (0.25, 0.12, 0.08),
              (math.sin(ang) * (R_BODY + 0.08), math.cos(ang) * (R_BODY + 0.08), 4.8), rot=(0, 0, -ang))
    haz = math.radians(-42)                          # circular EVA porthole
    hpos = Vector((math.sin(haz) * (R_BODY + 0.04), math.cos(haz) * (R_BODY + 0.04), 3.7))
    b.cyl("eva_hatch", "paint", 0.78, 0.12, hpos, rot=(math.pi / 2, 0, -haz), verts=40, smooth=True)
    ring = b.torus("eva_ring", "alu", 0.82, 0.05, hpos)
    ring.rotation_euler = (math.pi / 2, 0, -haz)
    b.cyl("eva_port", "glass", 0.22, 0.14, hpos + Vector((math.sin(haz) * 0.03, math.cos(haz) * 0.03, 0)),
          rot=(math.pi / 2, 0, -haz), verts=24, smooth=True)
    faz = math.radians(38)                           # flag + UNITED STATES
    _flag(b, faz, 4.15)
    b.text("text_us", "plate", "UNITED\nSTATES", 0.28,
           (math.sin(faz) * (R_BODY + 0.03), math.cos(faz) * (R_BODY + 0.03), 3.45),
           (math.pi / 2, 0, math.pi - faz))
    for i in range(12):                              # panel seams
        az = math.radians(30 * i + 15)
        b.box(f"cabin_seam_{i}", "plate", (0.02, 0.02, CAB_Z1 - CAB_Z0 - 0.35),
              (math.sin(az) * (R_BODY + 0.005), math.cos(az) * (R_BODY + 0.005), (CAB_Z0 + CAB_Z1) / 2), rot=(0, 0, -az))
    for i in range(3):                               # utility boxes + conduit greebles
        az = math.radians(150 + 40 * i)
        b.box(f"util_box_{i}", "paint", (0.5, 0.3, 0.6 + 0.15 * i),
              (math.sin(az) * (R_BODY + 0.18), math.cos(az) * (R_BODY + 0.18), 2.8), rot=(0, 0, -az))
        b.between(f"util_pipe_{i}", "alu", 0.035,
                  (math.sin(az) * (R_BODY + 0.1), math.cos(az) * (R_BODY + 0.1), 2.2),
                  (math.sin(az) * (R_BODY + 0.1), math.cos(az) * (R_BODY + 0.1), CAB_Z1 - 0.3))
    b.between("whip_antenna", "alu", 0.015, (0.6, -R_BODY - 0.1, CAB_Z1), (0.75, -R_BODY - 0.35, CAB_Z1 + 1.6))

    # ================= tank lobes + truss cage + catwalk
    for name, z, rr in (("tank_lobe_a", TANK_Z0 + 0.7, 2.75), ("tank_lobe_b", TANK_Z1 - 0.6, 2.6)):
        lobe = b.sphere(name, "mli_white", 1.0, (0, 0, z), scale=(rr, rr, 0.95))
        _mli(lobe, amplitude=0.06, scale=3.0)
    b.torus("tank_ring", "paint", R_BODY + 0.05, 0.07, (0, 0, (TANK_Z0 + TANK_Z1) / 2))
    n_bays = 12
    for i in range(n_bays):
        a0 = math.radians(360 / n_bays * i)
        a1 = math.radians(360 / n_bays * (i + 1))
        lo0 = (math.sin(a0) * R_BODY, math.cos(a0) * R_BODY, TANK_Z0 + 0.05)
        lo1 = (math.sin(a1) * R_BODY, math.cos(a1) * R_BODY, TANK_Z0 + 0.05)
        hi0 = (math.sin(a0) * R_BODY, math.cos(a0) * R_BODY, TANK_Z1 - 0.05)
        hi1 = (math.sin(a1) * R_BODY, math.cos(a1) * R_BODY, TANK_Z1 - 0.05)
        b.between(f"truss_x_{i}a", "alu", 0.03, lo0, hi1)
        b.between(f"truss_x_{i}b", "alu", 0.03, lo1, hi0)
        b.between(f"truss_post_{i}", "alu", 0.04, lo0, hi0)
    # railed catwalk at tank-ring level, -X side (per the 6-view sheet)
    cw = Vector((-(R_BODY + 0.7), 0, TANK_Z0 + 0.1))
    b.box("catwalk_deck", "alu", (1.1, 1.6, 0.05), cw)
    for sy in (-0.75, 0.75):
        b.between("catwalk_post", "alu", 0.025, (cw.x - 0.5, sy, cw.z), (cw.x - 0.5, sy, cw.z + 1.0))
        b.between("catwalk_rail", "alu", 0.03, (cw.x - 0.5, -0.75, cw.z + 1.0), (cw.x - 0.5, 0.75, cw.z + 1.0))
    for sy in (-0.78, 0.78):
        b.between("catwalk_siderail", "alu", 0.03, (cw.x - 0.5, sy, cw.z + 1.0), (cw.x + 0.55, sy, cw.z + 1.0))
        b.between("catwalk_sidepost", "alu", 0.025, (cw.x + 0.5, sy, cw.z), (cw.x + 0.5, sy, cw.z + 1.0))

    # ================= shroud + MLI trapezoid + decals + lettering
    b.cone("shroud", "paint", R_BODY + 0.25, R_BODY - 0.15, SHR_Z1 - SHR_Z0, (0, 0, (SHR_Z0 + SHR_Z1) / 2), verts=96)
    b.torus("shroud_hem", "paint", R_BODY + 0.28, 0.09, (0, 0, SHR_Z0 + 0.05))
    for i in range(16):                              # vertical shroud seams
        az = math.radians(22.5 * i + 11)
        r_mid = R_BODY + 0.07
        b.box(f"shroud_seam_{i}", "plate", (0.015, 0.015, SHR_Z1 - SHR_Z0 - 0.5),
              (math.sin(az) * r_mid, math.cos(az) * r_mid, (SHR_Z0 + SHR_Z1) / 2), rot=(math.radians(-5.2), 0, -az))
    bpy.ops.mesh.primitive_plane_add(size=1.0)       # recessed MLI trapezoid, +Y face
    trap = bpy.context.object
    trap.name = "mk2_shroud_mli_panel"
    vs = trap.data.vertices
    vs[0].co, vs[1].co = (-0.65, 0, -1.7), (0.65, 0, -1.7)
    vs[2].co, vs[3].co = (-1.35, 0, 1.8), (1.35, 0, 1.8)
    trap.location = (0, R_BODY + 0.02, 10.0)
    trap.modifiers.new("solid", "SOLIDIFY").thickness = 0.07
    trap.data.materials.append(b.mats["mli_white"])
    _mli(trap, amplitude=0.03, scale=5.0)
    for c in trap.users_collection:
        c.objects.unlink(trap)
    coll.objects.link(trap)
    b.cyl("decal_meatball", "decal_blue", 0.62, 0.03, (0, R_BODY + 0.12, 10.9), rot=(math.pi / 2, 0, 0), verts=40, smooth=False)
    b.cyl("decal_feather", "decal_white", 0.28, 0.03, (0, R_BODY + 0.10, 9.6), rot=(math.pi / 2, 0, 0), verts=32, smooth=False)
    for az_deg in (90, 200):                         # vertical BLUE ORIGIN lettering
        az = math.radians(az_deg)
        b.text(f"text_bo_{az_deg}", "blue", "BLUE ORIGIN", 0.42,
               (math.sin(az) * (R_BODY + 0.16), math.cos(az) * (R_BODY + 0.16), 10.0),
               (math.pi / 2, math.radians(-90), math.pi - az))

    # ================= dome crown: pinstripes, dock, dishes, fixtures, RCS
    b.sphere("dome", "mli_white", 1.0, (0, 0, DOME_Z0), scale=(R_BODY + 0.15, R_BODY + 0.15, H - DOME_Z0))
    _mli(bpy.data.objects["mk2_dome"], amplitude=0.02, scale=7.0)
    b.torus("dome_band", "blue", R_BODY + 0.16, 0.06, (0, 0, DOME_Z0 + 0.15))
    b.torus("dome_pinstripe", "blue", 1.55, 0.02, (0, 0, H - 0.55))
    b.cyl("dock_ring", "alu", 0.95, 0.22, (0, 0, H - 0.11), verts=48, smooth=True)
    b.cyl("dock_hatch", "paint", 0.78, 0.26, (0, 0, H - 0.09), verts=48, smooth=True)
    for i in range(4):
        az = math.radians(90 * i + 45)
        b.box(f"dock_clamp_{i}", "alu", (0.16, 0.1, 0.12), (math.sin(az) * 0.92, math.cos(az) * 0.92, H - 0.06))
    for i, s in enumerate((-1, 1)):                  # twin dishes
        base = Vector((s * (R_BODY - 0.55), -0.75, DOME_Z0 + 2.15))
        tip = base + Vector((s * 0.45, -0.25, 0.9))
        b.between(f"dish_mast_{i}", "alu", 0.035, base, tip)
        b.cone(f"dish_{i}", "decal_white", 0.4, 0.04, 0.22, tip + Vector((0, 0, 0.08)),
               rot=(math.radians(55), 0, s * math.radians(40)), verts=32, smooth=True)
    for i in range(4):                               # crown downlights + boxes + RCS
        az = math.radians(90 * i + 45)
        b.box(f"crown_light_{i}", "light", (0.2, 0.1, 0.08),
              (math.sin(az) * (R_BODY - 0.2), math.cos(az) * (R_BODY - 0.2), DOME_Z0 + 1.15), rot=(0, 0, -az))
        bx = math.radians(90 * i)
        b.box(f"crown_box_{i}", "paint", (0.35, 0.3, 0.25),
              (math.sin(bx) * (R_BODY - 0.9), math.cos(bx) * (R_BODY - 0.9), DOME_Z0 + 2.6), rot=(0, 0, -bx))
        rc = Vector((math.sin(bx) * (R_BODY - 0.35), math.cos(bx) * (R_BODY - 0.35), DOME_Z0 + 1.7))
        b.box(f"rcs_body_{i}", "plate", (0.28, 0.28, 0.28), rc, rot=(0, 0, -bx))
        for j, d in enumerate(((0.2, 0, 0.08), (-0.2, 0, 0.08), (0, 0.2, 0.08))):
            b.cone(f"rcs_{i}_n{j}", "engine", 0.018, 0.06, 0.12, rc + Vector(d), rot=(0, math.radians(100), -bx), verts=12)

    # ================= legs: two-tone, wide stance
    for i in range(4):
        az = math.radians(45 + 90 * i)
        od = Vector((math.sin(az), math.cos(az), 0))
        pad = od * LEG_PAD_R + Vector((0, 0, 0.1))
        b.cone(f"leg_pad_{i}", "mli_gold", 0.6, 0.42, 0.22, pad, verts=24, smooth=True)
        attach = od * (R_BODY * 0.95) + Vector((0, 0, CAB_Z1))
        mid = attach.lerp(pad + Vector((0, 0, 0.1)), 0.55)
        b.between(f"leg_upper_{i}", "paint", 0.17, attach, mid, verts=16)       # white upper
        lower = b.between(f"leg_lower_{i}", "mli_gold", 0.15, mid, pad + Vector((0, 0, 0.08)), verts=16)
        _mli(lower, amplitude=0.025, scale=9.0)
        for s in (-1, 1):
            side = Vector((math.sin(az + s * 0.4), math.cos(az + s * 0.4), 0))
            sec = b.between(f"leg_strut_{i}{'ab'[s > 0]}", "mli_gold", 0.08,
                            side * (R_BODY * 0.92) + Vector((0, 0, BASE_Z1 - 0.4)), pad + Vector((0, 0, 0.08)), verts=12)
            _mli(sec, amplitude=0.02, scale=10.0)
        b.between(f"leg_xlink_{i}", "alu", 0.04, mid, od * (R_BODY * 0.95) + Vector((0, 0, BASE_Z1)))

    # ================= switchback stair gantry, +Y access face
    door_z = 2.35
    p2 = Vector((0, R_BODY + 0.55, door_z))          # top platform at the door
    p1 = Vector((1.7, R_BODY + 1.9, door_z / 2))     # mid platform, offset sideways
    f2_foot = p1 + Vector((0, 0, 0.0))
    f1_foot = Vector((1.7, R_BODY + 3.6, 0.05))      # ground end of lower flight

    def flight(tag, a, bb, width=1.0):
        for sx in (-width / 2, width / 2):
            b.between(f"stair_stringer_{tag}", "alu", 0.045,
                      (a.x + sx, a.y, a.z), (bb.x + sx, bb.y, bb.z))
        n = 7
        for k in range(n):
            t = (k + 0.5) / n
            pos = a.lerp(bb, t)
            b.box(f"stair_step_{tag}{k}", "alu", (width, 0.26, 0.035), pos)
        for sx in (-width / 2 - 0.04, width / 2 + 0.04):
            b.between(f"stair_rail_{tag}", "alu", 0.03,
                      (a.x + sx, a.y, a.z + 0.95), (bb.x + sx, bb.y, bb.z + 0.95))
            for t in (0.2, 0.5, 0.8):
                p = a.lerp(bb, t)
                b.between(f"stair_post_{tag}", "alu", 0.022, (p.x + sx, p.y, p.z), (p.x + sx, p.y, p.z + 0.95))

    flight("f1", f1_foot, p1)                        # ground -> mid platform
    b.box("stair_plat1", "alu", (1.2, 1.1, 0.05), p1 + Vector((0, -0.4, 0)))
    flight("f2", p1 + Vector((0, -0.9, 0)), p2 + Vector((0.9, 0.35, 0)))  # mid -> door level
    b.box("stair_plat2", "alu", (1.4, 1.0, 0.05), p2 + Vector((0, 0.1, 0)))
    for corner in ((-0.65, -0.35), (0.65, -0.35), (-0.65, 0.5), (0.65, 0.5)):
        b.between("plat2_post", "alu", 0.022,
                  (p2.x + corner[0], p2.y + corner[1], p2.z), (p2.x + corner[0], p2.y + corner[1], p2.z + 0.95))
    for pair in (((-0.65, -0.35), (-0.65, 0.5)), ((0.65, -0.35), (0.65, 0.5)), ((-0.65, 0.5), (0.65, 0.5))):
        (x0, y0), (x1, y1) = pair
        b.between("plat2_rail", "alu", 0.03,
                  (p2.x + x0, p2.y + y0, p2.z + 0.95), (p2.x + x1, p2.y + y1, p2.z + 0.95))
    b.box("stair_door", "plate", (0.95, 0.08, 1.4), (0, R_BODY + 0.01, door_z + 0.85))
    b.box("door_light", "light", (0.3, 0.1, 0.07), (0, R_BODY + 0.1, door_z + 1.7))

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
