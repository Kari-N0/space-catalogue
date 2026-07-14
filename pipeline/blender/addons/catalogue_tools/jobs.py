"""Job status polling — reads the newest jobs/<id>/status.json (ADDON.md §6)
on a bpy.app.timers interval and mirrors it into the panel state. All reads go
over the \\\\wsl.localhost repo path; any hiccup is swallowed (next tick retries).
"""

import json
import os

import bpy

from . import prefs


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
        doc = _newest_status(p.repo_windows)
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


def stop():
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
