"""build_terrain_audition.py — build a 1:1 terrain audition .blend from an EXR heightmap.

bpy script (ML-free), run headless on Windows Blender:
    pipeline/blender/blender-win.sh -b --python pipeline/blender/build_terrain_audition.py -- \
        --exr <site.exr> --meta <site.meta.json> --vantage <site.vantage.json> --out <terrain_site_v001.blend>

Identical setup for every audition site (D2 methodology, SCENE-BIBLE.md §5 lighting):
  grid plane at true 1:1 meters + Displace(EXR, strength 1, mid 0) on a simple
  11-level subdivision (~2048^2 render mesh, ~7.8 m/vertex vs 5 m/px data);
  placeholder regolith (albedo 0.13, roughness 1); black world; Sun 1361 W/m^2,
  angular size 0.53 deg, elevation +1.5 deg; Cycles/OptiX, AgX at exposure -10.4;
  camera 24 mm at the vantage-JSON position, aimed at its target.

Importable API: build_audition_blend(exr, meta, vantage, out) -> None
"""

import argparse
import json
import math
import sys

import bpy
from mathutils import Vector

SUBSURF_RENDER_LEVELS = 11   # 2048x2048 quads at render
SUBSURF_VIEW_LEVELS = 9      # 512x512 for flying the viewport
SUN_ELEVATION_DEG = 1.5      # bible §5: max summer sun at ~89.5S
SUN_ANGLE_DEG = 0.53
SUN_IRRADIANCE = 1361.0
# Exposure is a view-transform choice, not physics: expose for grazing-lit
# terrain legibility. Flat ground at 1.5 deg sun sees ~36 W/m^2 (radiance ~1.5);
# -4.5 EV puts that dark-but-readable and lets sun-facing slopes (up to ~56)
# roll off through AgX's shoulder. Sun strength itself stays physical.
EXPOSURE_EV = -4.5
REGOLITH_ALBEDO = 0.13


def build_audition_blend(exr_path: str, meta_path: str, vantage_path: str, out_path: str) -> None:
    with open(meta_path) as fh:
        meta = json.load(fh)
    with open(vantage_path) as fh:
        van = json.load(fh)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    # ---- terrain plane (1:1 meters, centered at tile center) ----
    size_x = meta["suggested_plane_size_m"]["x"]
    size_y = meta["suggested_plane_size_m"]["y"]
    bpy.ops.mesh.primitive_plane_add(size=1.0)
    terrain = bpy.context.object
    terrain.name = f"terrain_{van['site']}"
    terrain.scale = (size_x, size_y, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.shade_smooth()

    subsurf = terrain.modifiers.new("subdiv", "SUBSURF")
    subsurf.subdivision_type = "SIMPLE"
    subsurf.levels = SUBSURF_VIEW_LEVELS
    subsurf.render_levels = SUBSURF_RENDER_LEVELS
    subsurf.show_only_control_edges = True

    img = bpy.data.images.load(exr_path)
    img.colorspace_settings.name = "Non-Color"
    tex = bpy.data.textures.new("heightmap", type="IMAGE")
    tex.image = img
    tex.extension = "EXTEND"
    disp = terrain.modifiers.new("displace", "DISPLACE")
    disp.texture = tex
    disp.texture_coords = "UV"
    disp.direction = "Z"
    disp.strength = 1.0
    disp.mid_level = 0.0

    mat = bpy.data.materials.new("regolith_placeholder")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (REGOLITH_ALBEDO, REGOLITH_ALBEDO, REGOLITH_ALBEDO, 1.0)
    bsdf.inputs["Roughness"].default_value = 1.0
    terrain.data.materials.append(mat)

    # ---- black world (bible §5: zero scattering, no earthshine in audition) ----
    world = bpy.data.worlds.new("black")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0, 0, 0, 1)
    bg.inputs["Strength"].default_value = 0.0

    # ---- sun (azimuth 0 placeholder; the sun-study script rotates it) ----
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.name = "sun"
    sun.data.energy = SUN_IRRADIANCE
    sun.data.angle = math.radians(SUN_ANGLE_DEG)
    sun.rotation_euler = (math.radians(90.0 - SUN_ELEVATION_DEG), 0.0, 0.0)

    # ---- camera at the audition vantage ----
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 24.0
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.1
    cam_data.clip_end = 100_000.0
    cam = bpy.data.objects.new("audition_cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    loc = Vector(van["camera_local_m"])
    tgt = Vector(van["target_local_m"])
    cam.location = loc
    cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()

    # ---- render config: Cycles/OptiX, AgX at physical exposure ----
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "OPTIX"
    scene.cycles.device = "GPU"
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = EXPOSURE_EV

    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    print(f"AUDITION BLEND SAVED: {out_path} ({van['name']}, "
          f"plane {size_x:.0f}x{size_y:.0f} m, relief {meta['elevation_range_m']:.0f} m)")


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--exr", required=True)
    ap.add_argument("--meta", required=True)
    ap.add_argument("--vantage", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    build_audition_blend(args.exr, args.meta, args.vantage, args.out)


if __name__ == "__main__":
    main()
