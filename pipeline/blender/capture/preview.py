"""Preview mode — bpy script (ML-free), Blender 5.1.

Samples the rig (rig.py, same code the export uses), spawns frustum markers into
PREVIEW_<vantage>, and prints/stores a stats readout. NOTHING here renders — the
preview exists so Kari can adjust ENV/FOCUS/props and re-run until happy; the
printed rig hash is what export_dataset.py later demands as --approved-rig.

Usage over MCP (or from the future Catalogue Tools panel):
    from pipeline.blender.capture import preview
    preview.run_preview("rehearsal")     # -> stats dict (also printed)
    preview.clear_preview("rehearsal")

Markers are linked-duplicate pyramids (one mesh + one flat material per color
group — object colors alone are invisible in the default Material shading mode).
"""

import math

import bpy
from mathutils import Matrix, Vector

from . import convention, rig

# color per (rig kind) — parent shells get a blue ramp by shell index
_COLORS = {
    "parent/playback": [(0.15, 0.45, 1.0, 1.0), (0.1, 0.7, 0.9, 1.0), (0.1, 0.9, 0.65, 1.0)],
    "parent/margin": [(0.55, 0.55, 0.55, 1.0)],
    "child/playback": [(0.8, 0.35, 1.0, 1.0), (0.95, 0.45, 0.8, 1.0), (1.0, 0.55, 0.55, 1.0)],
    "child/margin": [(0.45, 0.4, 0.5, 1.0)],
    "child/bridge": [(1.0, 0.85, 0.2, 1.0)],
}


def _marker_mesh_name(vantage, group):
    return f"PRV_{vantage}_{group}"


def _frustum_mesh(name, focal_mm, sensor_mm):
    """Unit-length wire pyramid: apex at origin, base 1 m towards -Z (camera fwd)."""
    s = sensor_mm / 2.0 / focal_mm
    verts = [(0, 0, 0), (-s, -s, -1), (s, -s, -1), (s, s, -1), (-s, s, -1)]
    faces = [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1), (1, 4, 3, 2)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return mesh


def _flat_material(name, rgba):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = False
    mat.diffuse_color = rgba
    return mat


def clear_preview(vantage):
    """Remove PREVIEW_<vantage> markers and materials. The CAPCAM_<vantage>
    preview camera survives (unlinked; ensure_preview_camera re-links it)."""
    coll = bpy.data.collections.get(f"PREVIEW_{vantage}")
    if coll is None:
        return
    for ob in list(coll.objects):
        if ob.type == "CAMERA":
            coll.objects.unlink(ob)
            continue
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.data.collections.remove(coll)
    for mesh in [m for m in bpy.data.meshes if m.name.startswith(f"PRV_{vantage}_")]:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for mat in [m for m in bpy.data.materials if m.name.startswith(f"PRV_{vantage}_")]:
        if mat.users == 0:
            bpy.data.materials.remove(mat)


def _format_stats(result):
    lines = [
        f"CAPTURE PREVIEW — vantage '{result['vantage']}'  "
        f"(preset {result['config']['preset']}, assembly {result['assembly']})",
        f"rig hash: {result['hash']}   <- pass as --approved-rig at execute time",
        "",
        f"views: " + ", ".join(f"{k}={v}" for k, v in sorted(result["totals"].items()))
        + f"   total={sum(result['totals'].values())}",
    ]
    for st in result["shell_stats"]:
        rej = ", ".join(f"{k}={v}" for k, v in st["rejected"].items() if v) or "none"
        lines.append(
            f"  {st['rig']:<18} shell {st['shell_m']:>7.1f} m  kept {st['kept']:>3}/{st['requested']:<3}"
            f"  max az gap {st['max_azimuth_gap_deg']:>5.1f}°  rejected: {rej}")
    if result["envelope"]:
        e = result["envelope"]
        a = e["angle_around_deg"]
        lines += [
            "",
            "runtime envelope (playback samples only — the same limits the web viewer will enforce):",
            f"  distance {e['distance_m']['min']}–{e['distance_m']['max']} m, "
            f"up/down {e['angle_up_down_deg']['min']}–{e['angle_up_down_deg']['max']}°, "
            f"around " + ("free 360°" if a["min"] is None else f"{a['min']}–{a['max']}°")
            + f", fov {e['zoom_fov_deg']}°",
        ]
    for key, oe in result.get("object_envelopes", {}).items():
        lines.append(
            f"  zoom '{key}': distance {oe['distance_m']['min']}–{oe['distance_m']['max']} m "
            f"@ look_at {oe['look_at_m']} (viewer frame)")
    if result["warnings"]:
        lines += ["", "WARNINGS:"] + [f"  ! {w}" for w in result["warnings"]]
    lines += ["", "adjust ENV_/FOCUS_/collection properties and re-run preview; "
                  "nothing renders without your go."]
    return "\n".join(lines)


# last rig result per vantage — reused by the camera preview so stepping
# through samples doesn't resample the rig every click
_LAST = {}


def rig_result(vantage_name, refresh=False):
    """Cached rig result for a vantage (generates without markers if needed)."""
    if refresh or vantage_name not in _LAST:
        vantages = convention.find_vantages()
        if vantage_name not in vantages:
            raise ValueError(f"no vantage {vantage_name!r} (have: {sorted(vantages)})")
        _LAST[vantage_name] = rig.generate_rig(vantages[vantage_name], render_fidelity=False)
    return _LAST[vantage_name]


def ensure_preview_camera(vantage_name, index):
    """Create/update the real camera CAPCAM_<vantage> posed at rig sample
    `index` (wrapped), configured with that sample's lens/sensor/clips, and make
    it the scene camera. Returns (camera_object, sample, sample_count).

    The camera is a normal Blender camera on purpose: look through it, adjust
    lens/clip with Blender's own tools, then write the values back to the
    capture with apply_camera_to_capture() (which changes the rig hash —
    re-preview for a fresh approval)."""
    from mathutils import Matrix, Vector

    result = rig_result(vantage_name)
    samples = result["samples"]
    if not samples:
        raise ValueError(f"{vantage_name}: rig has no samples")
    index %= len(samples)
    s = samples[index]

    name = f"CAPCAM_{vantage_name}"
    cam_data = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cam_data.lens = s["focal_mm"]
    cam_data.sensor_width = s["sensor_mm"]
    cam_data.clip_start = s["clip_start_m"]
    cam_data.clip_end = s["clip_end_m"]
    cam = bpy.data.objects.get(name)
    if cam is None:
        cam = bpy.data.objects.new(name, cam_data)
        cam.hide_render = True
    if not cam.users_collection:
        vantage = convention.find_vantages()[vantage_name]
        coll = bpy.data.collections.get(f"PREVIEW_{vantage_name}")
        if coll is None:
            coll = bpy.data.collections.new(f"PREVIEW_{vantage_name}")
            vantage.children.link(coll)
            coll.hide_render = True
        coll.objects.link(cam)
    m = Matrix([list(r) for r in s["rot"]]).to_4x4()
    m.translation = Vector(s["pos"])
    cam.matrix_world = m
    bpy.context.scene.camera = cam
    return cam, s, len(samples)


def apply_camera_to_capture(vantage_name):
    """Copy CAPCAM lens + clip values back onto the capture collection the
    current sample belongs to (parent or child rig). Returns (collection_name,
    dict_of_written_values). Changing these voids the previous approval hash —
    re-run the preview."""
    cam_data = bpy.data.cameras.get(f"CAPCAM_{vantage_name}")
    if cam_data is None:
        raise ValueError("no preview camera — use Look Through Camera first")
    result = _LAST.get(vantage_name)
    scene_cam = bpy.context.scene.camera
    # which rig does the currently shown sample belong to?
    rig_tag = "parent"
    if result is not None and scene_cam is not None and scene_cam.data == cam_data:
        # find the sample whose pose matches the camera (last ensure_ call wins)
        pos = scene_cam.matrix_world.translation
        best = min(result["samples"],
                   key=lambda s: sum((a - b) ** 2 for a, b in zip(s["pos"], pos)))
        rig_tag = best["rig"]
    vantage = convention.find_vantages()[vantage_name]
    coll = vantage
    if rig_tag.startswith("child:"):
        coll = convention.find_children(vantage).get(rig_tag[len("child:"):], vantage)
    values = {
        "focal_mm": round(cam_data.lens, 2),
        "clip_start_m": round(cam_data.clip_start, 4),
        "clip_end_m": round(cam_data.clip_end, 1),
    }
    for key, val in values.items():
        coll[key] = val
    _LAST.pop(vantage_name, None)  # rig config changed — force resample
    return coll.name, values


def run_preview(vantage_name):
    """Sample the rig, rebuild markers + stats. Returns the rig result dict."""
    vantages = convention.find_vantages()
    if vantage_name not in vantages:
        raise ValueError(f"no vantage {vantage_name!r} (have: {sorted(vantages)})")
    vantage = vantages[vantage_name]

    result = rig.generate_rig(vantage, render_fidelity=False)
    _LAST[vantage_name] = result

    clear_preview(vantage_name)
    coll = bpy.data.collections.new(f"PREVIEW_{vantage_name}")
    vantage.children.link(coll)
    coll.hide_render = True

    meshes, mats = {}, {}
    parent_shells = sorted({s["shell_m"] for s in result["samples"]
                            if s["rig"] == "parent" and s["kind"] == "playback"})
    child_shells = sorted({s["shell_m"] for s in result["samples"]
                           if s["rig"].startswith("child") and s["kind"] == "playback"})

    for i, s in enumerate(result["samples"]):
        side = "parent" if s["rig"] == "parent" else "child"
        ramp = _COLORS[f"{side}/{s['kind']}"]
        shells = parent_shells if side == "parent" else child_shells
        ci = shells.index(s["shell_m"]) % len(ramp) if s["kind"] == "playback" and s["shell_m"] in shells else 0
        group = f"{side}-{s['kind']}-{ci}"
        if group not in meshes:
            meshes[group] = _frustum_mesh(_marker_mesh_name(vantage_name, group),
                                          s["focal_mm"], s["sensor_mm"])
            mats[group] = _flat_material(f"PRV_{vantage_name}_{group}", ramp[ci])
            meshes[group].materials.append(mats[group])
        ob = bpy.data.objects.new(f"PRV_{vantage_name}_{i:04d}", meshes[group])
        rot = Matrix([list(r) for r in s["rot"]]).to_4x4()
        rot.translation = Vector(s["pos"])
        ob.matrix_world = rot
        size = min(6.0, max(0.5, 0.05 * s["shell_m"]))
        ob.scale = (size, size, size)
        ob.hide_render = True
        ob.hide_select = True
        coll.objects.link(ob)

    text = _format_stats(result)
    tb = bpy.data.texts.get(f"CAPTURE_STATS_{vantage_name}") or \
        bpy.data.texts.new(f"CAPTURE_STATS_{vantage_name}")
    tb.clear()
    tb.write(text)
    print(text)
    return result
