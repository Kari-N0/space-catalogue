"""N-panel UI — 3D viewport sidebar, tab "Catalogue" (ADDON.md §2).

Thin by construction: every button is a one-call operator into
pipeline.blender.capture; the panel also exposes the active vantage's key
custom properties directly (same id-props Kari can edit in
Properties ▸ Collection ▸ Custom Properties)."""

import bpy

# dynamic EnumProperty items must stay referenced module-side (bpy gotcha:
# returning fresh strings without holding them crashes/garbles the enum)
_ITEMS_CACHE = []


def vantage_items(_self, _context):
    global _ITEMS_CACHE
    try:
        names = sorted(
            c.name[len("CAPTURE_"):] for c in bpy.data.collections
            if c.name.startswith("CAPTURE_") and "__" not in c.name)
    except Exception:
        names = []
    _ITEMS_CACHE = ([(n, n, "capture") for n in names]
                    or [("NONE", "— no captures —", "create one below")])
    return _ITEMS_CACHE


class CatalogueToolsState(bpy.types.PropertyGroup):
    vantage: bpy.props.EnumProperty(name="Capture", items=vantage_items)
    new_name: bpy.props.StringProperty(
        name="Name", default="capture_01",
        description="letters, digits, '-' and '_' (no spaces, no double underscore)")
    last_hash: bpy.props.StringProperty()
    last_vantage: bpy.props.StringProperty()
    last_summary: bpy.props.StringProperty()
    job_id: bpy.props.StringProperty()
    job_state: bpy.props.StringProperty()
    job_stage: bpy.props.StringProperty()
    job_message: bpy.props.StringProperty()
    job_note: bpy.props.StringProperty()


class CATALOGUE_PT_capture(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Catalogue"
    bl_label = "Capture"

    def draw(self, context):
        layout = self.layout
        st = context.window_manager.catalogue_tools

        box = layout.box()
        box.label(text="Captures", icon="OUTLINER_COLLECTION")
        box.prop(st, "vantage", text="")
        row = box.row(align=True)
        row.prop(st, "new_name", text="Name")
        box.operator("catalogue.create_vantage", text="Create New Capture at Cursor", icon="ADD")
        sel = context.active_object.name if context.active_object else "—"
        box.operator("catalogue.add_child_rig", text=f"Add Child Rig ({sel})", icon="MESH_ICOSPHERE")

        coll = bpy.data.collections.get(f"CAPTURE_{st.vantage}")
        if coll is not None:
            props = layout.box()
            props.label(text=f"CAPTURE_{st.vantage}", icon="PROPERTIES")
            if "distance_shells_m" in coll.keys():
                props.prop(coll, '["distance_shells_m"]', text="camera distances (m)")
                props.operator("catalogue.fit_shells", icon="FULLSCREEN_ENTER")
            for key in ("views", "resolution", "samples", "min_height_m",
                        "clearance_m", "seed", "assembly"):
                if key in coll.keys():
                    props.prop(coll, f'["{key}"]', text=key)
            props.label(text="all knobs: Properties ▸ Collection", icon="INFO")

        box = layout.box()
        box.label(text="Preview (no rendering)", icon="HIDE_OFF")
        row = box.row(align=True)
        row.operator("catalogue.preview", icon="OVERLAY")
        row.operator("catalogue.clear_preview", text="", icon="TRASH")
        if st.last_hash:
            box.label(text=f"rig hash: {st.last_hash}  ({st.last_vantage})")
            for line in st.last_summary.split("\n"):
                if line:
                    box.label(text=line, icon="ERROR" if line.startswith("WARNING") else "NONE")

        box = layout.box()
        box.label(text="Execute", icon="RENDER_ANIMATION")
        if bpy.data.is_dirty:
            box.label(text="save the file first (hash = saved file)", icon="ERROR")
        elif not st.last_hash:
            box.label(text="run Preview first — its hash is the approval", icon="INFO")
        box.operator("catalogue.execute_capture",
                     text="Render + Build LichtFeld Dataset", icon="PLAY")

        box = layout.box()
        box.label(text="Job", icon="SORTTIME")
        if st.job_id:
            box.label(text=f"{st.job_id}: {st.job_state} / {st.job_stage}")
            if st.job_message:
                box.label(text=st.job_message)
            if st.job_state in ("queued", "running"):
                box.operator("catalogue.cancel_job", icon="CANCEL")
        else:
            box.label(text="no jobs yet")
        if st.job_note:
            box.label(text=st.job_note, icon="INFO")

        row = layout.row(align=True)
        row.operator("catalogue.export_envelope", icon="EXPORT")
        row.operator("catalogue.reload_pipeline", text="", icon="FILE_REFRESH")


CLASSES = (CatalogueToolsState, CATALOGUE_PT_capture)
