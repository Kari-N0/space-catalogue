"""Operators — thin wrappers over pipeline.blender.capture (ADDON.md §1 rule 1:
no logic forks into the add-on; everything here is glue + UI feedback).
ML stack is never imported (rule 2); Execute launches the WSL-side orchestrator
headless and the panel polls its status file (rule 3)."""

import os
import subprocess
import sys
import time

import bpy

from . import jobs, prefs


def capture_modules():
    """Capture pipeline modules — repo copy when available (dev machine,
    hot-reloadable), else the copy vendored inside this extension at build
    time (any other computer: just Blender + the add-on)."""
    repo = prefs.get_prefs().repo_windows
    try:
        if repo and os.path.isdir(repo):
            if repo not in sys.path:
                sys.path.insert(0, repo)
            from pipeline.blender.capture import (  # noqa: PLC0415
                _reload, convention, export_envelope, presets, preview,
            )
            return convention, preview, export_envelope, presets, _reload
    except ImportError:
        pass
    from .capture import (  # noqa: PLC0415  (vendored by build_addon)
        _reload, convention, export_envelope, presets, preview,
    )
    return convention, preview, export_envelope, presets, _reload


def export_script_path():
    """export_dataset.py for headless rendering — vendored copy if this is an
    installed extension, else the repo copy."""
    local = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "capture", "export_dataset.py")
    if os.path.isfile(local):
        return local
    return os.path.join(prefs.get_prefs().repo_windows,
                        "pipeline", "blender", "capture", "export_dataset.py")


def state(context):
    return context.window_manager.catalogue_tools


def active_vantage(context):
    convention = capture_modules()[0]
    name = state(context).vantage
    return convention.find_vantages().get(name)


class CATALOGUE_OT_create_vantage(bpy.types.Operator):
    """Create a capture vantage at the 3D cursor (ENV sphere + FOCUS empty)"""
    bl_idname = "catalogue.create_vantage"
    bl_label = "Create Vantage at Cursor"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        convention = capture_modules()[0]
        st = state(context)
        try:
            coll = convention.create_vantage(st.new_name.strip(),
                                             tuple(context.scene.cursor.location),
                                             snap_to_terrain_surface=True)
        except ValueError as err:
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}
        st.vantage = st.new_name.strip()
        foc = convention.focus_object(coll)
        z = foc.location.z if foc else 0.0
        self.report({"INFO"}, f"CAPTURE_{st.new_name.strip()} created, FOCUS snapped to "
                              f"terrain surface (z={z:.1f}) — move/scale ENV + FOCUS freely")
        return {"FINISHED"}


class CATALOGUE_OT_add_child_rig(bpy.types.Operator):
    """Add a close-up child rig auto-fitted to the selected object's bounds"""
    bl_idname = "catalogue.add_child_rig"
    bl_label = "Add Child Rig from Selected"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == "MESH"

    def execute(self, context):
        convention = capture_modules()[0]
        vantage = active_vantage(context)
        if vantage is None:
            self.report({"ERROR"}, "no active capture")
            return {"CANCELLED"}
        try:
            coll = convention.create_child_rig(convention.vantage_name(vantage),
                                               context.active_object.name)
        except ValueError as err:
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}
        self.report({"INFO"}, f"{coll.name} created")
        return {"FINISHED"}


class CATALOGUE_OT_preview(bpy.types.Operator):
    """Sample the rig, spawn frustum markers, print stats (nothing renders)"""
    bl_idname = "catalogue.preview"
    bl_label = "Preview Rig"

    def execute(self, context):
        convention, preview_mod = capture_modules()[:2]
        vantage = active_vantage(context)
        if vantage is None:
            self.report({"ERROR"}, "no active capture")
            return {"CANCELLED"}
        st = state(context)
        context.window.cursor_set("WAIT")
        try:
            result = preview_mod.run_preview(convention.vantage_name(vantage))
        except Exception as err:  # surfaced in UI, full trace in console
            self.report({"ERROR"}, f"preview failed: {err}")
            return {"CANCELLED"}
        finally:
            context.window.cursor_set("DEFAULT")
        st.last_hash = result["hash"]
        st.last_vantage = result["vantage"]
        st.total_images = sum(result["totals"].values())
        e = result["envelope"] or {}
        dist = e.get("distance_m", {})
        ud = e.get("angle_up_down_deg", {})
        lines = [f"views: " + "  ".join(f"{k}={v}" for k, v in sorted(result["totals"].items())),
                 f"envelope: {dist.get('min')}–{dist.get('max')} m, "
                 f"up/down {ud.get('min')}–{ud.get('max')}°"]
        for key in result.get("object_envelopes", {}):
            lines.append(f"zoom rig: {key}")
        lines += [f"WARNING: {w}" for w in result["warnings"]]
        st.last_summary = "\n".join(lines)
        # freshly rebuilt markers must respect the panel's display mode/scale
        preview_mod.set_marker_display(st.vantage, st.marker_mode, st.marker_scale)
        self.report({"INFO"},
                    f"rig {result['hash']} — full stats in text block "
                    f"CAPTURE_STATS_{result['vantage']}")
        return {"FINISHED"}


class CATALOGUE_OT_clear_preview(bpy.types.Operator):
    """Remove this vantage's preview markers"""
    bl_idname = "catalogue.clear_preview"
    bl_label = "Clear Preview"

    def execute(self, context):
        convention, preview_mod = capture_modules()[:2]
        vantage = active_vantage(context)
        if vantage is None:
            return {"CANCELLED"}
        preview_mod.clear_preview(convention.vantage_name(vantage))
        return {"FINISHED"}


class CATALOGUE_OT_execute_capture(bpy.types.Operator):
    """Render the approved rig headless and build the LichtFeld dataset folder"""
    bl_idname = "catalogue.execute_capture"
    bl_label = "Execute Capture (renders!)"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    @classmethod
    def poll(cls, context):
        st = context.window_manager.catalogue_tools
        return bool(st.last_hash) and not bpy.data.is_dirty

    def execute(self, context):
        st = state(context)
        p = prefs.get_prefs()
        if st.vantage != st.last_vantage:
            self.report({"ERROR"}, f"preview hash belongs to '{st.last_vantage}' — "
                                   "re-run Preview for this vantage")
            return {"CANCELLED"}
        out_win = st.output_dir.strip().rstrip("\\/")
        if not out_win:
            self.report({"ERROR"}, "set the Output folder first (always user-specified)")
            return {"CANCELLED"}
        if p.block_c_drive and out_win.lower().startswith("c:"):
            self.report({"ERROR"}, "staging on C: is blocked (add-on preferences) — "
                                   "pick another drive")
            return {"CANCELLED"}
        vantage = active_vantage(context)
        if vantage is not None:
            vantage["output_dir"] = out_win  # remembered per capture

        # WINDOWS-NATIVE launch (v0.2.0): render with THIS machine's own Blender
        # (bpy.app.binary_path) running the vendored export script — no WSL, no
        # repo needed; works on any computer the add-on is installed on. The
        # child process outlives Blender closing normally (Windows doesn't kill
        # children on parent exit); render log lives next to the dataset.
        script = export_script_path()
        if not os.path.isfile(script):
            self.report({"ERROR"}, f"export script not found: {script}")
            return {"CANCELLED"}
        try:
            os.makedirs(out_win, exist_ok=True)
            log = open(os.path.join(out_win, "render.log"), "a")
        except OSError as err:
            self.report({"ERROR"}, f"cannot create output folder: {err}")
            return {"CANCELLED"}
        proc = subprocess.Popen(
            [bpy.app.binary_path, "--factory-startup", "-b", bpy.data.filepath,
             "--python-exit-code", "1", "--python", script, "--",
             "--vantage", st.vantage, "--out", out_win,
             "--approved-rig", st.last_hash],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        log.close()  # the child holds its own handle
        jobs.track_local_job(proc, st.vantage, out_win, st.total_images)
        time.sleep(2)  # instant deaths (bad args, unwritable out) surface here
        rc = proc.poll()
        if rc is not None and rc != 0:
            self.report({"ERROR"}, f"render process died (exit {rc}) — see "
                                   f"{os.path.join(out_win, 'render.log')}")
            return {"CANCELLED"}
        st.job_note = f"launched: {st.vantage} @ {st.last_hash}"
        self.report({"INFO"}, "render running on this machine's Blender — progress below; "
                              "survives closing this Blender window")
        return {"FINISHED"}


class CATALOGUE_OT_cancel_job(bpy.types.Operator):
    """Ask the running capture job to stop between stages"""
    bl_idname = "catalogue.cancel_job"
    bl_label = "Cancel Job"

    def execute(self, context):
        st = state(context)
        if jobs.cancel_local_job():
            self.report({"INFO"}, "local render terminated")
            return {"FINISHED"}
        if not st.job_id or st.job_id.startswith("local"):
            return {"CANCELLED"}
        control = os.path.join(prefs.get_prefs().repo_windows, "jobs", st.job_id, "control")
        try:
            with open(control, "w") as fh:
                fh.write("cancel")
        except OSError as err:
            self.report({"ERROR"}, f"cannot write control file: {err}")
            return {"CANCELLED"}
        self.report({"INFO"}, "cancel requested (takes effect between stages)")
        return {"FINISHED"}


class CATALOGUE_OT_export_envelope(bpy.types.Operator):
    """Write this vantage's envelope sidecar JSON (no rendering)"""
    bl_idname = "catalogue.export_envelope"
    bl_label = "Export Envelope Sidecar"

    def execute(self, context):
        convention, _pv, export_envelope = capture_modules()[:3]
        vantage = active_vantage(context)
        if vantage is None:
            self.report({"ERROR"}, "no active capture")
            return {"CANCELLED"}
        name = convention.vantage_name(vantage)
        out = os.path.join(prefs.get_prefs().repo_windows, "pipeline", "provenance",
                           "lunar-base", f"capture-{name}.envelope.json")
        try:
            export_envelope.export_envelope(name, out_path=out)
        except Exception as err:
            self.report({"ERROR"}, f"export failed: {err}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"sidecar written: capture-{name}.envelope.json")
        return {"FINISHED"}


def _view_through_camera(context):
    for area in context.window.screen.areas:
        if area.type == "VIEW_3D":
            for space in area.spaces:
                if space.type == "VIEW_3D":
                    space.region_3d.view_perspective = "CAMERA"
            return


class CATALOGUE_OT_camera_look(bpy.types.Operator):
    """Pose the preview camera at the rig sample and look through it
    (step: -1 previous / 0 current / +1 next)"""
    bl_idname = "catalogue.camera_look"
    bl_label = "Look Through Camera"

    step: bpy.props.IntProperty(default=0)

    def execute(self, context):
        _c, preview_mod = capture_modules()[:2]
        st = state(context)
        if st.vantage in ("", "NONE"):
            self.report({"ERROR"}, "no active capture")
            return {"CANCELLED"}
        try:
            st.cam_index += self.step
            cam, sample, total = preview_mod.ensure_preview_camera(st.vantage, st.cam_index)
        except ValueError as err:
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}
        st.cam_index %= total
        st.cam_info = (f"{st.cam_index + 1}/{total}  {sample['rig']} · {sample['kind']}"
                       f" · shell {sample['shell_m']} m · {sample['name']}")
        _view_through_camera(context)
        return {"FINISHED"}


class CATALOGUE_OT_camera_apply(bpy.types.Operator):
    """Write this camera's lens + clip start/end back into the capture
    (changes the rig — re-run Preview for a fresh approval hash)"""
    bl_idname = "catalogue.camera_apply"
    bl_label = "Apply Lens/Clips to Capture"

    def execute(self, context):
        _c, preview_mod = capture_modules()[:2]
        st = state(context)
        try:
            coll_name, values = preview_mod.apply_camera_to_capture(st.vantage)
        except ValueError as err:
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}
        st.last_hash = ""  # camera config changed — previous approval is void
        st.total_images = 0
        self.report({"INFO"}, f"{coll_name}: " +
                    ", ".join(f"{k}={v}" for k, v in values.items()) + " — re-run Preview")
        return {"FINISHED"}


class CATALOGUE_OT_test_render(bpy.types.Operator):
    """Render ONE frame from the preview camera with the dataset's render
    settings (resolution/samples) and the scene's own look + compositing —
    for setting up the final look before executing the full capture"""
    bl_idname = "catalogue.test_render"
    bl_label = "Test Render This Camera"

    def execute(self, context):
        _c, preview_mod = capture_modules()[:2]
        st = state(context)
        try:
            cam, sample, _total = preview_mod.ensure_preview_camera(st.vantage, st.cam_index)
        except ValueError as err:
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}
        from pipeline.blender.capture.export_dataset import _setup_cycles
        scene = context.scene
        _setup_cycles(scene)
        # persistent data is for the headless batch loop ONLY: interactively it
        # pins the whole Cycles scene in VRAM after the render and starves the
        # viewport (blacks out on heavy terrain). One test frame gains nothing.
        scene.render.use_persistent_data = False
        scene.render.resolution_x = sample["resolution"]
        scene.render.resolution_y = sample["resolution"]
        scene.cycles.samples = sample["samples"]
        scene.camera = cam
        bpy.ops.render.render("INVOKE_DEFAULT")
        self.report({"INFO"}, f"test render: {sample['name']} @ {sample['resolution']}px "
                              f"/{sample['samples']}smp — scene look + compositing apply "
                              "exactly as in the final dataset")
        return {"FINISHED"}


class CATALOGUE_OT_set_ground(bpy.types.Operator):
    """Use the currently selected mesh objects as this capture's ground
    (min-height reference) — select all your terrain tiles, then click"""
    bl_idname = "catalogue.set_ground"
    bl_label = "Set Selected as Ground"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return any(o.type == "MESH" for o in context.selected_objects)

    def execute(self, context):
        vantage = active_vantage(context)
        if vantage is None:
            self.report({"ERROR"}, "no active capture")
            return {"CANCELLED"}
        names = [o.name for o in context.selected_objects
                 if o.type == "MESH" and not o.name.startswith(
                     ("ENV_", "FOCUS_", "PRV_", "CAPCAM_"))]
        if not names:
            self.report({"ERROR"}, "selection has no usable meshes (capture helpers don't count)")
            return {"CANCELLED"}
        vantage["ground_objects"] = ";".join(sorted(names))
        self.report({"INFO"}, f"ground = {len(names)} object(s): " + ", ".join(sorted(names)[:4])
                    + ("…" if len(names) > 4 else "") + " — re-run Preview")
        return {"FINISHED"}


class CATALOGUE_OT_clear_ground(bpy.types.Operator):
    """Back to automatic ground (any mesh named terrain*)"""
    bl_idname = "catalogue.clear_ground"
    bl_label = "Clear Ground Selection"

    def execute(self, context):
        vantage = active_vantage(context)
        if vantage is None:
            return {"CANCELLED"}
        vantage["ground_objects"] = ""
        vantage["ground_object"] = ""
        self.report({"INFO"}, "ground = automatic (terrain*) — re-run Preview")
        return {"FINISHED"}


class CATALOGUE_OT_fit_shells(bpy.types.Operator):
    """Fit this rig's camera distance shells to its own ENV's current size"""
    bl_idname = "catalogue.fit_shells"
    bl_label = "Fit Shells to ENV"
    bl_options = {"REGISTER", "UNDO"}

    coll_name: bpy.props.StringProperty()

    def execute(self, context):
        convention = capture_modules()[0]
        coll = bpy.data.collections.get(self.coll_name)
        if coll is None:
            self.report({"ERROR"}, f"collection {self.coll_name!r} not found")
            return {"CANCELLED"}
        old = [round(float(s), 2) for s in coll.get("distance_shells_m", [])]
        try:
            shells = convention.fit_shells_to_env(coll)
        except ValueError as err:
            self.report({"ERROR"}, str(err))
            return {"CANCELLED"}
        if old == [round(s, 2) for s in shells]:
            self.report({"INFO"}, "shells already fit this ENV — nothing changed")
        else:
            self.report({"INFO"}, f"{self.coll_name}: {old} → {shells} — re-run Preview")
        return {"FINISHED"}


class CATALOGUE_OT_toggle_section(bpy.types.Operator):
    """Expand/collapse this rig's settings"""
    bl_idname = "catalogue.toggle_section"
    bl_label = "Toggle Rig Settings"

    coll_name: bpy.props.StringProperty()

    def execute(self, _context):
        coll = bpy.data.collections.get(self.coll_name)
        if coll is not None:
            coll["_ui_open"] = not coll.get("_ui_open", False)
        return {"FINISHED"}


class CATALOGUE_OT_reload_pipeline(bpy.types.Operator):
    """Dev: reload the pipeline capture modules after edits on the WSL side"""
    bl_idname = "catalogue.reload_pipeline"
    bl_label = "Reload Pipeline Modules"

    def execute(self, _context):
        reload_mod = capture_modules()[4]
        reload_mod.reload_all()
        self.report({"INFO"}, "pipeline.blender.capture reloaded")
        return {"FINISHED"}


CLASSES = (
    CATALOGUE_OT_create_vantage,
    CATALOGUE_OT_add_child_rig,
    CATALOGUE_OT_preview,
    CATALOGUE_OT_clear_preview,
    CATALOGUE_OT_execute_capture,
    CATALOGUE_OT_cancel_job,
    CATALOGUE_OT_export_envelope,
    CATALOGUE_OT_set_ground,
    CATALOGUE_OT_clear_ground,
    CATALOGUE_OT_fit_shells,
    CATALOGUE_OT_toggle_section,
    CATALOGUE_OT_camera_look,
    CATALOGUE_OT_camera_apply,
    CATALOGUE_OT_test_render,
    CATALOGUE_OT_reload_pipeline,
)
