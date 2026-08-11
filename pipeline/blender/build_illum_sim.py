"""build_illum_sim.py — build the polar illumination simulation scene (v002).

bpy script (ML-free), run headless on Windows Blender:
    pipeline/blender/blender-win.sh -b --factory-startup \
        --python pipeline/blender/build_illum_sim.py -- \
        --exr-dir assets_src/lunar-base/figures/illum_v002 \
        --out assets_src/lunar-base/figures/illum_v002/illum_sim_v002.blend

Scene model (see the v002 method note in the provenance record):
  * Sun is defined in the SOUTH POLE's local frame: a sweep runs at constant
    pole-datum elevation and the curvature-corrected terrain supplies every
    pixel's local sun geometry automatically (daily modulation included).
  * Terrain = 5 planes, all displaced by Cycles true displacement from
    composite EXRs (absolute meters vs the 1737.4 km sphere) with the
    curvature term  z -= (x^2+y^2) / 2R  applied in the shader, POLE-referenced
    (v001 FIG_02 used the same correction but frame-center-referenced).
      - inset: the 20 m grid B footprint (illum_B_dem.exr)
      - 4 bands: the 60 m grid A domain around it (illum_A_dem.exr),
        no overlap, so no z-fighting shadows at grazing sun
  * Flat white diffuse everywhere, black world, no bounces — a pixel is lit
    iff it receives direct sun (classified later from float EXRs).
  * Two cameras replicated VERBATIM from Kari's figure blends (2026-08-08
    probe): illum_camA = fig01_cam.001 (wide map), illum_camB = fig02_cam of
    fig02_shadow_clock_image_4_5_ratio.blend (close-up). Both ortho, AUTO fit,
    2048x2560 -> ortho_scale is the VERTICAL extent.

Importable API: build_sim(exr_dir, out_path) -> None
"""

import argparse
import json
import math
import os
import sys

import bpy

R_MOON_M = 1_737_400.0

# Kari's camera parameters, replicated verbatim (probe 2026-08-08)
CAMERAS = {
    "illum_camA": {"loc": (-25020.0, 5010.0, 60000.0), "ortho_scale": 230000.0},
    "illum_camB": {"loc": (-4321.5, -15461.1, 60000.0), "ortho_scale": 58252.19921875},
}
RES_X, RES_Y = 2048, 2560  # 4:5, both figures


def _load_meta(exr_dir: str, name: str) -> dict:
    with open(os.path.join(exr_dir, name + ".meta.json")) as f:
        return json.load(f)


def _terrain_material(name: str, exr_path: str, bounds: dict) -> bpy.types.Material:
    """White diffuse + true displacement: h(x,y) - (x^2+y^2)/2R, world-XY mapped."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.displacement_method = "DISPLACEMENT"
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfDiffuse")
    bsdf.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    bsdf.inputs["Roughness"].default_value = 1.0
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs["Vector"])

    # uv = ((x-left)/(right-left), (y-bottom)/(top-bottom)); row 0 of the EXR is
    # the top edge and Blender maps v=1 to it, so this is orientation-correct.
    left, right = bounds["left"], bounds["right"]
    bottom, top = bounds["bottom"], bounds["top"]
    u = nt.nodes.new("ShaderNodeMath"); u.operation = "MULTIPLY_ADD"
    u.inputs[1].default_value = 1.0 / (right - left)
    u.inputs[2].default_value = -left / (right - left)
    nt.links.new(sep.outputs["X"], u.inputs[0])
    v = nt.nodes.new("ShaderNodeMath"); v.operation = "MULTIPLY_ADD"
    v.inputs[1].default_value = 1.0 / (top - bottom)
    v.inputs[2].default_value = -bottom / (top - bottom)
    nt.links.new(sep.outputs["Y"], v.inputs[0])
    uv = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(u.outputs[0], uv.inputs["X"])
    nt.links.new(v.outputs[0], uv.inputs["Y"])

    img = bpy.data.images.load(exr_path, check_existing=True)
    img.colorspace_settings.name = "Non-Color"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    tex.extension = "EXTEND"
    nt.links.new(uv.outputs["Vector"], tex.inputs["Vector"])

    # curvature drop, POLE-referenced: (x^2 + y^2) / (2R)
    x2 = nt.nodes.new("ShaderNodeMath"); x2.operation = "MULTIPLY"
    nt.links.new(sep.outputs["X"], x2.inputs[0]); nt.links.new(sep.outputs["X"], x2.inputs[1])
    y2 = nt.nodes.new("ShaderNodeMath"); y2.operation = "MULTIPLY"
    nt.links.new(sep.outputs["Y"], y2.inputs[0]); nt.links.new(sep.outputs["Y"], y2.inputs[1])
    d2 = nt.nodes.new("ShaderNodeMath"); d2.operation = "ADD"
    nt.links.new(x2.outputs[0], d2.inputs[0]); nt.links.new(y2.outputs[0], d2.inputs[1])
    drop = nt.nodes.new("ShaderNodeMath"); drop.operation = "DIVIDE"
    nt.links.new(d2.outputs[0], drop.inputs[0])
    drop.inputs[1].default_value = 2.0 * R_MOON_M

    height = nt.nodes.new("ShaderNodeMath"); height.operation = "SUBTRACT"
    nt.links.new(tex.outputs["Color"], height.inputs[0])
    nt.links.new(drop.outputs[0], height.inputs[1])

    disp = nt.nodes.new("ShaderNodeDisplacement")
    disp.inputs["Midlevel"].default_value = 0.0
    disp.inputs["Scale"].default_value = 1.0
    nt.links.new(height.outputs[0], disp.inputs["Height"])
    nt.links.new(disp.outputs["Displacement"], out.inputs["Displacement"])
    return mat


def _rect_plane(name: str, x0: float, x1: float, y0: float, y1: float,
                mat: bpy.types.Material, cell_m: float = 2000.0) -> bpy.types.Object:
    """Rect grid plane [x0,x1]x[y0,y1] at z=0 with adaptive subdivision."""
    nx = max(2, min(256, round((x1 - x0) / cell_m)))
    ny = max(2, min(256, round((y1 - y0) / cell_m)))
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=nx, y_subdivisions=ny, size=1.0)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = ((x1 - x0), (y1 - y0), 1.0)
    obj.location = ((x0 + x1) / 2.0, (y0 + y1) / 2.0, 0.0)
    bpy.ops.object.transform_apply(location=True, scale=True)
    obj.data.materials.append(mat)
    mod = obj.modifiers.new("adaptive", "SUBSURF")
    mod.subdivision_type = "SIMPLE"
    # Blender 5.x: adaptive subdivision lives on the modifier (obj.cycles.* is gone)
    mod.use_adaptive_subdivision = True
    return obj


def build_sim(exr_dir: str, out_path: str) -> None:
    # fresh file
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "ILLUM_V002"

    meta_a = _load_meta(exr_dir, "illum_A_dem")
    meta_b = _load_meta(exr_dir, "illum_B_dem")
    a, b = meta_a["bounds_m"], meta_b["bounds_m"]

    mat_a = _terrain_material("illum_mat_A60", os.path.join(exr_dir, "illum_A_dem.exr"), a)
    mat_b = _terrain_material("illum_mat_B20", os.path.join(exr_dir, "illum_B_dem.exr"), b)

    # inset (20 m) + 4 non-overlapping 60 m bands around it, out to the full A domain
    _rect_plane("illum_inset", b["left"], b["right"], b["bottom"], b["top"], mat_b, cell_m=1000.0)
    _rect_plane("illum_band_N", a["left"], a["right"], b["top"], a["top"], mat_a)
    _rect_plane("illum_band_S", a["left"], a["right"], a["bottom"], b["bottom"], mat_a)
    _rect_plane("illum_band_W", a["left"], b["left"], b["bottom"], b["top"], mat_a)
    _rect_plane("illum_band_E", b["right"], a["right"], b["bottom"], b["top"], mat_a)

    # cameras, verbatim from Kari's figure blends (top-down, north up)
    for name, p in CAMERAS.items():
        cam = bpy.data.cameras.new(name)
        cam.type = "ORTHO"
        cam.ortho_scale = p["ortho_scale"]
        cam.sensor_fit = "AUTO"
        cam.clip_start = 1000.0
        cam.clip_end = 200000.0
        obj = bpy.data.objects.new(name, cam)
        obj.location = p["loc"]
        obj.rotation_euler = (0.0, 0.0, 0.0)
        scene.collection.objects.link(obj)
    scene.camera = bpy.data.objects["illum_camA"]

    # sun: the runner sets elevation/azimuth/angle per sweep
    sun_data = bpy.data.lights.new("illum_sun", "SUN")
    sun_data.energy = 1361.0
    sun_data.angle = 0.0
    sun = bpy.data.objects.new("illum_sun", sun_data)
    scene.collection.objects.link(sun)

    # black world — direct sun is the only light
    world = bpy.data.worlds.new("illum_world")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0, 0, 0, 1)
    bg.inputs["Strength"].default_value = 0.0
    scene.world = world

    # Cycles: OptiX, experimental (adaptive dicing), direct light only
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "OPTIX"
    scene.cycles.device = "GPU"
    # (no feature_set in Blender 5.x — adaptive subdivision is stable now)
    scene.cycles.dicing_rate = 1.0
    scene.cycles.max_bounces = 0
    scene.cycles.diffuse_bounces = 0
    scene.cycles.glossy_bounces = 0
    scene.cycles.transmission_bounces = 0
    scene.cycles.volume_bounces = 0
    scene.cycles.transparent_max_bounces = 0
    scene.cycles.use_denoising = False
    scene.cycles.samples = 8
    scene.render.use_persistent_data = True

    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_mode = "BW"
    scene.render.image_settings.color_depth = "32"
    scene.render.image_settings.exr_codec = "ZIP"
    scene.view_settings.view_transform = "Raw"

    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    print(f"ILLUM SIM BUILT: {out_path}")


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--exr-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    build_sim(os.path.abspath(args.exr_dir), os.path.abspath(args.out))


if __name__ == "__main__":
    main()
