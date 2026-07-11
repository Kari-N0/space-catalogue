"""render_asset_turnaround.py — neutral review renders for the asset loop (ASSETS.md).

bpy script (ML-free), run headless on Windows Blender:
    pipeline/blender/blender-win.sh -b <asset.blend> --python pipeline/blender/render_asset_turnaround.py -- \
        --collection AST_pad --out-dir /mnt/d/renders/lunar-base/assets/pad

NEUTRAL BY CONSTRUCTION (CLAUDE.md art-direction boundaries): three cameras at
fixed azimuths 0/120/240 deg, fixed 22 deg elevation, 50 mm, distance auto-fit
to the collection bounding box +15% margin, aimed at bbox center. Sun elevation
35 deg at camera azimuth +50 deg, physical 1361 W/m^2, AgX @ -4.5 EV, plus a
0.02-strength gray world so shadowed geometry stays readable. 1280x1280.
These are review documents, not shots — no composition choices are made here.

Importable: render_turnaround(collection, out_dir) -> list[str]
"""

import argparse
import math
import os
import sys

import bpy
from mathutils import Vector


def _bbox(coll):
    deps = bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e18,) * 3)
    hi = Vector((-1e18,) * 3)
    objs = list(coll.objects)
    for child in coll.children:
        objs += list(child.objects)
    for ob in objs:
        if ob.type != "MESH":
            continue
        ev = ob.evaluated_get(deps)
        for corner in ev.bound_box:
            w = ev.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def render_turnaround(collection: str, out_dir: str) -> list:
    scene = bpy.context.scene
    coll = bpy.data.collections[collection]
    lo, hi = _bbox(coll)
    center = (lo + hi) / 2
    extent = max((hi - lo).length, 1.0)

    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "OPTIX"
    scene.cycles.device = "GPU"
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = 1280
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = -4.5

    world = bpy.data.worlds.new("turnaround_fill")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.02

    sun_data = bpy.data.lights.new("turnaround_sun", type="SUN")
    sun_data.energy = 1361.0
    sun_data.angle = math.radians(0.53)
    sun = bpy.data.objects.new("turnaround_sun", sun_data)
    scene.collection.objects.link(sun)

    cam_data = bpy.data.cameras.new("turnaround_cam")
    cam_data.lens = 50.0
    cam_data.clip_end = 100_000.0
    cam = bpy.data.objects.new("turnaround_cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    fov = 2 * math.atan(18.0 / cam_data.lens)  # sensor 36 mm
    dist = (extent / 2) / math.tan(fov / 2) * 1.15
    elev = math.radians(22.0)

    os.makedirs(out_dir, exist_ok=True)
    frames = []
    for az_deg in (0, 120, 240):
        az = math.radians(az_deg)
        cam.location = center + Vector((
            dist * math.cos(elev) * math.sin(az),
            dist * math.cos(elev) * math.cos(az),
            dist * math.sin(elev),
        ))
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
        sun.rotation_euler = (math.radians(90.0 - 35.0), 0.0, az + math.radians(50.0))
        path = os.path.join(out_dir, f"turn_{az_deg:03d}.png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        frames.append(path)
        print(f"TURNAROUND: {path}")
    return frames


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--collection", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)
    render_turnaround(args.collection, args.out_dir)


if __name__ == "__main__":
    main()
