"""Rig generation — bpy script (ML-free), Blender 5.1.

Deterministic function of (scene geometry, CAPTURE_ collection properties):
same scene + same props + same seed => identical rig, identical contract hash.
Preview and export call the same code; export additionally raises SUBSURF
viewport levels to render levels while sampling (try/finally, never saved) so
headless validation sees render-accurate terrain, while interactive preview
compensates with validity.TERRAIN_TOL_M-tightened thresholds instead.

Importable API:
    generate_rig(vantage_coll, render_fidelity=False) -> dict (see docstring)
"""

import contextlib
import math

import bpy

from . import convention, frames, presets, validity


@contextlib.contextmanager
def render_fidelity_subdiv(scene):
    """Temporarily set SUBSURF viewport levels = render levels (never saved)."""
    touched = []
    for ob in scene.objects:
        for mod in getattr(ob, "modifiers", []):
            if mod.type == "SUBSURF" and mod.levels != mod.render_levels:
                touched.append((mod, mod.levels))
                mod.levels = mod.render_levels
    try:
        bpy.context.view_layer.update()
        yield
    finally:
        for mod, levels in touched:
            mod.levels = levels
        bpy.context.view_layer.update()


def _rig_fingerprint(vantage_coll):
    """Hash payload capturing everything the rig depends on."""
    def mesh_print(ob):
        return {
            "verts": len(ob.data.vertices),
            "sample": [
                [round(c, 3) for c in (ob.matrix_world @ v.co)]
                for v in list(ob.data.vertices)[::max(1, len(ob.data.vertices) // 64)]
            ],
        }

    def coll_print(coll, child):
        cfg = convention.read_config(coll, child=child)
        env = convention.env_object(coll)
        foc = convention.focus_object(coll)
        return {
            "config": cfg,
            "env": mesh_print(env) if env else None,
            "focus": [round(c, 3) for c in foc.matrix_world.translation] if foc else None,
        }

    payload = {"parent": coll_print(vantage_coll, False), "children": {}}
    for key, child in convention.find_children(vantage_coll).items():
        payload["children"][key] = coll_print(child, True)
    # the approval covers WHAT RENDERS: hiding/showing/moving scene geometry
    # changes both the validity result and the dataset — it must void the hash
    root = bpy.data.collections.get(convention.CAPTURE_ROOT)
    scene_sig = []
    for ob in validity.render_visible_objects(bpy.context.scene):
        if ob.type != "MESH" or (root is not None and validity._under_collection(ob, root)):
            continue
        mat = [round(v, 3) for row in ob.matrix_world for v in row]
        scene_sig.append([ob.name, len(ob.data.vertices), mat])
    payload["scene"] = sorted(scene_sig)
    return frames.contract_hash(payload)


# fixed oversampling factor: preview and export must draw the SAME candidate set
# (an adaptive 4x->8x flip would let their rigs diverge wholesale, since
# fibonacci_dirs(4n) and fibonacci_dirs(8n) share no directions)
OVERSAMPLE = 8


def _sample_shell(env, scene_bvh, focus, r, count, cfg, tol, phase,
                  target_object=None, check_env=True, height_floor=None):
    """One distance shell -> (accepted [(pos, dir)], reject tally). Deterministic.

    tol tightens every check for the coarse-terrain interactive preview: more
    required height/clearance/standoff, and a SMALLER los slack (a larger slack
    would loosen the LOS test — the one check where the sign flips).
    """
    tally = {"outside_env": 0, "below_terrain": 0, "low_height": 0,
             "clearance": 0, "standoff": 0, "los": 0}
    min_height = cfg["min_height_m"] if height_floor is None else height_floor
    los_slack = max(0.0, cfg["los_slack_m"] - tol)
    accepted = []
    if count <= 0:
        return accepted, tally
    for d in frames.fibonacci_dirs(count * OVERSAMPLE, phase):
        pos = (focus[0] + d[0] * r, focus[1] + d[1] * r, focus[2] + d[2] * r)
        if check_env and not env.contains(pos):
            tally["outside_env"] += 1
            continue
        h = scene_bvh.height_above_terrain(pos)
        if h is None:
            tally["below_terrain"] += 1
            continue
        if h < min_height + tol:
            tally["low_height"] += 1
            continue
        c, _who = scene_bvh.clearance(pos, within_m=cfg["clearance_m"] + tol + 1.0)
        if c is not None and c < cfg["clearance_m"] + tol:
            tally["clearance"] += 1
            continue
        if target_object:
            sd = scene_bvh.distance_to(pos, target_object,
                                       within_m=cfg["standoff_min_m"] + tol + 1.0)
            if sd is not None and sd < cfg["standoff_min_m"] + tol:
                tally["standoff"] += 1
                continue
        if cfg["require_los"] and scene_bvh.los_blocked(pos, focus, los_slack, target_object):
            tally["los"] += 1
            continue
        accepted.append((pos, d))
    if len(accepted) > count:
        keep = frames.farthest_point_downsample([a[1] for a in accepted], count)
        accepted = [accepted[i] for i in keep]
    return accepted, tally


def _sample_rig(rig_name, coll, scene_bvh, cfg, focus, tol, prefix,
                target_object=None):
    """All shells + margin samples for one rig -> (samples, shell_stats, warnings)."""
    env_ob = convention.env_object(coll)
    env = validity.EnvVolume(env_ob) if env_ob else None
    if env is None:
        return [], [], [f"{rig_name}: missing ENV — rig skipped"]

    shells = cfg["distance_shells_m"]
    counts = presets.shell_counts(cfg["views"], shells)
    samples, shell_stats, warnings = [], [], []
    idx = 0
    playback = []

    for si, (r, n) in enumerate(zip(shells, counts)):
        phase = 0.61803 * (cfg["seed"] + si)
        acc, tally = _sample_shell(env, scene_bvh, focus, r, n, cfg, tol, phase,
                                   target_object=target_object)
        az = [frames.alpha_deg_from_delta(frames.vec_sub(p, focus)) for p, _ in acc]
        shell_stats.append({
            "rig": rig_name, "shell_m": r, "requested": n, "kept": len(acc),
            "rejected": tally, "max_azimuth_gap_deg": round(frames.max_azimuth_gap_deg(az), 1),
        })
        if len(acc) < n * 0.8:
            warnings.append(
                f"{rig_name}: shell {r} m short {len(acc)}/{n} — grow ENV_{convention.vantage_name(coll)} "
                f"or relax min_height/clearance (rejections: "
                + ", ".join(f"{k}={v}" for k, v in tally.items() if v) + ")")
        for pos, _d in acc:
            samples.append(_mk_sample(f"{prefix}{idx:04d}.png", rig_name, "playback",
                                      r, pos, focus, cfg))
            playback.append(pos)
            idx += 1

    # dataset-only margins (ADDON.md §3): render past the playback envelope so
    # splat quality doesn't fall off exactly at the runtime clamp. NEVER exported
    # as viewer limits. Radius margins ride the outer/inner shells; the beta
    # margin ring sits train_margin_beta_deg BELOW the lowest playback ring
    # (i.e. beta_max + margin: closer to the horizon, the edge users push against).
    # Margins relax the height floor to half — a height-limited playback edge
    # (the flat-terrain norm) would otherwise reject every below-the-edge sample.
    margin_floor = max(cfg["clearance_m"], cfg["min_height_m"] * 0.5)
    n_margin = 0
    if playback and cfg["train_margin_radius_pct"] > 0:
        for r, frac in ((max(shells) * (1 + cfg["train_margin_radius_pct"] / 100.0), 3),
                        (min(shells) * (1 - cfg["train_margin_radius_pct"] / 100.0), 6)):
            n = max(4, cfg["views"] // (frac * 2))
            acc, _ = _sample_shell(env, scene_bvh, focus, r, n, cfg, tol,
                                   0.61803 * (cfg["seed"] + 17), target_object=target_object,
                                   check_env=False, height_floor=margin_floor)
            for pos, _d in acc:
                samples.append(_mk_sample(f"{prefix}{idx:04d}.png", rig_name, "margin",
                                          round(r, 2), pos, focus, cfg))
                idx += 1
                n_margin += 1
    if playback and cfg["train_margin_beta_deg"] > 0:
        beta_max = max(frames.beta_deg_from_delta(frames.vec_sub(p, focus)) for p in playback)
        beta = min(89.5, beta_max + cfg["train_margin_beta_deg"])
        r = sorted(shells)[len(shells) // 2]
        n = max(8, cfg["views"] // 8)
        los_slack = max(0.0, cfg["los_slack_m"] - tol)
        for i in range(n):
            a = 2 * math.pi * i / n + 0.61803 * cfg["seed"]
            sb, cb = math.sin(math.radians(beta)), math.cos(math.radians(beta))
            pos = (focus[0] + r * sb * math.cos(a), focus[1] + r * sb * math.sin(a),
                   focus[2] + r * cb)
            h = scene_bvh.height_above_terrain(pos)
            c, _ = scene_bvh.clearance(pos, within_m=cfg["clearance_m"] + tol + 1.0)
            if h is not None and h >= margin_floor + tol and (c is None or c >= cfg["clearance_m"] + tol):
                if not (cfg["require_los"] and scene_bvh.los_blocked(pos, focus, los_slack, target_object)):
                    samples.append(_mk_sample(f"{prefix}{idx:04d}.png", rig_name, "margin",
                                              r, pos, focus, cfg))
                    idx += 1
                    n_margin += 1
    if playback and n_margin == 0 and (
            cfg["train_margin_radius_pct"] > 0 or cfg["train_margin_beta_deg"] > 0):
        warnings.append(f"{rig_name}: margin pass yielded 0 views — the dataset will "
                        "end exactly at the playback envelope edge")
    return samples, shell_stats, warnings


def _mk_sample(name, rig_name, kind, shell, pos, focus, cfg):
    return {
        "name": name, "rig": rig_name, "kind": kind, "shell_m": shell,
        "pos": [round(c, 4) for c in pos],
        "rot": frames.look_at_rotation(pos, tuple(focus)),
        "resolution": cfg["resolution"], "focal_mm": cfg["focal_mm"],
        "sensor_mm": cfg["sensor_mm"], "samples": cfg["samples"],
    }


def generate_rig(vantage_coll, render_fidelity=False):
    """Sample the full rig for a vantage (parent + children + bridges).

    Returns {vantage, focus_blender, hash, assembly, samples[], shell_stats[],
    envelope, object_envelopes{}, warnings[], totals{}} — samples carry Blender
    world pos + world-from-camera rotation rows; the COLMAP/viewer conversion
    happens in frames.py at export time.
    """
    scene = bpy.context.scene
    # freshly created FOCUS/ENV objects report identity matrix_world until the
    # depsgraph runs once — a same-block create_vantage() -> generate_rig() flow
    # would otherwise sample around a stale transform
    bpy.context.view_layer.update()
    name = convention.vantage_name(vantage_coll)
    warnings = convention.validate_vantage(vantage_coll)
    cfg = convention.read_config(vantage_coll, child=False)
    foc_ob = convention.focus_object(vantage_coll)
    if foc_ob is None:
        raise ValueError(f"vantage {name!r} has no FOCUS empty")
    focus = tuple(foc_ob.matrix_world.translation)

    ctx = render_fidelity_subdiv(scene) if render_fidelity else contextlib.nullcontext()
    tol = 0.0 if render_fidelity else validity.TERRAIN_TOL_M
    with ctx:
        scene_bvh = validity.SceneGeo(exclude_root=bpy.data.collections.get(convention.CAPTURE_ROOT))
        h = scene_bvh.height_above_terrain(focus)
        if h is None:
            warnings.append(
                f"FOCUS_{name} has NO terrain below it — it is under the surface or "
                "off the tile; expect every candidate to be rejected. Snap the FOCUS "
                "to the surface (the panel's Create does this automatically).")
        elif h < -0.5:
            warnings.append(f"FOCUS_{name} sits {-h:.1f} m below the terrain surface")

        samples, shell_stats, w = _sample_rig(
            "parent", vantage_coll, scene_bvh, cfg, focus, tol, prefix="p")
        warnings += w
        playback_parent = [s for s in samples if s["kind"] == "playback"]

        object_envelopes = {}
        for key, child_coll in convention.find_children(vantage_coll).items():
            ccfg = convention.read_config(child_coll, child=True)
            cf_ob = convention.focus_object(child_coll)
            if cf_ob is None or not ccfg["target_object"]:
                warnings.append(f"child rig {key}: missing FOCUS or target_object — skipped")
                continue
            cfocus = tuple(cf_ob.matrix_world.translation)
            # keep the hyphens: stripping them could collide two distinct keys
            # ("boulder-001" vs "boulder001") into the same image names
            csamples, cstats, cw = _sample_rig(
                f"child:{key}", child_coll, scene_bvh, ccfg, cfocus, tol,
                prefix=f"c_{key}_", target_object=ccfg["target_object"])
            warnings += cw
            shell_stats += cstats
            samples += csamples

            cplay = [s for s in csamples if s["kind"] == "playback"]
            if cplay:
                deltas = [frames.vec_sub(tuple(s["pos"]), cfocus) for s in cplay]
                env_patch = frames.derive_envelope(deltas, ccfg["focal_mm"], ccfg["sensor_mm"])
                env_patch["look_at_m"] = [round(c, 3) for c in frames.viewer_from_blender(cfocus, focus)]
                object_envelopes[key] = env_patch

            # bridge shell: intermediate views between the parent and child scales
            # (training glue — safety-checked, exempt from both ENV volumes).
            if playback_parent and cplay and ccfg["bridge_views"] > 0:
                dmin = min(frames.vec_len(frames.vec_sub(tuple(s["pos"]), cfocus))
                           for s in playback_parent)
                r_b = math.sqrt(dmin * max(ccfg["distance_shells_m"]))
                acc, _ = _sample_shell(
                    validity.EnvVolume(convention.env_object(child_coll)), scene_bvh,
                    cfocus, r_b, ccfg["bridge_views"], ccfg, tol,
                    0.61803 * (ccfg["seed"] + 33),
                    target_object=ccfg["target_object"], check_env=False)
                for j, (pos, _d) in enumerate(acc):
                    samples.append(_mk_sample(
                        f"b_{key}_{j:04d}.png", f"child:{key}",
                        "bridge", round(r_b, 2), pos, cfocus, ccfg))

    envelope = None
    if playback_parent:
        deltas = [frames.vec_sub(tuple(s["pos"]), focus) for s in playback_parent]
        envelope = frames.derive_envelope(deltas, cfg["focal_mm"], cfg["sensor_mm"])

    totals = {}
    for s in samples:
        totals[s["kind"]] = totals.get(s["kind"], 0) + 1
    resolutions = {(s["resolution"], s["focal_mm"], s["sensor_mm"]) for s in samples}
    if len(resolutions) > 1:
        warnings.append(
            "mixed camera intrinsics across rigs (multi-camera COLMAP dataset — "
            "supported by the gsplat parser but not yet validated in this pipeline)")

    return {
        "vantage": name,
        "focus_blender": [round(c, 4) for c in focus],
        "hash": _rig_fingerprint(vantage_coll),
        "assembly": cfg["assembly"],
        "config": cfg,
        "samples": samples,
        "shell_stats": shell_stats,
        "envelope": envelope,
        "object_envelopes": object_envelopes,
        "totals": totals,
        "warnings": warnings,
    }
