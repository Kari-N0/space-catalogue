"""Rehearsal scene + 3DGS training dataset exporter (PLAN.md §11, stage 1).

Seed of the future pipeline/blender/export_dataset.py (Phase 10 handover):
known camera poses -> no COLMAP solve, zero pose error.

Builds a primitive scene, renders ~120 hemisphere views with Cycles/OptiX,
and writes a COLMAP-format dataset (the layout gsplat's simple_trainer
consumes via its colmap parser):

    <out>/images/00000.png ...
    <out>/sparse/0/{cameras.txt, images.txt, points3D.txt}

Run headless on Windows Blender via blender-win.sh:
    blender-win.sh -b --python make_scene.py -- --out /mnt/d/renders/rehearsal
(the wrapper converts the path argument to D:\\renders\\rehearsal)
"""

import argparse
import math
import os
import sys
import time

import bpy
from mathutils import Matrix, Vector

# ---------------------------------------------------------------- args
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--views", type=int, default=120)
ap.add_argument("--res", type=int, default=800)
ap.add_argument("--samples", type=int, default=64)
args = ap.parse_args(argv)

OUT = args.out
IMG_DIR = os.path.join(OUT, "images")
SPARSE_DIR = os.path.join(OUT, "sparse", "0")
os.makedirs(IMG_DIR, exist_ok=True)
os.makedirs(SPARSE_DIR, exist_ok=True)

t_start = time.perf_counter()

# ---------------------------------------------------------------- scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def add_material(obj, name, rgba):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = rgba
    obj.data.materials.append(mat)
    return rgba

colors = {}

bpy.ops.mesh.primitive_plane_add(size=6)
plane = bpy.context.object
# subdivide so the ground contributes a grid of init points
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.subdivide(number_cuts=19)
bpy.ops.object.mode_set(mode="OBJECT")
colors[plane.name] = add_material(plane, "ground", (0.55, 0.5, 0.45, 1))

bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-1.2, -0.8, 0.5))
colors[bpy.context.object.name] = add_material(bpy.context.object, "cube", (0.8, 0.15, 0.1, 1))

bpy.ops.mesh.primitive_uv_sphere_add(radius=0.6, location=(1.1, -0.6, 0.6))
bpy.ops.object.shade_smooth()
colors[bpy.context.object.name] = add_material(bpy.context.object, "sphere", (0.1, 0.35, 0.8, 1))

bpy.ops.mesh.primitive_cone_add(radius1=0.5, depth=1.2, location=(0.0, 1.1, 0.6))
colors[bpy.context.object.name] = add_material(bpy.context.object, "cone", (0.9, 0.7, 0.1, 1))

bpy.ops.mesh.primitive_torus_add(major_radius=0.5, minor_radius=0.18, location=(-0.2, 0.1, 1.4))
bpy.ops.object.shade_smooth()
colors[bpy.context.object.name] = add_material(bpy.context.object, "torus", (0.1, 0.7, 0.3, 1))

bpy.ops.object.light_add(type="SUN", location=(4, -3, 6))
sun = bpy.context.object
sun.data.energy = 4.0
sun.data.angle = math.radians(0.5)
sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(30))

world = bpy.data.worlds.new("world")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.85, 0.85, 0.85, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0

# ---------------------------------------------------------------- render config
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == "OPTIX"
scene.cycles.device = "GPU"
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.render.resolution_x = args.res
scene.render.resolution_y = args.res
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"

FOCAL_MM, SENSOR_MM = 40.0, 36.0
cam_data = bpy.data.cameras.new("cam")
cam_data.lens = FOCAL_MM
cam_data.sensor_width = SENSOR_MM
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

# ---------------------------------------------------------------- camera rig
# Golden-angle hemisphere: uniform-ish coverage, elevation 15..70 deg,
# all aimed at the scene center. This envelope definition must match the
# web camera limits later (PLAN.md §10).
N = args.views
TARGET = Vector((0.0, 0.0, 0.6))
RADIUS = 8.0
GOLDEN = math.radians(137.50776)
E0, E1 = math.radians(15), math.radians(70)

poses = []
for i in range(N):
    elev = math.asin(math.sin(E0) + (math.sin(E1) - math.sin(E0)) * (i + 0.5) / N)
    az = i * GOLDEN
    loc = Vector((
        RADIUS * math.cos(elev) * math.cos(az),
        RADIUS * math.cos(elev) * math.sin(az),
        RADIUS * math.sin(elev),
    )) + Vector((0, 0, TARGET.z))
    cam.location = loc
    cam.rotation_euler = (TARGET - loc).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    poses.append((f"{i:05d}.png", cam.matrix_world.copy()))

# ---------------------------------------------------------------- render loop
t_render = time.perf_counter()
for name, M in poses:
    cam.matrix_world = M
    scene.render.filepath = os.path.join(IMG_DIR, name)
    bpy.ops.render.render(write_still=True)
render_s = time.perf_counter() - t_render

# ---------------------------------------------------------------- COLMAP export
res = args.res
f_px = FOCAL_MM / SENSOR_MM * res
with open(os.path.join(SPARSE_DIR, "cameras.txt"), "w") as fh:
    fh.write("# CAMERA_ID MODEL WIDTH HEIGHT PARAMS\n")
    fh.write(f"1 PINHOLE {res} {res} {f_px} {f_px} {res / 2} {res / 2}\n")

# COLMAP wants world->cam in OpenCV convention (x right, y down, z forward);
# Blender cameras are OpenGL (y up, looking down -z): flip Y and Z.
D = Matrix(((1, 0, 0), (0, -1, 0), (0, 0, -1)))
with open(os.path.join(SPARSE_DIR, "images.txt"), "w") as fh:
    fh.write("# IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME\n")
    for idx, (name, M) in enumerate(poses, start=1):
        r_w2c = M.to_3x3().transposed()
        t_w2c = -(r_w2c @ M.translation)
        r_cv = D @ r_w2c
        t_cv = D @ t_w2c
        q = r_cv.to_quaternion()
        fh.write(f"{idx} {q.w} {q.x} {q.y} {q.z} {t_cv.x} {t_cv.y} {t_cv.z} 1 {name}\n\n")

deps = bpy.context.evaluated_depsgraph_get()
pid = 0
with open(os.path.join(SPARSE_DIR, "points3D.txt"), "w") as fh:
    fh.write("# POINT3D_ID X Y Z R G B ERROR TRACK[]\n")
    for obj in scene.objects:
        if obj.type != "MESH":
            continue
        rgba = colors.get(obj.name, (0.5, 0.5, 0.5, 1))
        r, g, b = (int(c * 255) for c in rgba[:3])
        mesh = obj.evaluated_get(deps).to_mesh()
        for v in mesh.vertices:
            w = obj.matrix_world @ v.co
            pid += 1
            fh.write(f"{pid} {w.x} {w.y} {w.z} {r} {g} {b} 0.1\n")

total_s = time.perf_counter() - t_start
print(f"DATASET DONE: {N} views @ {res}px, {pid} init points")
print(f"TIMING: render {render_s:.0f}s, total {total_s:.0f}s")
