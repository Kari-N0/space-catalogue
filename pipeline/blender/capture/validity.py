"""Rig-candidate validity checks — bpy script (ML-free), Blender 5.1.

Scene queries use Object.ray_cast / Object.closest_point_on_mesh with the
evaluated depsgraph: Blender builds the BVH C-side, so multi-million-face
displaced terrain costs no Python marshaling. Queries are transformed into each
object's local space (matrix_world.inverted()) and results back to world — the
classic local-space gotcha handled in exactly one place.
scene.ray_cast is forbidden in this module: it intersects viewport-visible
objects, and ENV wireframes are viewport-visible by design — a down-ray from
inside an envelope must hit terrain, not the envelope wall.

ENV containment uses a world-baked BVHTree.FromPolygons over the RAW mesh
(ENV volumes are modifier-free, small, and closed by convention) with a
closest-point normal-dot test — exact for closed manifolds, no ray-parity
grazing pathology; inverted normals are handled via the signed volume.

Terrain caveat (blockout_lunar_base.py learning): interactive sessions evaluate
SUBSURF at viewport levels (± a couple of meters vs render). Callers pass
`tolerance_m` — preview tightens every threshold by TERRAIN_TOL_M; headless
export raises subsurf to render levels instead (rig.render_fidelity_subdiv).

Importable API:
    SceneGeo(exclude_root)                    # evaluated render geometry
      .height_above_terrain(p) -> float | None
      .clearance(p, within_m) -> (dist | None, object_name)
      .distance_to(p, object_name, within_m) -> float | None
      .los_blocked(p, focus, slack_m, target_object=None) -> str | None
    EnvVolume(env_object).contains(p) -> bool
"""

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

_EPS = 1e-4
TERRAIN_TOL_M = 2.0          # viewport-vs-render subdiv discrepancy budget
TERRAIN_PREFIX = "terrain"   # terrain objects: name starts with 'terrain' (repo convention)


def _under_collection(ob, coll):
    if any(c == coll for c in ob.users_collection):
        return True
    return any(_under_collection(ob, child) for child in coll.children)


def render_visible_objects(scene):
    """Objects that will actually appear in a render: ob.hide_render False AND
    reachable through at least one collection path with no hide_render ancestor.
    (A collection-level hide_render — e.g. a hidden Blockout — must remove its
    objects from validity too, or invisible geometry blocks LOS/clearance.)"""
    visible = set()

    def walk(coll, hidden):
        hidden = hidden or coll.hide_render
        if not hidden:
            for ob in coll.objects:
                visible.add(ob.name)
        for child in coll.children:
            walk(child, hidden)

    walk(scene.collection, False)
    return [ob for ob in scene.objects if ob.name in visible and not ob.hide_render]


class _Entry:
    __slots__ = ("name", "ob", "inv", "mat", "is_terrain")

    def __init__(self, ob):
        self.name = ob.name
        self.ob = ob
        self.mat = ob.matrix_world.copy()
        self.inv = ob.matrix_world.inverted()
        self.is_terrain = ob.name.lower().startswith(TERRAIN_PREFIX)

    def ray_world(self, origin, direction, deps):
        """World-space ray against the evaluated mesh -> world hit point or None."""
        lo = self.inv @ Vector(origin)
        ld = (self.inv.to_3x3() @ Vector(direction)).normalized()
        hit, loc, _n, _i = self.ob.ray_cast(lo, ld, depsgraph=deps)
        return (self.mat @ loc) if hit else None

    def nearest_world(self, p, max_dist, deps):
        """World-space distance to the evaluated surface, or None beyond max_dist."""
        lp = self.inv @ Vector(p)
        # local-space search radius: conservative under (possibly non-uniform) scale
        s = max(self.inv.to_scale())
        ok, loc, _n, _i = self.ob.closest_point_on_mesh(
            lp, distance=max_dist * s + _EPS, depsgraph=deps)
        if not ok:
            return None
        d = ((self.mat @ loc) - Vector(p)).length
        return d if d <= max_dist else None


class SceneGeo:
    """Validity queries against everything that will actually render."""

    def __init__(self, exclude_root=None, scene=None):
        scene = scene or bpy.context.scene
        self.deps = bpy.context.evaluated_depsgraph_get()
        self.entries = []
        for ob in render_visible_objects(scene):
            if ob.type != "MESH":
                continue
            if exclude_root is not None and _under_collection(ob, exclude_root):
                continue
            self.entries.append(_Entry(ob))
        self.has_terrain = any(e.is_terrain for e in self.entries)

    def height_above_terrain(self, p):
        """Vertical clearance to the terrain below p; None when no terrain below.
        Falls back to any render geometry when no terrain-named object exists."""
        p = Vector(p)
        best = None
        for e in self.entries:
            if self.has_terrain and not e.is_terrain:
                continue
            hit = e.ray_world(p, (0.0, 0.0, -1.0), self.deps)
            if hit is not None:
                d = p.z - hit.z
                best = d if best is None else min(best, d)
        return best

    def clearance(self, p, within_m=1e6):
        """(distance to nearest render surface or None if all beyond within_m,
        nearest object's name)."""
        best, who = None, ""
        for e in self.entries:
            d = e.nearest_world(p, within_m if best is None else min(best, within_m), self.deps)
            if d is not None and (best is None or d < best):
                best, who = d, e.name
        return (best, who)

    def distance_to(self, p, object_name, within_m=1e6):
        """Distance from p to one named object's surface (child-rig standoff guard)."""
        for e in self.entries:
            if e.name == object_name:
                return e.nearest_world(p, within_m, self.deps)
        return None

    def los_blocked(self, p, focus, slack_m, target_object=None):
        """Name of the object blocking the p->focus ray, or None when clear.

        Hits within slack_m of the focus don't count (the focus often sits on
        the ground or at an object's center). For child rigs pass target_object:
        hits on the target itself are what the camera is FOR, never a blocker.
        """
        p, focus = Vector(p), Vector(focus)
        direction = focus - p
        dist = direction.length
        if dist < _EPS:
            return None
        direction /= dist
        blocker, blocker_d = None, dist - slack_m
        origin = p + direction * _EPS
        for e in self.entries:
            if target_object is not None and e.name == target_object:
                continue
            hit = e.ray_world(origin, direction, self.deps)
            if hit is not None:
                d = (hit - p).length
                if d < blocker_d:
                    blocker, blocker_d = e.name, d
        return blocker


class EnvVolume:
    """World-space containment test for an ENV volume (raw mesh + matrix_world:
    ENV meshes are modifier-free by convention, so a layer-collection exclusion
    of capture/ can't silently empty the evaluated geometry)."""

    def __init__(self, env_object):
        import bmesh

        mesh = env_object.data
        if not mesh.polygons:
            raise ValueError(f"ENV mesh {env_object.name!r} has no faces")
        mw = env_object.matrix_world
        verts = [mw @ v.co for v in mesh.vertices]
        polys = [tuple(p.vertices) for p in mesh.polygons]
        self.bvh = BVHTree.FromPolygons(verts, polys)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.transform(mw)
        self.orientation = 1.0 if bm.calc_volume(signed=True) >= 0.0 else -1.0
        bm.free()

    def contains(self, p):
        co, normal, _index, _dist = self.bvh.find_nearest(Vector(p))
        if co is None:
            return False
        return self.orientation * normal.dot(Vector(p) - co) < 0.0
