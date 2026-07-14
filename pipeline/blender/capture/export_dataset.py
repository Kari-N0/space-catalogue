"""Capture dataset export — bpy script (ML-free), run headless on Windows Blender:

    pipeline/blender/blender-win.sh -b <scene.blend> --python \\
        pipeline/blender/capture/export_dataset.py -- \\
        --vantage <name> --out /mnt/d/renders/<concept>/capture/<name> \\
        --approved-rig <hash-from-preview> [--concept lunar-base] [--limit N] [--dry-run]

    <out>/images/*.png + <out>/sparse/0/{cameras,images,points3D}.txt
    + capture-meta.json + capture-provenance.json

GATE: nothing renders without Kari's go. --approved-rig must match the hash the
preview printed (rig regenerated deterministically here and compared); any
mismatch — config, ENV mesh, FOCUS, seed changed since approval — refuses.

The caller (pipeline/splats/run_capture.py) MUST create the --out directory
before invoking: blender-win.sh only wslpath-converts absolute args whose parent
exists, and a POSIX path reaching Windows Blender unconverted must hard-fail.

Importable API: export_dataset(vantage, out_dir, approved_rig=None, concept="lunar-base",
                               limit=0, dry_run=False) -> meta dict
"""

import argparse
import json
import math
import os
import sys
import time

# --python scripts run as __main__ with no package context. Two homes exist:
# the repo (pipeline/blender/capture/) and the Catalogue Tools extension's
# vendored copy (catalogue_tools/capture/) — bootstrap whichever this file
# lives in, so the dataset export runs on any computer with just the add-on.
_HERE = os.path.dirname(os.path.abspath(__file__))
try:
    _REPO = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
    if _REPO not in sys.path:
        sys.path.insert(0, _REPO)
    from pipeline.blender.capture import convention, frames, rig  # noqa: E402
    _PKG = "pipeline.blender.capture"
except ImportError:
    _PARENT = os.path.dirname(_HERE)
    if _PARENT not in sys.path:
        sys.path.insert(0, _PARENT)
    from capture import convention, frames, rig  # noqa: E402
    _PKG = "capture"

import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

SCHEMA_VERSION = 1
INIT_POINT_CAP = 120_000
INIT_CHILD_CAP = 20_000


def _assert_capture_hidden():
    """capture/ never renders — force it and refuse cross-linked objects."""
    root = bpy.data.collections.get(convention.CAPTURE_ROOT)
    if root is None:
        return
    root.hide_render = True

    def subtree(coll, acc):
        acc.add(coll.name)
        for c in coll.children:
            subtree(c, acc)
        return acc

    names = subtree(root, set())
    for coll in [bpy.data.collections[n] for n in names]:
        for ob in coll.objects:
            ob.hide_render = True
            outside = [c.name for c in ob.users_collection if c.name not in names]
            if outside:
                raise RuntimeError(
                    f"{ob.name} is linked both under capture/ and into {outside} — "
                    "it would render into the dataset; unlink it first")


def _setup_cycles(scene):
    """Repo-standard OptiX block (build_terrain_audition.py convention)."""
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "OPTIX"
    scene.cycles.device = "GPU"
    scene.cycles.use_denoising = True
    scene.render.use_persistent_data = True  # camera-only changes: keep device scene
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_percentage = 100


def _material_color(ob):
    for slot in ob.material_slots:
        mat = slot.material
        if mat is None:
            continue
        if mat.use_nodes:
            node = mat.node_tree.nodes.get("Principled BSDF")
            if node is not None:
                c = node.inputs["Base Color"].default_value
                return (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))
        c = mat.diffuse_color
        return (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))
    return (128, 128, 128)


def _init_points(result):
    """Init cloud from evaluated mesh vertices near the vantage (capture frame)."""
    focus = tuple(result["focus_blender"])
    r_max = 1.5 * max(result["config"]["distance_shells_m"])
    child_regions = []
    for key, oe in result["object_envelopes"].items():
        # viewer (x,z,y) -> blender delta (x, z<-y? ) : viewer=(dx,dz,dy) => blender delta=(vx, vz, vy)
        v = oe["look_at_m"]
        cf = (focus[0] + v[0], focus[1] + v[2], focus[2] + v[1])
        child_regions.append((cf, 2.0 * oe["distance_m"]["max"]))

    deps = bpy.context.evaluated_depsgraph_get()
    root = bpy.data.collections.get(convention.CAPTURE_ROOT)
    import importlib
    _validity = importlib.import_module(_PKG + ".validity")
    _under_collection = _validity._under_collection
    render_visible_objects = _validity.render_visible_objects

    scene_pts, child_pts = [], []
    for ob in render_visible_objects(bpy.context.scene):
        if ob.type != "MESH":
            continue
        if root is not None and _under_collection(ob, root):
            continue
        rgb = _material_color(ob)
        ev = ob.evaluated_get(deps)
        mesh = ev.to_mesh()
        mw = ev.matrix_world
        for v in mesh.vertices:
            w = mw @ v.co
            wt = (w.x, w.y, w.z)
            in_child = any(
                (w - Vector(cf)).length <= cr for cf, cr in child_regions)
            if in_child:
                child_pts.append((frames.capture_from_blender(wt, focus), rgb))
            elif (w - Vector(focus)).length <= r_max:
                scene_pts.append((frames.capture_from_blender(wt, focus), rgb))
        ev.to_mesh_clear()

    if len(child_pts) > INIT_CHILD_CAP:
        child_pts = child_pts[::max(1, len(child_pts) // INIT_CHILD_CAP)]
    budget = INIT_POINT_CAP - len(child_pts)
    if len(scene_pts) > budget:
        scene_pts = scene_pts[::max(1, math.ceil(len(scene_pts) / budget))]
    return child_pts + scene_pts


def export_dataset(vantage, out_dir, approved_rig=None, concept="lunar-base",
                   limit=0, dry_run=False):
    if os.name == "nt" and out_dir.startswith("/"):
        raise RuntimeError(
            f"--out reached Windows Blender unconverted: {out_dir!r}. The caller must "
            "create the output directory first (blender-win.sh only converts existing paths)")

    t0 = time.perf_counter()
    scene = bpy.context.scene
    vantages = convention.find_vantages()
    if vantage not in vantages:
        raise RuntimeError(f"no vantage {vantage!r} in this file (have: {sorted(vantages)})")

    _assert_capture_hidden()
    result = rig.generate_rig(vantages[vantage], render_fidelity=True)

    # ---- the render gate -------------------------------------------------
    if not dry_run:
        if not approved_rig:
            raise RuntimeError(
                "refusing to render: no --approved-rig. Run preview, get Kari's go, "
                f"then pass the printed hash (current rig hash: {result['hash']})")
        if approved_rig != result["hash"]:
            raise RuntimeError(
                f"refusing to render: rig hash {result['hash']} != approved {approved_rig}. "
                "The vantage changed since preview — re-run preview and get a fresh go.")

    samples = result["samples"][:limit] if limit else result["samples"]
    names = [s["name"] for s in samples]
    if len(set(names)) != len(names):
        raise RuntimeError("duplicate image names in rig — refusing to write a corrupt dataset")
    # LichtFeld-Studio drop-in layout (Kari's convention, 2026-07-14):
    #   <out>/lichtFeld/{cameras,images,points3D}.txt + images/ + output/
    # plus sparse/0/ copies of the same three text files, so the very same
    # folder is also a standard COLMAP root for the optional gsplat path.
    lfs_dir = os.path.join(out_dir, "lichtFeld")
    img_dir = os.path.join(lfs_dir, "images")
    sparse_dir = os.path.join(lfs_dir, "sparse", "0")
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(os.path.join(lfs_dir, "output"), exist_ok=True)
    if not dry_run:
        # stale frames from a previous run (different preset/rig) would pollute
        # the image-count check and, worse, the training set
        for old in os.listdir(img_dir):
            if old.endswith(".png"):
                os.remove(os.path.join(img_dir, old))

    # ---- render ----------------------------------------------------------
    render_s = 0.0
    if not dry_run:
        _setup_cycles(scene)
        cam_data = bpy.data.cameras.new("capture_cam")
        cam_ob = bpy.data.objects.new("capture_cam", cam_data)
        scene.collection.objects.link(cam_ob)
        scene.camera = cam_ob
        t_render = time.perf_counter()
        for i, s in enumerate(samples):
            cam_data.lens = s["focal_mm"]
            cam_data.sensor_width = s["sensor_mm"]
            cam_data.clip_start = s["clip_start_m"]
            cam_data.clip_end = s["clip_end_m"]
            scene.render.resolution_x = s["resolution"]
            scene.render.resolution_y = s["resolution"]
            scene.cycles.samples = s["samples"]  # per-rig override (child rigs)
            m = Matrix([list(r) for r in s["rot"]]).to_4x4()
            m.translation = Vector(s["pos"])
            cam_ob.matrix_world = m
            scene.render.filepath = os.path.join(img_dir, s["name"])
            bpy.ops.render.render(write_still=True)
            print(f"CAPTURE RENDER {i + 1}/{len(samples)} {s['name']}", flush=True)
        render_s = time.perf_counter() - t_render

    # ---- COLMAP ----------------------------------------------------------
    focus = tuple(result["focus_blender"])
    groups = {}
    for s in samples:
        key = (s["resolution"], s["focal_mm"], s["sensor_mm"])
        groups.setdefault(key, len(groups) + 1)
    cameras = []
    for (res, focal, sensor), cid in sorted(groups.items(), key=lambda kv: kv[1]):
        f_px = focal / sensor * res
        cameras.append((cid, res, res, f_px, f_px, res / 2, res / 2))
    images = []
    for i, s in enumerate(samples, start=1):
        q, t = frames.colmap_pose(s["rot"], tuple(s["pos"]), focus)
        cid = groups[(s["resolution"], s["focal_mm"], s["sensor_mm"])]
        images.append((i, q, t, cid, s["name"]))
    points = _init_points(result)
    frames.write_colmap_text(lfs_dir, cameras, images, points)   # LFS reads from the root
    frames.write_colmap_text(sparse_dir, cameras, images, points)  # COLMAP-standard twin

    # ---- metadata + provenance -------------------------------------------
    meta = {
        "schema": f"capture-meta v{SCHEMA_VERSION}",
        "concept": concept,
        "vantage": vantage,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "blend_file": bpy.data.filepath,
        "blender_version": bpy.app.version_string,
        "frame": {
            "origin_blender": list(focus),
            "rotation": "RX90 (x,y,z)->(x,-z,y); Babylon shows (dx,dz,dy) after loader y-mirror",
            "rule": "SuperSplat pass: clean/crop ONLY — never rotate/translate/set-pivot",
        },
        "approved_rig": approved_rig,
        "rig_hash": result["hash"],
        "assembly": result["assembly"],
        "config": result["config"],
        "totals": result["totals"],
        "shell_stats": result["shell_stats"],
        "envelope": result["envelope"],
        "object_envelopes": result["object_envelopes"],
        "warnings": result["warnings"],
        "images": len(samples),
        "init_points": len(points),
        "trainer": {
            "max_steps": result["config"]["max_steps"],
            "cap_max": result["config"]["cap_max"],
            "flags_note": "MUST train with --no-normalize-world-space (frame contract)",
        },
        "timing": {"render_s": round(render_s, 1)},
    }
    with open(os.path.join(out_dir, "capture-meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)

    provenance = {
        "asset": f"capture dataset {concept}/{vantage}",
        "generated": meta["generated"],
        "stages": [{
            "stage": "render-dataset",
            "tool": f"Blender {bpy.app.version_string} / Cycles OptiX",
            "script": "pipeline/blender/capture/export_dataset.py",
            "blend_file": bpy.data.filepath,
            "seed": result["config"]["seed"],
            "views": len(samples),
            "resolution": result["config"]["resolution"],
            "license": "original render — project IP; terrain DEM lineage per "
                       "pipeline/provenance/lunar-base/terrain-dems.json",
        }],
    }
    with open(os.path.join(out_dir, "capture-provenance.json"), "w") as fh:
        json.dump(provenance, fh, indent=2)

    print(f"CAPTURE DATASET DONE: {len(samples)} views, {len(points)} init points, "
          f"{len(cameras)} camera group(s)")
    print(f"TIMING: render {render_s:.0f}s, total {time.perf_counter() - t0:.0f}s")
    return meta


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vantage", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--approved-rig", default=None)
    ap.add_argument("--concept", default="lunar-base")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    export_dataset(args.vantage, args.out, approved_rig=args.approved_rig,
                   concept=args.concept, limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
