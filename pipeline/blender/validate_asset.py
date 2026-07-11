"""validate_asset.py — headless asset gate (ASSETS.md loop; runs before any 'approved').

bpy script (ML-free), run headless on Windows Blender:
    pipeline/blender/blender-win.sh -b <asset.blend> --python pipeline/blender/validate_asset.py -- \
        --asset pad [--specs pipeline/blender/asset_specs.json]

Checks (asset spec in ASSETS.md; expected dims in asset_specs.json):
  A001 collection AST_<slug> exists and is non-empty
  A002 bounding box vs bible dims (sorted XY extents; skipped when dims_m null)
  A003 grounded at Z=0 (collection min-Z within ±0.5 m; terrain-context CTX_ excluded)
  A004 footprint centered near world origin (XY within 10% of largest extent)
  A005 applied transforms: object scale == (1,1,1)
  A006 naming: objects prefixed '<slug>_', materials 'M_', GN groups 'GN_'
  A007 every mesh object has >=1 material slot
  A008 UV layer present on every mesh (unless object custom prop procedural_ok=1)

Exit code 0 = all pass, 1 = failures (headless gate). Importable:
    run_checks(slug, specs) -> list[(check_id, ok, message)]
"""

import argparse
import json
import os
import sys

import bpy
from mathutils import Vector


def _collection_objects(coll):
    objs = list(coll.objects)
    for child in coll.children:
        objs += _collection_objects(child)
    return objs


def _world_bbox(objs):
    deps = bpy.context.evaluated_depsgraph_get()
    lo = Vector((1e18, 1e18, 1e18))
    hi = Vector((-1e18, -1e18, -1e18))
    for ob in objs:
        if ob.type != "MESH":
            continue
        ev = ob.evaluated_get(deps)
        for corner in ev.bound_box:
            w = ev.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def run_checks(slug: str, specs: dict) -> list:
    spec = specs.get(slug, {})
    coll_name = spec.get("collection", f"AST_{slug}")
    results = []
    ok = lambda cid, cond, msg: results.append((cid, bool(cond), msg))

    coll = bpy.data.collections.get(coll_name)
    ok("A001", coll and len(_collection_objects(coll)) > 0, f"collection {coll_name} exists and is non-empty")
    if not coll:
        return results
    objs = _collection_objects(coll)
    meshes = [o for o in objs if o.type == "MESH"]

    lo, hi = _world_bbox(meshes)
    size = hi - lo
    if spec.get("dims_m"):
        want = spec["dims_m"]
        tol = spec.get("tolerance_frac", 0.15)
        got_xy, want_xy = sorted([size.x, size.y]), sorted(want[:2])
        dims_ok = all(
            abs(g - w) <= tol * w
            for g, w in zip(got_xy + [size.z], want_xy + [want[2]])
        )
        ok("A002", dims_ok, f"bbox {size.x:.1f}x{size.y:.1f}x{size.z:.1f} vs bible {want} (tol {tol:.0%})")
    else:
        ok("A002", True, "dims check skipped (no canonical dims for this asset)")

    if spec.get("skip_origin_checks"):
        ok("A003", True, "grounding check skipped per spec")
        ok("A004", True, "centering check skipped per spec")
    else:
        gtol = spec.get("ground_tol_m", 0.5)
        ok("A003", abs(lo.z) <= gtol, f"grounded: min-Z {lo.z:+.2f} m (want 0 +-{gtol})")
        center = (lo + hi) / 2
        max_ext = max(size.x, size.y, 1.0)
        ok("A004", abs(center.x) <= 0.1 * max_ext and abs(center.y) <= 0.1 * max_ext,
           f"footprint centered: ({center.x:+.1f}, {center.y:+.1f}) m")

    unapplied = [o.name for o in meshes if any(abs(s - 1.0) > 1e-4 for s in o.scale)]
    ok("A005", not unapplied, f"applied scale (offenders: {unapplied or 'none'})")

    bad_names = [o.name for o in objs if not o.name.startswith(f"{slug}_")]
    bad_mats = [m.name for o in meshes for m in o.data.materials if m and not m.name.startswith("M_")]
    bad_gn = [
        g.name for g in bpy.data.node_groups
        if g.type == "GEOMETRY" and not g.name.startswith("GN_")
        and not g.name.startswith(".") and g.name != "Smooth by Angle"  # Blender-internal essentials
    ]
    ok("A006", not (bad_names or bad_mats or bad_gn),
       f"naming (objs {bad_names or 'ok'}, mats {bad_mats or 'ok'}, GN {bad_gn or 'ok'})")

    no_mat = [o.name for o in meshes if not o.data.materials]
    ok("A007", not no_mat, f"material slots (missing: {no_mat or 'none'})")

    no_uv = [
        o.name for o in meshes
        if not o.data.uv_layers and not o.get("procedural_ok")
    ]
    ok("A008", not no_uv, f"UVs (missing, not flagged procedural_ok: {no_uv or 'none'})")
    return results


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--asset", required=True, help="asset slug (key in asset_specs.json)")
    ap.add_argument("--specs", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "asset_specs.json"))
    args = ap.parse_args(argv)
    with open(args.specs) as fh:
        specs = json.load(fh)
    results = run_checks(args.asset, specs)
    failed = [r for r in results if not r[1]]
    for cid, passed, msg in results:
        print(f"{'PASS' if passed else 'FAIL'} {cid}: {msg}")
    print(f"VALIDATE {'OK' if not failed else 'FAILED'}: {len(results) - len(failed)}/{len(results)} checks")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
