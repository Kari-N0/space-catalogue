"""Capture execute mode — WSL orchestrator (never imported in Blender; no ML
imports, training runs as a subprocess in the splat conda env).

    python3 pipeline/splats/run_capture.py --blend <path.blend> --vantage <name> \\
        --approved-rig <hash-from-preview> [--concept lunar-base] [--train-gsplat] \\
        [--skip-render] [--skip-sync] [--skip-train] [--dry-run]

Default flow (LichtFeld Studio, Kari 2026-07-14):
    render-dataset  blender-win.sh -b <blend> --python capture/export_dataset.py
                    -> D:\\renders\\<concept>\\capture\\<vantage>\\lichtFeld\\
                    (COLMAP text at the folder root + images/ + output/ — a
                    drag-and-drop LFS dataset; sparse/0/ twin keeps the same
                    folder valid for gsplat)
    report          provenance + envelope sidecar finalized; Kari drops the
                    lichtFeld folder into LichtFeld Studio, trains, cleans
                    (crop/clean ONLY), exports .sog. LFS runs natively on
                    Windows against D:\\ — the ext4 rule only governs WSL-side
                    training I/O.

--train-gsplat (validation/automation path):
    + sync-dataset  pipeline/blender/sync-dataset.sh <concept>/capture/<vantage>
                    (training I/O on ext4, never /mnt/*)
    + train-splat   gsplat simple_trainer.py mcmc, preset params from capture-meta,
                    ALWAYS with --no-normalize-world-space (frame contract:
                    normalization would bake a recenter+rescale+PCA rotation into
                    the PLY and break the meter-true envelope); PLY copied to D:\\

GATE: --approved-rig is required (the hash preview printed after Kari's go);
export_dataset.py re-derives the rig and refuses on any mismatch.

Job directory contract = ADDON.md §6 (the future Catalogue Tools panel polls
status.json unchanged): jobs/<yyyymmdd-hhmmss>-capture/{status.json, params.json,
control, log.txt}. Write "cancel" into control to stop between stages.

Importable API: run_capture(blend, vantage, approved_rig, ...) -> report dict
"""

import argparse
import datetime as _dt
import json
import os
import shutil
import struct
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SPLAT_PY = os.path.expanduser("~/miniconda3/envs/splat/bin/python")
GSPLAT_EXAMPLES = os.path.expanduser("~/apps/gsplat/examples")


class Job:
    """ADDON.md §6 job directory: atomic status.json + params + control + log."""

    def __init__(self, kind, params, stages):
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.job_id = f"{stamp}-{kind}"
        self.dir = os.path.join(REPO, "jobs", self.job_id)
        os.makedirs(self.dir, exist_ok=True)
        self.kind = kind
        self.stages = stages
        self.started = _dt.datetime.now().astimezone().isoformat(timespec="seconds")
        self.log_path = os.path.join(self.dir, "log.txt")
        with open(os.path.join(self.dir, "params.json"), "w") as fh:
            json.dump(params, fh, indent=2)
        with open(os.path.join(self.dir, "control"), "w") as fh:
            fh.write("continue")
        self.status(state="queued", stage=stages[0], message="starting")

    def status(self, state, stage, message, progress=-1, metrics=None):
        doc = {
            "job_id": self.job_id, "kind": self.kind, "state": state,
            "stage": stage, "stages": self.stages, "progress": progress,
            "message": message, "metrics": metrics or {}, "gate": None,
            "pid": os.getpid(), "started_at": self.started,
            "updated_at": _dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        tmp = os.path.join(self.dir, "status.json.tmp")
        with open(tmp, "w") as fh:
            json.dump(doc, fh, indent=2)
        os.replace(tmp, os.path.join(self.dir, "status.json"))

    def cancelled(self):
        try:
            with open(os.path.join(self.dir, "control")) as fh:
                return fh.read().strip() == "cancel"
        except OSError:
            return False

    def run(self, stage, cmd, cwd=None):
        """Run a subprocess, teeing output to console + log, status on the way."""
        self.status("running", stage, " ".join(map(str, cmd))[:200])
        with open(self.log_path, "a") as log:
            log.write(f"\n===== {stage}: {' '.join(map(str, cmd))}\n")
            proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True,
                                    errors="replace")
            last_update = 0.0
            for line in proc.stdout:
                sys.stdout.write(line)
                log.write(line)
                now = _dt.datetime.now().timestamp()
                if now - last_update > 5:
                    self.status("running", stage, line.strip()[:200])
                    last_update = now
            proc.wait()
        if proc.returncode != 0:
            self.status("failed", stage, f"exit code {proc.returncode}")
            raise SystemExit(f"{stage} failed (exit {proc.returncode}); log: {self.log_path}")


def ply_vertex_count(path):
    """'element vertex N' from a PLY header (no deps)."""
    with open(path, "rb") as fh:
        while True:
            line = fh.readline()
            if not line or line.strip() == b"end_header":
                return None
            if line.startswith(b"element vertex"):
                return int(line.split()[-1])


def ply_count_within(path, center, radius):
    """Splats within radius of center (capture-frame meters). Pure-python binary
    PLY walk over float32 properties — a few seconds at 1M splats."""
    with open(path, "rb") as fh:
        n, props, fmt_le = None, [], True
        while True:
            raw = fh.readline()
            if not raw:  # truncated header: never spin on EOF
                return None
            line = raw.strip()
            if line.startswith(b"format"):
                fmt_le = b"little" in line
            elif line.startswith(b"element vertex"):
                n = int(line.split()[-1])
            elif line.startswith(b"property float") and n is not None:
                props.append(line.split()[-1])
            elif line == b"end_header":
                break
        if not fmt_le or n is None or props[:3] != [b"x", b"y", b"z"]:
            return None
        stride = len(props) * 4
        cx, cy, cz = center
        r2 = radius * radius
        count = 0
        chunk_rows = 65536
        unpack = struct.Struct(f"<{len(props)}f").unpack_from
        for start in range(0, n, chunk_rows):
            rows = min(chunk_rows, n - start)
            buf = fh.read(rows * stride)
            for off in range(0, rows * stride, stride):
                x, y, z = unpack(buf, off)[:3]
                dx, dy, dz = x - cx, y - cy, z - cz
                if dx * dx + dy * dy + dz * dz <= r2:
                    count += 1
        return count


def _val_psnr(result_dir):
    """PSNR of the LATEST eval step (numeric sort — lexicographic would pick
    val_step9999 over val_step19999)."""
    stats_dir = os.path.join(result_dir, "stats")
    if not os.path.isdir(stats_dir):
        return None
    val = [n for n in os.listdir(stats_dir) if n.startswith("val") and n.endswith(".json")]
    val.sort(key=lambda n: int("".join(ch for ch in n if ch.isdigit()) or 0))
    if not val:
        return None
    with open(os.path.join(stats_dir, val[-1])) as fh:
        return json.load(fh).get("psnr")


def run_capture(blend, vantage, approved_rig, concept="lunar-base",
                skip_render=False, skip_sync=False, skip_train=False,
                train_gsplat=False, dry_run=False):
    if not approved_rig:
        raise SystemExit(
            "refusing to start: --approved-rig <hash> is required (run preview in "
            "Blender, get Kari's go, use the hash from the stats readout)")
    blend = os.path.abspath(blend)
    if not os.path.isfile(blend):
        raise SystemExit(f"blend not found: {blend}")

    scene_id = f"{concept}/capture/{vantage}"
    stage_dir = f"/mnt/d/renders/{scene_id}"          # Windows staging (never C:)
    lfs_dir = os.path.join(stage_dir, "lichtFeld")    # drop-in for LichtFeld Studio
    # optional gsplat path: the synced lichtFeld/ folder doubles as a standard
    # COLMAP root (it carries a sparse/0/ twin of the root text files)
    data_dir = os.path.expanduser(f"~/datasets/{scene_id}/lichtFeld")
    result_dir = os.path.expanduser(f"~/datasets/{scene_id}/results")

    if train_gsplat:
        train_plan = (f"  sync:    -> {data_dir}\n  train:   gsplat mcmc (splat env, "
                      f"--no-normalize-world-space pinned)\n"
                      f"  ply:     -> {stage_dir}/<vantage>_<preset>.ply")
    else:
        train_plan = (f"  train:   LichtFeld Studio (Kari): drop "
                      f"D:\\renders\\{scene_id.replace('/', chr(92))}\\lichtFeld into LFS")
    plan = (f"capture execute plan\n  blend:   {blend}\n  vantage: {vantage}\n"
            f"  render:  {lfs_dir} (via blender-win.sh, Windows Cycles/OptiX)\n{train_plan}")
    print(plan)
    if dry_run:
        return {"plan": plan}

    stages = (["render-dataset", "sync-dataset", "train-splat", "report"]
              if train_gsplat else ["render-dataset", "report"])
    job = Job("capture", {"blend": blend, "vantage": vantage, "concept": concept,
                          "approved_rig": approved_rig, "train_gsplat": train_gsplat},
              stages)
    print(f"job: {job.job_id} (status: jobs/{job.job_id}/status.json)")

    # ---- render-dataset ---------------------------------------------------
    if not skip_render:
        # blender-win.sh only wslpath-converts absolute args whose path exists:
        # the out dir MUST exist before the call (contract with export_dataset.py)
        os.makedirs(stage_dir, exist_ok=True)
        job.run("render-dataset", [
            os.path.join(REPO, "pipeline/blender/blender-win.sh"),
            # factory-startup: user add-ons (MCP server etc.) must not load into
            # headless render jobs — a lingering add-on thread kept blender.exe
            # alive after the 2026-07-13 rehearsal render finished, deadlocking
            # this orchestrator. export_dataset.py sets all its own prefs.
            "--factory-startup", "-b", blend,
            # without this Blender exits 0 on Python exceptions — the approval
            # gate's refusal (and any mid-render crash) would be invisible here
            "--python-exit-code", "1",
            "--python", os.path.join(REPO, "pipeline/blender/capture/export_dataset.py"),
            "--", "--vantage", vantage, "--out", stage_dir,
            "--approved-rig", approved_rig, "--concept", concept,
        ])
    meta_path = os.path.join(stage_dir, "capture-meta.json")
    if not os.path.isfile(meta_path):
        job.status("failed", "render-dataset", "capture-meta.json missing")
        raise SystemExit(f"no capture-meta.json at {meta_path}")
    with open(meta_path) as fh:
        meta = json.load(fh)
    if meta.get("rig_hash") != approved_rig:
        job.status("failed", "render-dataset",
                   f"stale dataset: meta rig hash {meta.get('rig_hash')} != approved")
        raise SystemExit(
            f"capture-meta.json carries rig hash {meta.get('rig_hash')}, not the approved "
            f"{approved_rig} — stale dataset from an earlier run? Re-render without --skip-render.")
    try:
        n_img = len([f for f in os.listdir(os.path.join(lfs_dir, "images"))
                     if f.endswith(".png")])
    except FileNotFoundError:
        job.status("failed", "render-dataset", "lichtFeld/images/ directory missing")
        raise SystemExit(f"no images under {lfs_dir} (did --skip-render skip a fresh dir?)")
    if n_img != meta["images"]:
        job.status("failed", "render-dataset", f"{n_img}/{meta['images']} images")
        raise SystemExit(f"image count mismatch: {n_img} on disk vs {meta['images']} in meta")

    prov_dir = os.path.join(REPO, "pipeline/provenance", concept)
    os.makedirs(prov_dir, exist_ok=True)
    win_lfs = "D:\\" + lfs_dir[len("/mnt/d/"):].replace("/", "\\")

    if not train_gsplat:
        # ---- LichtFeld Studio handoff (default flow, Kari 2026-07-14) --------
        job.status("running", "report", "finalizing LFS handoff")
        with open(os.path.join(stage_dir, "capture-provenance.json")) as fh:
            prov = json.load(fh)
        prov_path = os.path.join(prov_dir, f"capture-{vantage}.json")
        if os.path.isfile(prov_path):
            with open(prov_path) as fh:
                old = json.load(fh)
            prov["stages"].extend(
                s for s in old.get("stages", [])
                if s.get("stage") not in ("render-dataset", "train-splat"))
        prov["pending_stages"] = [
            "lichtfeld-train+clean (Kari, LichtFeld Studio GPLv3 — license checked "
            "2026-07-14: gsplat/Apache-2.0 rasterizer lineage, Inria listed as research "
            "citation only in THIRD_PARTY_LICENSES.md; no non-commercial deps found. "
            "Editing rule: clean/crop ONLY — never rotate/translate/set-pivot)",
            "sog-export (LichtFeld Studio; record LFS version + export settings here; "
            "VERIFY first export: meter-true scale + orientation in the web viewer — "
            "no world normalization may be baked in)",
        ]
        with open(prov_path, "w") as fh:
            json.dump(prov, fh, indent=2)
        with open(os.path.join(prov_dir, f"capture-{vantage}.envelope.json"), "w") as fh:
            json.dump({k: meta[k] for k in
                       ("concept", "vantage", "generated", "blend_file", "rig_hash",
                        "envelope", "object_envelopes")}, fh, indent=2)
        report = {"job": job.job_id, "lichtfeld_folder": win_lfs, "images": n_img,
                  "provenance": prov_path}
        job.status("done", "report", f"dataset ready for LichtFeld Studio: {win_lfs}",
                   progress=1.0, metrics={"images": n_img})
        print("\nCAPTURE DATASET READY (LichtFeld Studio flow)")
        print(f"  drop this folder into LFS:  {win_lfs}")
        print(f"  images: {n_img}   provenance: {prov_path}")
        print("  LFS rules: train, then clean/crop ONLY — never rotate/translate/"
              "set-pivot; export .sog (the frame IS the contract)")
        return report

    if job.cancelled():
        job.status("cancelled", "sync-dataset", "cancelled via control file")
        return {"cancelled": True}

    # ---- sync-dataset -------------------------------------------------------
    if not skip_sync:
        job.run("sync-dataset", [os.path.join(REPO, "pipeline/blender/sync-dataset.sh"),
                                 scene_id])
    if job.cancelled():
        job.status("cancelled", "train-splat", "cancelled via control file")
        return {"cancelled": True}

    # ---- train-splat --------------------------------------------------------
    max_steps = meta["trainer"]["max_steps"]
    if not skip_train:
        job.run("train-splat", [
            SPLAT_PY, "simple_trainer.py", "mcmc",
            "--data_dir", data_dir, "--data_factor", "1",
            "--result_dir", result_dir,
            "--max_steps", str(max_steps), "--save_ply", "--ply_steps", str(max_steps),
            # default eval steps are [7000, 30000] — without this the reported
            # PSNR would be an early checkpoint's, not the final model's
            "--eval_steps", str(max_steps),
            "--disable_viewer", "--strategy.cap-max", str(meta["trainer"]["cap_max"]),
            # frame contract: never let the trainer renormalize the world
            "--no-normalize-world-space",
        ], cwd=GSPLAT_EXAMPLES)
    if job.cancelled():
        job.status("cancelled", "report", "cancelled via control file")
        return {"cancelled": True}

    # ---- report -------------------------------------------------------------
    job.status("running", "report", "collecting artifacts")
    ply = os.path.join(result_dir, "ply", f"point_cloud_{max_steps - 1}.ply")
    if not os.path.isfile(ply):
        try:
            cand = os.listdir(os.path.join(result_dir, "ply"))
        except FileNotFoundError:
            cand = []
        # numeric, not lexicographic: point_cloud_9999 must lose to point_cloud_19999
        cand = sorted((f for f in cand if f.endswith(".ply")),
                      key=lambda f: int("".join(ch for ch in f if ch.isdigit()) or 0))
        if not cand:
            job.status("failed", "report", "no PLY produced")
            raise SystemExit("training produced no PLY")
        ply = os.path.join(result_dir, "ply", cand[-1])

    preset = meta["config"]["preset"]
    ply_out = os.path.join(stage_dir, f"{vantage}_{preset}.ply")
    shutil.copy2(ply, ply_out)

    total = ply_vertex_count(ply)
    metrics = {"splats_total": total, "psnr": _val_psnr(result_dir)}
    for key, oe in meta.get("object_envelopes", {}).items():
        v = oe["look_at_m"]
        # child focus in capture frame: viewer (x,y,z) -> capture (x,-y,z)
        near = ply_count_within(ply, (v[0], -v[1], v[2]), oe["distance_m"]["max"])
        if near is not None:
            metrics[f"splats_near_{key}"] = near

    # provenance finalize (hard rule: every generated asset)
    with open(os.path.join(stage_dir, "capture-provenance.json")) as fh:
        prov = json.load(fh)
    # re-running execute must not destroy stages appended after earlier runs
    # (SuperSplat/pack-sog entries recorded at SOG-swap time — the hard rule
    # says the SHIPPED asset's lineage lives in this file)
    prov_path = os.path.join(prov_dir, f"capture-{vantage}.json")
    if os.path.isfile(prov_path):
        with open(prov_path) as fh:
            old = json.load(fh)
        keep = [s for s in old.get("stages", [])
                if s.get("stage") not in ("render-dataset", "train-splat")]
        prov["stages"].extend(keep)
    gsplat_ver = subprocess.run(
        [SPLAT_PY, "-c", "import gsplat; print(gsplat.__version__)"],
        capture_output=True, text=True).stdout.strip()
    prov["stages"].append({
        "stage": "train-splat",
        "tool": f"gsplat {gsplat_ver} (git main, sm_89) simple_trainer.py mcmc",
        "flags": f"--max_steps {max_steps} --strategy.cap-max {meta['trainer']['cap_max']} "
                 "--data_factor 1 --no-normalize-world-space",
        "metrics": metrics,
        "license": "gsplat Apache-2.0; no Inria/graphdeco code (PLAN.md §5)",
    })
    prov["pending_stages"] = [
        "supersplat-clean (Kari, manual: clean/crop ONLY — never rotate/translate/set-pivot)",
        "pack-sog (splat-transform; record flags + input PLY here at SOG-swap time)",
    ]
    with open(prov_path, "w") as fh:
        json.dump(prov, fh, indent=2)
    with open(os.path.join(prov_dir, f"capture-{vantage}.envelope.json"), "w") as fh:
        json.dump({k: meta[k] for k in
                   ("concept", "vantage", "generated", "blend_file", "rig_hash",
                    "envelope", "object_envelopes")}, fh, indent=2)

    win_ply = "D:\\" + ply_out[len("/mnt/d/"):].replace("/", "\\")
    report = {
        "job": job.job_id, "ply_for_supersplat": win_ply, "metrics": metrics,
        "provenance": prov_path,
        "envelope_sidecar": os.path.join(prov_dir, f"capture-{vantage}.envelope.json"),
        "render_s": meta["timing"]["render_s"],
    }
    job.status("done", "report", f"PLY ready for SuperSplat: {win_ply}", progress=1.0,
               metrics=metrics)
    print("\nCAPTURE EXECUTE DONE")
    print(f"  PLY for SuperSplat:  {win_ply}")
    print(f"  splats: {metrics}")
    print(f"  provenance: {prov_path}")
    print("  SuperSplat rules: clean/crop ONLY — never rotate/translate/set-pivot "
          "(the frame IS the contract)")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--blend", required=True)
    ap.add_argument("--vantage", required=True)
    ap.add_argument("--approved-rig", default=None)
    ap.add_argument("--concept", default="lunar-base")
    ap.add_argument("--train-gsplat", action="store_true",
                    help="also sync + train with gsplat (validation path); "
                         "default is the LichtFeld Studio handoff")
    ap.add_argument("--skip-render", action="store_true")
    ap.add_argument("--skip-sync", action="store_true")
    ap.add_argument("--skip-train", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run_capture(args.blend, args.vantage, args.approved_rig, concept=args.concept,
                skip_render=args.skip_render, skip_sync=args.skip_sync,
                skip_train=args.skip_train, train_gsplat=args.train_gsplat,
                dry_run=args.dry_run)


if __name__ == "__main__":
    main()
