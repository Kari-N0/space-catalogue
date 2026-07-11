"""import_trellis_glb.py — bring a TRELLIS GLB into an asset .blend (ADDON.md §8 import step).

bpy script (ML-free), run headless on Windows Blender:
    pipeline/blender/blender-win.sh -b --python pipeline/blender/import_trellis_glb.py -- \
        --glb <mk2_ai.glb> --slug mk2_ai --height 16.0 --out <mk2_ai_v001.blend>

Imports the GLB, renames objects/materials to asset conventions
(<slug>_mesh*, M_<slug>_baked*), uniformly scales so the bounding-box height
equals --height (TRELLIS outputs ~unit scale), centers the footprint on the
origin, grounds min-Z at 0, applies transforms, and files everything under
AST_<slug>. Real-world scale is REQUIRED before an AI mesh leaves intake
(ADDON.md: needs_scale discipline).

Importable: import_glb(glb_path, slug, height) -> None
"""

import argparse
import sys

import bpy
from mathutils import Vector


def import_glb(glb_path: str, slug: str, height: float) -> None:
    scene = bpy.context.scene
    coll = bpy.data.collections.new(f"AST_{slug}")
    scene.collection.children.link(coll)

    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    imported = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in imported if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("GLB import produced no mesh objects")

    for i, ob in enumerate(meshes):
        ob.name = f"{slug}_mesh" if i == 0 else f"{slug}_mesh_{i}"
        for j, m in enumerate(ob.data.materials):
            if m:
                m.name = f"M_{slug}_baked" if j == 0 else f"M_{slug}_baked_{j}"
        for c in ob.users_collection:
            c.objects.unlink(ob)
        coll.objects.link(ob)
    for ob in imported:  # drop empties the importer may add
        if ob.type != "MESH" and not ob.children:
            bpy.data.objects.remove(ob)

    deps = bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e18,) * 3)
    hi = Vector((-1e18,) * 3)
    for ob in meshes:
        ev = ob.evaluated_get(deps)
        for corner in ev.bound_box:
            w = ev.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    size = hi - lo
    s = height / size.z
    center = (lo + hi) / 2
    for ob in meshes:
        ob.scale = (ob.scale[0] * s, ob.scale[1] * s, ob.scale[2] * s)
        ob.location = (
            (ob.location[0] - center.x) * s,
            (ob.location[1] - center.y) * s,
            (ob.location[2] - lo.z) * s,
        )
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        ob.select_set(False)
    print(f"IMPORTED: {len(meshes)} mesh(es), scaled x{s:.3f} to {height} m, grounded at Z0")


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--glb", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--height", type=float, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    import_glb(args.glb, args.slug, args.height)
    bpy.ops.wm.save_as_mainfile(filepath=args.out)
    print(f"SAVED: {args.out}")


if __name__ == "__main__":
    main()
