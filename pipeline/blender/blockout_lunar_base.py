"""blockout_lunar_base.py — build the lunar-base layout blockout on audition terrain.

bpy script (ML-free), run headless on Windows Blender:
    pipeline/blender/blender-win.sh -b --python pipeline/blender/blockout_lunar_base.py -- \
        --terrain-blend <terrain_site11_v001.blend> --layout <site11.layout.json> \
        --out <blockout_site11_v001.blend> [--render-dir /mnt/d/renders/lunar-base/blockout]

Adds a "Blockout" collection of true-dimension primitives (SCENE-BIBLE.md §3
element table; proxies only — real modeling comes later), three cameras
(hero / top-down ortho / eye level), sun at the provisional hero azimuth
(D7 open), and optionally renders one frame per camera.

Importable API: build_blockout(terrain_blend, layout_json, out_blend, render_dir=None)
"""

import argparse
import json
import math
import sys

import bpy
from mathutils import Vector

HERO_SUN_AZ_DEG = 135.0  # provisional — fully lit in the hero-cam 8-az sweep; D7 decides
GRAY = (0.45, 0.45, 0.45, 1.0)


def _mat(name, rgba, roughness=0.9):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = rgba
    b.inputs["Roughness"].default_value = roughness
    return m


def _add(coll, name, mesh_op, loc, mat, **kw):
    mesh_op(location=loc, **kw)
    ob = bpy.context.object
    ob.name = f"BLK_{name}"
    ob.data.materials.append(mat)
    for c in ob.users_collection:
        c.objects.unlink(ob)
    coll.objects.link(ob)
    return ob


def build_blockout(terrain_blend: str, layout_json: str, out_blend: str, render_dir: str | None = None) -> None:
    with open(layout_json) as fh:
        lay = json.load(fh)
    el = {k: Vector(v["local_m"]) for k, v in lay["elements"].items()}

    bpy.ops.wm.open_mainfile(filepath=terrain_blend)
    scene = bpy.context.scene
    coll = bpy.data.collections.new("Blockout")
    scene.collection.children.link(coll)

    hw = _mat("blk_hardware", GRAY)
    pad_m = _mat("blk_pad_sintered", (0.06, 0.06, 0.07, 1.0), 0.35)
    berm_m = _mat("blk_berm", (0.13, 0.13, 0.13, 1.0))
    suit_m = _mat("blk_astronaut", (0.9, 0.9, 0.9, 1.0))
    cyl = bpy.ops.mesh.primitive_cylinder_add
    box = bpy.ops.mesh.primitive_cube_add
    cone = bpy.ops.mesh.primitive_cone_add

    def at(v, dz):
        return (v.x, v.y, v.z + dz)

    # FSH: 4 dia x 4 metallic base + 6.5 dia x 6 inflatable upper (~10 m total)
    _add(coll, "fsh_base", cyl, at(el["fsh_habitat"], 2.0), hw, radius=2.0, depth=4.0)
    _add(coll, "fsh_upper", cyl, at(el["fsh_habitat"], 7.0), hw, radius=3.25, depth=6.0)
    # rovers (Cruiser 6.0x5.2x3.8, Pegasus ~4x2.3x1.5 [UNCONFIRMED], CLV-1 ~4x2.3x2.6)
    for name, dims in (("lunar_cruiser", (6.0, 5.2, 3.8)), ("ltv_pegasus", (4.0, 2.3, 1.5)), ("ltv_clv1", (4.0, 2.3, 2.6))):
        ob = _add(coll, name, box, at(el[name], dims[2] / 2), hw, size=1.0)
        ob.scale = dims
    # ISRU vignette: drill mast + reactor drum
    _add(coll, "isru_drill", cyl, at(el["isru_vignette"], 1.0), hw, radius=0.15, depth=2.0)
    _add(coll, "isru_reactor", cyl, at(el["isru_vignette"] + Vector((3, 0, 0)), 1.0), hw, radius=0.75, depth=2.0)
    # VSAT: 10 m masts + vertical blanket (baseline class, bible §3 row 7)
    for v in ("vsat_a", "vsat_b"):
        _add(coll, f"{v}_mast", cyl, at(el[v], 5.0), hw, radius=0.2, depth=10.0)
        blanket = _add(coll, f"{v}_blanket", box, at(el[v], 6.0), hw, size=1.0)
        blanket.scale = (6.0, 0.1, 7.0)
    # comms mast + dish
    _add(coll, "comms_mast", cyl, at(el["comms_mast"], 4.0), hw, radius=0.1, depth=8.0)
    _add(coll, "comms_dish", cone, at(el["comms_mast"], 8.4), hw, radius1=0.5, radius2=0.05, depth=0.4)
    # landing pad 40 m + berm ring at 30 m radius, 2.5 m high (corridor gap = later pass)
    _add(coll, "pad", cyl, at(el["landing_pad"], 0.05), pad_m, radius=20.0, depth=0.1)
    bpy.ops.mesh.primitive_torus_add(location=at(el["landing_pad"], 0.0), major_radius=30.0, minor_radius=1.25)
    berm = bpy.context.object
    berm.name = "BLK_berm"
    berm.data.materials.append(berm_m)
    for c in berm.users_collection:
        c.objects.unlink(berm)
    coll.objects.link(berm)
    # landers: Mk2 stepped (7x5 cabin + 5x11 tanks = 16), HLS 9x52 + black skirt band
    _add(coll, "mk2_cabin", cyl, at(el["blue_moon_mk2"], 2.6), hw, radius=3.5, depth=5.0)
    _add(coll, "mk2_tanks", cyl, at(el["blue_moon_mk2"], 10.6), hw, radius=2.5, depth=11.0)
    _add(coll, "hls_hull", cyl, at(el["starship_hls"], 26.1), hw, radius=4.5, depth=52.0)
    _add(coll, "hls_skirt", cyl, at(el["starship_hls"], 3.0), _mat("blk_dark", (0.03, 0.03, 0.03, 1)), radius=4.55, depth=6.0)
    # FSP: 4x6 core + two 10x6 radiator wings + shadow-shield cone toward base
    _add(coll, "fsp_core", cyl, at(el["fsp_reactor"], 3.0), hw, radius=2.0, depth=6.0)
    for s in (-1, 1):
        wing = _add(coll, f"fsp_radiator_{'ew'[s > 0]}", box, at(el["fsp_reactor"] + Vector((s * 7, 0, 0)), 3.5), hw, size=1.0)
        wing.scale = (10.0, 0.2, 6.0)
    shield_bear = math.radians((lay["bearings_deg"]["fsp"] + 180) % 360)
    sh = _add(coll, "fsp_shield", cone, at(el["fsp_reactor"], 3.0), hw, radius1=3.0, radius2=0.5, depth=2.5)
    sh.rotation_euler = (math.radians(90), 0, -shield_bear)
    # astronaut scale marker by the habitat
    _add(coll, "astronaut_1p8", cyl, at(el["fsh_habitat"] + Vector((6, -4, 0)), 0.9), suit_m, radius=0.25, depth=1.8)

    # --- sun at provisional hero azimuth (D7 open) ---
    sun = bpy.data.objects["sun"]
    sun.rotation_euler = (math.radians(90.0 - 1.5), 0.0, math.radians(HERO_SUN_AZ_DEG))

    # --- cameras ---
    def add_cam(name, loc, look_at, lens=35.0, ortho_scale=None):
        cd = bpy.data.cameras.new(name)
        if ortho_scale:
            cd.type = "ORTHO"
            cd.ortho_scale = ortho_scale
        cd.lens = lens
        cd.clip_end = 100_000.0
        c = bpy.data.objects.new(name, cd)
        scene.collection.objects.link(c)
        c.location = loc
        c.rotation_euler = (Vector(look_at) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return c

    def surface_z(x, y):
        """Z of the displaced terrain (viewport-subdiv accuracy) via ray cast."""
        deps = bpy.context.evaluated_depsgraph_get()
        hit, loc, *_ = scene.ray_cast(deps, Vector((x, y, 50_000.0)), Vector((0, 0, -1)))
        return loc.z if hit else 0.0

    hero = lay["hero_camera_suggestion"]
    hab = el["fsh_habitat"]
    cam_hero = add_cam("CAM_hero", hero["local_m"], hero["look_at"], lens=50.0)
    add_cam("CAM_top", (hab.x, hab.y, hab.z + 4000), (hab.x, hab.y + 0.01, hab.z), ortho_scale=4500)
    # eye-level: 80 m out along the hero-cam line (known open ground), boom height,
    # Z from the real displaced surface (ray cast — interpolation buries cameras)
    hero_pos = Vector(hero["local_m"])
    d = (hero_pos - hab).normalized()
    eye_x, eye_y = hab.x + d.x * 80.0, hab.y + d.y * 80.0
    add_cam("CAM_eye", (eye_x, eye_y, surface_z(eye_x, eye_y) + 2.5), at(el["blue_moon_mk2"], 8.0), lens=35.0)
    scene.camera = cam_hero

    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    print(f"BLOCKOUT SAVED: {out_blend} ({len(coll.objects)} proxies)")

    if render_dir:
        import os
        os.makedirs(render_dir, exist_ok=True)
        for cam in ("CAM_hero", "CAM_top", "CAM_eye"):
            scene.camera = bpy.data.objects[cam]
            scene.render.filepath = os.path.join(render_dir, f"blockout_{cam[4:].lower()}.png")
            bpy.ops.render.render(write_still=True)
            print(f"BLOCKOUT RENDER: {scene.render.filepath}")


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--terrain-blend", required=True)
    ap.add_argument("--layout", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--render-dir", default=None)
    args = ap.parse_args(argv)
    build_blockout(args.terrain_blend, args.layout, args.out, args.render_dir)


if __name__ == "__main__":
    main()
