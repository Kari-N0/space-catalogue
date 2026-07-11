"""make_lods.py — generate LOD1/LOD2 collections for an asset (ASSETS.md janitor pass).

bpy script (ML-free), run headless or imported:
    pipeline/blender/blender-win.sh -b <asset.blend> --python pipeline/blender/make_lods.py -- \
        --slug pad --save <out.blend>

For every mesh object in AST_<slug>: evaluate modifiers to a real mesh, then
decimate (collapse) to the LOD ratio. Results land in AST_<slug>_LOD1 / _LOD2
collections with `_lod1`/`_lod2` name suffixes; AST_<slug> itself is LOD0 and
is never touched. Ratios per ASSET-SPEC: LOD1 mid ~0.35, LOD2 far ~0.08.

Importable: make_lods(slug, ratios=(0.35, 0.08)) -> dict[str, int]  # tri counts
"""

import argparse
import sys

import bpy


def make_lods(slug: str, ratios=(0.35, 0.08)) -> dict:
    src = bpy.data.collections[f"AST_{slug}"]
    scene = bpy.context.scene
    deps = bpy.context.evaluated_depsgraph_get()
    counts = {}
    for lod, ratio in enumerate(ratios, start=1):
        coll = bpy.data.collections.new(f"AST_{slug}_LOD{lod}")
        scene.collection.children.link(coll)
        for ob in list(src.objects):
            if ob.type != "MESH":
                continue
            mesh = bpy.data.meshes.new_from_object(ob.evaluated_get(deps))
            dup = bpy.data.objects.new(f"{ob.name}_lod{lod}", mesh)
            dup.matrix_world = ob.matrix_world.copy()
            if ob.get("procedural_ok"):
                dup["procedural_ok"] = 1
            coll.objects.link(dup)
            dec = dup.modifiers.new("decimate", "DECIMATE")
            dec.ratio = ratio
            ev = bpy.data.meshes.new_from_object(dup.evaluated_get(bpy.context.evaluated_depsgraph_get()))
            dup.modifiers.clear()
            old = dup.data
            dup.data = ev
            bpy.data.meshes.remove(old)
        total = 0
        for o in coll.objects:
            if o.type == "MESH":
                o.data.calc_loop_triangles()
                total += len(o.data.loop_triangles)
        counts[f"LOD{lod}"] = total
    return counts


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--save", default=None, help="save result to this .blend path")
    args = ap.parse_args(argv)
    counts = make_lods(args.slug)
    print(f"LODS: {counts}")
    if args.save:
        bpy.ops.wm.save_as_mainfile(filepath=args.save)
        print(f"LODS SAVED: {args.save}")


if __name__ == "__main__":
    main()
