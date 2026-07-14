"""Capture authoring convention — bpy script (ML-free), Blender 5.1 / Python 3.13.

Scene layout (CAPTURE.md):

    capture                          (root collection)
      CAPTURE_<vantage>              (config = custom properties on this collection)
        ENV_<vantage>                (envelope volume mesh — Kari moves/scales it)
        FOCUS_<vantage>              (look-at empty = envelope target)
        PREVIEW_<vantage>            (transient markers, preview.py owns it)
        CAPTURE_<vantage>__<object>  (child rig; ENV/FOCUS suffixed the same way)

Importable API (the M2.5 add-on calls these in-process):
    ensure_capture_root() / find_vantages() / find_children(coll)
    create_vantage(name, focus, preset) / create_child_rig(vantage, object_name)
    read_config(coll, child=False) -> resolved config dict
    env_object(coll) / focus_object(coll) / vantage_name(coll)
    env_mesh_state(obj) -> 'ok'|'open'|'flipped'|'empty'
    validate_vantage(coll) -> [warning strings]
"""

import re

import bpy
import bmesh
from mathutils import Vector

from . import presets

CAPTURE_ROOT = "capture"
# letters/digits/underscore/hyphen; "__" is reserved as the child-rig separator
# (CAPTURE_<capture>__<object>) and therefore forbidden inside a name
NAME_RE = re.compile(r"^(?!.*__)[A-Za-z0-9_-]+$")
CHILD_SEP = "__"


def _link_once(parent, coll):
    if coll.name not in {c.name for c in parent.children}:
        parent.children.link(coll)


def _in_subtree(coll, root):
    """True when coll is root or any descendant collection of root."""
    if coll == root:
        return True
    return any(_in_subtree(coll, child) for child in root.children)


def ensure_capture_root(scene=None):
    scene = scene or bpy.context.scene
    root = bpy.data.collections.get(CAPTURE_ROOT)
    if root is None:
        root = bpy.data.collections.new(CAPTURE_ROOT)
    _link_once(scene.collection, root)
    root.hide_render = True  # nothing under capture/ ever renders
    return root


def vantage_name(coll):
    return coll.name[len("CAPTURE_"):]


def is_child_rig(coll):
    return CHILD_SEP in vantage_name(coll)


def find_vantages():
    """{vantage_name: collection} for top-level (non-child) CAPTURE_ collections."""
    return {
        vantage_name(c): c
        for c in bpy.data.collections
        if c.name.startswith("CAPTURE_") and not is_child_rig(c)
    }


def find_children(vantage_coll):
    """{target_key: collection} for child rigs nested under a vantage."""
    prefix = vantage_coll.name + CHILD_SEP
    return {
        c.name[len(prefix):]: c
        for c in vantage_coll.children
        if c.name.startswith(prefix)
    }


def env_object(coll):
    return coll.objects.get("ENV_" + vantage_name(coll))


def focus_object(coll):
    return coll.objects.get("FOCUS_" + vantage_name(coll))


def no_render_footprint(ob):
    """Make a helper object completely invisible to render engines — including
    the RENDERED VIEWPORT shading, where hide_render alone doesn't apply and a
    'hidden' ENV sphere would still block light and cast shadows."""
    ob.hide_render = True
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy",
                 "visible_transmission", "visible_volume_scatter", "visible_shadow"):
        if hasattr(ob, attr):
            setattr(ob, attr, False)


def _new_env_sphere(name, center, radius):
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=radius)
    bm.to_mesh(mesh)
    bm.free()
    ob = bpy.data.objects.new(name, mesh)
    ob.location = Vector(center)
    ob.display_type = "WIRE"
    no_render_footprint(ob)
    ob.color = (0.2, 0.55, 1.0, 1.0)
    return ob


def _new_focus_empty(name, location):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = "PLAIN_AXES"
    ob.empty_display_size = 2.0
    ob.location = Vector(location)
    ob.hide_render = True
    return ob


_PROP_UI = {
    "preset": "draft | standard | hero (CAPTURE.md preset table)",
    "views": "view count for this rig; 0 = preset default",
    "resolution": "square render size in px; 0 = preset default",
    "samples": "Cycles samples per view; 0 = preset default",
    "distance_shells_m": "camera distance shells from FOCUS, meters",
    "min_height_m": "min camera height above terrain (m); keep >= 5 (subdiv tolerance +-2)",
    "clearance_m": "min camera distance from any render geometry (m)",
    "require_los": "reject cameras whose view of FOCUS is blocked",
    "los_slack_m": "obstruction within this distance of FOCUS doesn't count (m)",
    "train_margin_radius_pct": "dataset-only radius margin percent (never viewer limits)",
    "train_margin_beta_deg": "dataset-only extra ring this many deg below lowest playback ring",
    "focal_mm": "rig camera focal length (mm) — becomes the page's zoom FOV",
    "sensor_mm": "rig camera sensor width (mm)",
    "clip_start_m": "camera clip start (m) — evaluate with the camera preview",
    "clip_end_m": "camera clip end (m) — must exceed the farthest visible terrain",
    "assembly": "merged | separate (how child rigs combine at training time)",
    "ground_object": "explicit ground mesh for min-height ('' = any terrain* mesh)",
    "ground_objects": "semicolon-separated ground mesh names for min-height "
                      "('' = any terrain* mesh); set via the panel from selection",
    "seed": "rotates the sampling spiral; same seed = identical rig",
    "target_object": "object this child rig orbits (read-only by convention)",
    "standoff_min_m": "min camera distance from the target object's surface (m)",
}


def _write_props(coll, values):
    """Write every config key explicitly so all knobs are visible/editable in
    Properties > Collection > Custom Properties (tooltips via id_properties_ui)."""
    for key, val in values.items():
        coll[key] = val
        desc = _PROP_UI.get(key)
        if desc:
            try:
                coll.id_properties_ui(key).update(description=desc)
            except TypeError:
                pass  # non-rna-idprop types (strings/bools pre-5.x quirks)


def snap_to_terrain(point, clearance=1.5):
    """(x, y, terrain_surface_z + clearance) at the point's x,y — raycast from
    high above against render-visible terrain-named objects. Returns the input
    unchanged when no terrain is hit (off-tile). Guards the classic trap: the
    3D cursor sits at z=0 while the surface is hundreds of meters up."""
    deps = bpy.context.evaluated_depsgraph_get()
    best = None
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH" or ob.hide_render:
            continue
        if not ob.name.lower().startswith("terrain"):
            continue
        inv = ob.matrix_world.inverted()
        hit, loc, _n, _i = ob.ray_cast(
            inv @ Vector((point[0], point[1], 1.0e5)),
            (inv.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized(), depsgraph=deps)
        if hit:
            z = (ob.matrix_world @ loc).z
            best = z if best is None else max(best, z)
    if best is None:
        return tuple(point)
    return (point[0], point[1], best + clearance)


def create_vantage(name, focus, preset="draft", snap_to_terrain_surface=False):
    """Create CAPTURE_<name> with default ENV sphere + FOCUS empty. Returns the
    collection. Kari then moves/scales ENV and FOCUS freely. views/resolution/
    samples are written as explicit resolved numbers (directly editable — no
    0-means-preset sentinels on freshly created vantages)."""
    if not NAME_RE.match(name):
        raise ValueError(f"capture name: letters, digits, - and _ (no double underscore): {name!r}")
    if preset not in presets.PRESETS:
        raise ValueError(f"unknown preset {preset!r}")
    root = ensure_capture_root()
    coll_name = "CAPTURE_" + name
    if bpy.data.collections.get(coll_name):
        raise ValueError(f"{coll_name} already exists")
    if snap_to_terrain_surface:
        focus = snap_to_terrain(focus)
    coll = bpy.data.collections.new(coll_name)
    _link_once(root, coll)

    props = dict(presets.VANTAGE_DEFAULTS)
    props["preset"] = preset
    resolved = presets.resolve_config({"preset": preset})
    props["views"] = resolved["views"]
    props["resolution"] = resolved["resolution"]
    props["samples"] = resolved["samples"]
    _write_props(coll, props)

    shells = props["distance_shells_m"]
    env = _new_env_sphere("ENV_" + name, focus, 1.15 * max(shells))
    foc = _new_focus_empty("FOCUS_" + name, focus)
    coll.objects.link(env)
    coll.objects.link(foc)
    return coll


def _world_bounds(ob, depsgraph):
    """(center, radius) of the evaluated world-space bounding box."""
    ev = ob.evaluated_get(depsgraph)
    corners = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
    center = sum(corners, Vector()) / 8.0
    radius = max((c - center).length for c in corners)
    return center, radius


def create_child_rig(vantage, object_name, preset=None):
    """CAPTURE_<vantage>__<object>: spherical ENV auto-fitted to the object's
    evaluated bounds (+ standoff shells), FOCUS at bounds center."""
    vantages = find_vantages()
    if vantage not in vantages:
        raise ValueError(f"no vantage {vantage!r} (have: {sorted(vantages)})")
    parent = vantages[vantage]
    target = bpy.data.objects.get(object_name)
    if target is None or target.type != "MESH":
        raise ValueError(f"target object {object_name!r} not found or not a mesh")
    # child rigs orbit RENDERABLE SCENE CONTENT — never capture infrastructure
    # (ENV_/FOCUS_/markers) or render-hidden helpers; those don't exist in the
    # dataset, so a rig around them is meaningless (and auto-fit goes wild:
    # an ENV sphere target once produced 25-60 km shells)
    root = bpy.data.collections.get(CAPTURE_ROOT)
    if (object_name.startswith(("ENV_", "FOCUS_", "PRV_"))
            or (root is not None and any(_in_subtree(c, root) for c in target.users_collection))):
        raise ValueError(f"{object_name!r} is capture infrastructure — select a scene object")
    if target.hide_render:
        raise ValueError(f"{object_name!r} is render-hidden — it won't appear in the "
                         "dataset; unhide it or pick another object")
    deps_check = bpy.context.evaluated_depsgraph_get()
    _c, radius_check = _world_bounds(target, deps_check)
    if radius_check > 500.0:
        raise ValueError(f"{object_name!r} bounds radius is {radius_check:.0f} m — child "
                         "rigs are close-up orbits; select a smaller object")

    key = re.sub(r"[^a-z0-9]+", "-", object_name.lower()).strip("-")
    if not NAME_RE.match(key):
        raise ValueError(f"object name does not reduce to [a-z0-9-]+: {object_name!r}")
    child_id = vantage + CHILD_SEP + key
    coll_name = "CAPTURE_" + child_id
    if bpy.data.collections.get(coll_name):
        raise ValueError(f"{coll_name} already exists")

    deps = bpy.context.evaluated_depsgraph_get()
    center, radius = _world_bounds(target, deps)

    coll = bpy.data.collections.new(coll_name)
    _link_once(parent, coll)

    props = dict(presets.VANTAGE_DEFAULTS)
    props.update(presets.CHILD_DEFAULTS)
    props["preset"] = preset or parent.get("preset", "draft")
    # explicit numbers, same as create_vantage — no 0-means-preset sentinels
    resolved = presets.resolve_config({"preset": props["preset"]}, child=True)
    props["views"] = resolved["views"]
    props["resolution"] = resolved["resolution"]
    props["samples"] = resolved["samples"]
    props["target_object"] = object_name
    props["standoff_min_m"] = max(0.5, round(0.35 * radius, 2))
    props["distance_shells_m"] = [round(radius * f, 2) for f in presets.CHILD_DEFAULTS["shell_factors"]]
    props["min_height_m"] = 0.5   # close-ups may skim the ground
    props["clearance_m"] = max(0.3, round(0.15 * radius, 2))
    props.pop("shell_factors", None)
    props.pop("assembly", None)   # assembly is a parent-vantage decision
    _write_props(coll, props)

    env = _new_env_sphere("ENV_" + child_id, center, 1.05 * max(props["distance_shells_m"]))
    env.color = (0.75, 0.4, 1.0, 1.0)
    foc = _new_focus_empty("FOCUS_" + child_id, center)
    foc.empty_display_size = max(0.5, 0.25 * radius)
    coll.objects.link(env)
    coll.objects.link(foc)
    return coll


def fit_shells_to_env(coll, fractions=(0.5, 0.72, 0.92)):
    """Set distance_shells_m from the ENV volume's actual size: fractions of the
    nearest FOCUS->ENV-surface distance (so every shell fits inside the envelope
    in all directions). The scale-the-ENV-then-fit authoring flow: cameras stay
    on shells; the ENV alone never moves them outward."""
    from . import validity

    env, foc = env_object(coll), focus_object(coll)
    if env is None or foc is None:
        raise ValueError(f"{coll.name}: missing ENV or FOCUS")
    vol = validity.EnvVolume(env)
    focus = foc.matrix_world.translation
    if not vol.contains(tuple(focus)):
        raise ValueError(f"FOCUS_{vantage_name(coll)} is outside its ENV volume — "
                         "move one of them first")
    co, _n, _i, _d = vol.bvh.find_nearest(focus)
    reach = (co - focus).length
    shells = [round(reach * f, 1) for f in fractions]
    coll["distance_shells_m"] = shells
    return shells


def fit_all_shells(vantage_coll, fractions=(0.5, 0.72, 0.92)):
    """fit_shells_to_env for the parent AND every child rig (each against its
    own ENV). Returns ([(collection_name, old_shells, new_shells), ...],
    [error strings]). Unchanged geometry -> unchanged shells (idempotent)."""
    changes, errors = [], []
    for coll in [vantage_coll] + list(find_children(vantage_coll).values()):
        old = [round(float(s), 2) for s in coll.get("distance_shells_m", [])]
        try:
            new = fit_shells_to_env(coll, fractions)
        except ValueError as err:
            errors.append(str(err))
            continue
        changes.append((coll.name, old, [round(s, 2) for s in new]))
    return changes, errors


def read_config(coll, child=False):
    """Collection custom properties -> plain dict -> presets.resolve_config()."""
    props = {}
    for key in coll.keys():
        val = coll[key]
        if hasattr(val, "to_list"):
            val = val.to_list()
        elif hasattr(val, "to_dict"):
            val = val.to_dict()
        props[key] = val
    return presets.resolve_config(props, child=child)


def env_mesh_state(ob):
    """('ok'|'open'|'flipped'|'empty') for an ENV volume mesh (raw data +
    matrix_world — ENV meshes are modifier-free by convention)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    try:
        if not bm.faces:
            return "empty"
        if not all(e.is_manifold and e.is_contiguous for e in bm.edges):
            return "open"
        bm.transform(ob.matrix_world)
        if bm.calc_volume(signed=True) < 0.0:
            return "flipped"
        return "ok"
    finally:
        bm.free()


def validate_vantage(coll):
    """Cheap structural checks -> list of warning strings (preview shows them)."""
    warnings = []
    name = vantage_name(coll)
    env, foc = env_object(coll), focus_object(coll)
    if env is None:
        warnings.append(f"missing ENV_{name}")
    else:
        state = env_mesh_state(env)
        if state == "open":
            warnings.append(f"ENV_{name} mesh is not closed — inside/outside tests unreliable")
        elif state == "flipped":
            warnings.append(f"ENV_{name} normals point inward (handled, but consider Recalculate Outside)")
        elif state == "empty":
            warnings.append(f"ENV_{name} has no faces")
    if foc is None:
        warnings.append(f"missing FOCUS_{name}")
    for key, child in find_children(coll).items():
        target = child.get("target_object", "")
        if not bpy.data.objects.get(target):
            warnings.append(f"child rig {key}: target object {target!r} missing")
        warnings.extend(validate_vantage(child))
    return warnings
