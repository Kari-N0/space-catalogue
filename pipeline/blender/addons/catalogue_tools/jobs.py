"""Job status polling. Two sources, local first:

1. LOCAL renders (v0.2.0 default): headless Blender children launched by
   Execute on this machine — progress = png count in the output folder,
   done = clean exit + capture-meta.json present.
2. Repo jobs/<id>/status.json (ADDON.md §6) — WSL-side runs launched via the
   CLI (run_capture.py) on the dev machine.

Any read hiccup is swallowed; the next tick retries."""

import json
import os

import bpy

from . import prefs

# local render jobs: [{proc, vantage, out, total}] — newest last
_LOCAL = []


def track_local_job(proc, vantage, out_dir, total_images):
    _LOCAL.append({"proc": proc, "vantage": vantage, "out": out_dir,
                   "total": total_images})


def cancel_local_job():
    """Terminate the newest still-running local render. True if one was killed."""
    for job in reversed(_LOCAL):
        if job["proc"].poll() is None:
            job["proc"].terminate()
            return True
    return False


def _local_status():
    if not _LOCAL:
        return None
    j = _LOCAL[-1]
    rc = j["proc"].poll()
    img_dir = os.path.join(j["out"], "lichtFeld", "images")
    try:
        imgs = len([f for f in os.listdir(img_dir) if f.endswith(".png")])
    except OSError:
        imgs = 0
    if rc is None:
        state, msg = "running", f"rendering {imgs}/{j['total'] or '?'} images"
    elif rc == 0 and os.path.isfile(os.path.join(j["out"], "capture-meta.json")):
        state, msg = "done", f"dataset ready: {os.path.join(j['out'], 'lichtFeld')}"
    else:
        state, msg = "failed", f"exit {rc} — see {os.path.join(j['out'], 'render.log')}"
    return {"job_id": f"local · {j['vantage']}", "state": state,
            "stage": "render-dataset", "message": msg}


def _newest_status(repo_win):
    jobs_dir = os.path.join(repo_win, "jobs")
    try:
        entries = [d for d in os.listdir(jobs_dir) if d.endswith("-capture")]
    except OSError:
        return None
    for name in sorted(entries, reverse=True):
        try:
            with open(os.path.join(jobs_dir, name, "status.json")) as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
    return None


def _tick():
    try:
        p = prefs.get_prefs()
        st = bpy.context.window_manager.catalogue_tools
        doc = _local_status() or _newest_status(p.repo_windows)
        if doc:
            changed = (st.job_id != doc.get("job_id", "")
                       or st.job_state != doc.get("state", "")
                       or st.job_message != doc.get("message", ""))
            st.job_id = doc.get("job_id", "")
            st.job_state = doc.get("state", "")
            st.job_stage = doc.get("stage", "")
            st.job_message = doc.get("message", "")[:120]
            if changed:
                for window in bpy.context.window_manager.windows:
                    for area in window.screen.areas:
                        if area.type == "VIEW_3D":
                            area.tag_redraw()
        return max(1.0, p.poll_seconds)
    except Exception:
        return 5.0  # never let the timer die


def start():
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=2.0)


def ensure_timer():
    """Self-heal: extension upgrades can drop the timer — the panel calls this
    on every draw, so polling is guaranteed whenever the panel is visible."""
    start()


def stop():
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
