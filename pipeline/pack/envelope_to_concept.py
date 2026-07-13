"""Merge a capture envelope into a concept page JSON — pure Python, no bpy/ML.

    python3 pipeline/pack/envelope_to_concept.py \\
        --meta <capture-meta.json | capture-<vantage>.envelope.json> \\
        [--concept-json content/concepts/lunar-base.json] [--apply] [--set-fov]

Default is a DRY RUN: prints a unified diff and warnings, writes nothing.
The training envelope and the runtime envelope come from the same source object
(CLAUDE.md hard rule); this script only MERGES the numbers the rig derived —
all envelope math lives in pipeline/blender/capture/frames.py.

Merge policy (content/concepts/<id>.json is Kari's editing surface):
  generated → written:   look_at_m, distance_m.min/max, angle_up_down_deg,
                         angle_around_deg, camera.object_envelopes.*,
                         _camera_generated (audit note)
  authored → preserved:  distance_m.start (clamped into the new range, warned),
                         controls, move_limit_m, zoom_fov_deg (unless --set-fov
                         or absent), pins, features, every other byte of the file
  warned:                pins vs a moved target, feature view angles outside a
                         finite orbit arc, fov drift vs the rig camera, pan reach
"""

import argparse
import difflib
import json
import sys


def _load_envelope(meta_path):
    with open(meta_path) as fh:
        doc = json.load(fh)
    if "envelope" not in doc or doc["envelope"] is None:
        sys.exit(f"{meta_path}: no envelope block (rig had no playback samples?)")
    return doc


def _strip_private(obj):
    if isinstance(obj, dict):
        return {k: _strip_private(v) for k, v in obj.items() if not k.startswith("_")}
    return obj


def merge(meta_path, concept_path, apply=False, set_fov=False):
    src = _load_envelope(meta_path)
    env = src["envelope"]
    with open(concept_path) as fh:
        original = fh.read()
    doc = json.loads(original)

    live = doc.setdefault("live_view", {})
    cam = live.setdefault("camera", {})
    warnings = []

    # alpha invariant (a wrapped pair would pin Babylon's clamp to one endpoint)
    arc = env["angle_around_deg"]
    if arc["min"] is not None and not (arc["min"] < arc["max"] <= arc["min"] + 360):
        sys.exit(f"alpha arc invariant broken in {meta_path}: {arc}")

    old_target = cam.get("look_at_m")
    if old_target is not None and old_target != env["look_at_m"]:
        n_pins = len(live.get("pins", []))
        if n_pins:
            warnings.append(
                f"look_at_m moves {old_target} -> {env['look_at_m']}: {n_pins} authored "
                "pin position(s) were placed against the old frame — re-check them")
    cam["look_at_m"] = env["look_at_m"]

    dist = cam.setdefault("distance_m", {})
    start = dist.get("start")
    dist["min"], dist["max"] = env["distance_m"]["min"], env["distance_m"]["max"]
    if isinstance(start, (int, float)):
        clamped = min(max(start, dist["min"]), dist["max"])
        if clamped != start:
            warnings.append(f"authored distance_m.start {start} clamped to {clamped}")
        dist["start"] = clamped

    cam["angle_up_down_deg"] = dict(env["angle_up_down_deg"])
    cam["angle_around_deg"] = dict(env["angle_around_deg"])

    rig_fov = env["zoom_fov_deg"]
    if "zoom_fov_deg" not in cam or set_fov:
        cam["zoom_fov_deg"] = rig_fov
    elif abs(cam["zoom_fov_deg"] - rig_fov) > 2.0:
        warnings.append(
            f"authored zoom_fov_deg {cam['zoom_fov_deg']} vs rig camera {rig_fov} "
            "(lens mismatch between training and playback; --set-fov to adopt the rig's)")

    move = cam.get("move_limit_m")
    if isinstance(move, (int, float)) and move > 0.25 * dist["min"]:
        warnings.append(
            f"move_limit_m {move} is >25% of distance min {dist['min']} — panning can "
            "reach regions the orbit rig never photographed")

    if arc["min"] is not None:
        for feat in doc.get("overview", {}).get("features", []):
            a = -90.0 + float(feat.get("view_angle_deg", 0))
            k = round(((arc["min"] + arc["max"]) / 2 - a) / 360.0)
            a += 360.0 * k
            if not (arc["min"] - 1e-6 <= a <= arc["max"] + 1e-6):
                warnings.append(
                    f"feature '{feat.get('label', '?')}' view_angle_deg {feat.get('view_angle_deg')} "
                    "falls outside the finite orbit arc — that window will clamp to an arc edge")

    obj_envs = _strip_private(src.get("object_envelopes") or {})
    if obj_envs:
        cam["object_envelopes"] = obj_envs
    else:
        cam.pop("object_envelopes", None)

    cam["_camera_generated"] = {
        "note": "envelope fields generated from the capture rig — do not hand-edit "
                "look_at_m/distance min,max/angles; edit the vantage in Blender and re-export",
        "vantage": src.get("vantage"),
        "rig_hash": src.get("rig_hash"),
        "blend_file": src.get("blend_file"),
        "generated": src.get("generated"),
        "tool": "pipeline/pack/envelope_to_concept.py",
    }

    updated = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    diff = list(difflib.unified_diff(
        original.splitlines(keepends=True), updated.splitlines(keepends=True),
        fromfile=concept_path, tofile=concept_path + (" (applied)" if apply else " (dry-run)")))

    sys.stdout.writelines(diff or ["(no changes)\n"])
    for w in warnings:
        print(f"WARNING: {w}")
    if apply:
        with open(concept_path, "w") as fh:
            fh.write(updated)
        print(f"applied -> {concept_path}")
    else:
        print("dry run — re-run with --apply to write")
    return {"warnings": warnings, "changed": bool(diff)}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--meta", required=True,
                    help="capture-meta.json or capture-<vantage>.envelope.json")
    ap.add_argument("--concept-json", default="content/concepts/lunar-base.json")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--set-fov", action="store_true",
                    help="adopt the rig camera's FOV even when the JSON has an authored one")
    args = ap.parse_args()
    merge(args.meta, args.concept_json, apply=args.apply, set_fov=args.set_fov)


if __name__ == "__main__":
    main()
