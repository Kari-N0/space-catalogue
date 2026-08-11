"""run_illum_sweep.py — render one illumination sweep from illum_sim_v002.blend.

bpy script (ML-free), run headless on Windows Blender:
    pipeline/blender/blender-win.sh -b <illum_sim_v002.blend> --factory-startup \
        --python pipeline/blender/run_illum_sweep.py -- \
        --camera A|B --season psr|lit|beauty --out-dir <dir> \
        [--steps 150] [--res-pct 25] [--samples 8] [--dicing 2.0]

Sun conventions (v002 method — derivation in the provenance record):
  * Pole-datum elevation, constant per sweep; the pole-referenced curvature
    in the terrain shader turns it into correct per-pixel local geometry.
  * Subsolar latitude oscillation: +-1.54 deg (Moon's obliquity to the
    ecliptic, 1.5424 deg). Solar semi-diameter at 1 AU: 0.266 deg.
  * season psr    -> elevation +1.806 deg (best season +1.54 plus the top
    limb +0.266), POINT sun: "any part of the disk visible" test for
    horizon-like occluders. PSR = never lit across the sweep. Conservative
    toward shadow claims.
  * season lit    -> elevation -1.54 deg (worst season), POINT sun =
    disk-center visibility. Lit fraction = share of the sweep's 150 steps
    lit. Conservative toward lit claims.
  * season beauty -> one presentational frame (elev +1.54, disk 0.53 deg,
    az 225, 64 samples) as a backdrop for preview overlays.
  * Azimuth steps: 360/steps per frame, same formula as render_sun_study.py
    (sun.rotation_euler = (90-elev, 0, az)); full circle, so sweep direction
    does not affect the masks.

Importable API: run_sweep(camera, season, out_dir, steps, res_pct, samples, dicing)
"""

import argparse
import math
import os
import sys
import time

import bpy

SEASONS = {
    "psr": {"elevation_deg": 1.806, "sun_angle_deg": 0.0},
    "lit": {"elevation_deg": -1.54, "sun_angle_deg": 0.0},
    "beauty": {"elevation_deg": 1.54, "sun_angle_deg": 0.53},
    # annual integral: the caller passes --elevation-deg = -1.54*sin(theta_k)
    # for equal-time samples theta_k of the sinusoidal subsolar-latitude cycle
    "custom": {"elevation_deg": None, "sun_angle_deg": 0.0},
}


def run_sweep(camera: str, season: str, out_dir: str, steps: int = 150,
              res_pct: int = 25, samples: int = 8, dicing: float = 2.0,
              elevation_deg: float | None = None) -> list:
    scene = bpy.context.scene
    cfg = dict(SEASONS[season])
    if elevation_deg is not None:
        cfg["elevation_deg"] = elevation_deg
    if cfg["elevation_deg"] is None:
        raise SystemExit("season 'custom' requires --elevation-deg")
    sun = bpy.data.objects["illum_sun"]
    sun.data.angle = math.radians(cfg["sun_angle_deg"])
    scene.camera = bpy.data.objects[f"illum_cam{camera}"]
    scene.render.resolution_percentage = res_pct
    scene.cycles.samples = 64 if season == "beauty" else samples
    scene.cycles.dicing_rate = dicing
    os.makedirs(out_dir, exist_ok=True)

    elev = cfg["elevation_deg"]
    frames = []
    t0 = time.perf_counter()
    plan = [225.0] if season == "beauty" else [360.0 * i / steps for i in range(steps)]
    for i, az in enumerate(plan):
        sun.rotation_euler = (math.radians(90.0 - elev), 0.0, math.radians(az))
        path = os.path.join(out_dir, f"f{i:03d}.exr")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        frames.append(path)
        if i % 25 == 0 or season == "beauty":
            print(f"SWEEP {camera}/{season} {i + 1}/{len(plan)}: az {az:.1f} elev {elev:+.3f} -> {path}")
    print(f"SWEEP DONE {camera}/{season}: {len(plan)} frames in {time.perf_counter() - t0:.0f}s")
    return frames


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--camera", required=True, choices=["A", "B"])
    ap.add_argument("--season", required=True, choices=list(SEASONS))
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--steps", type=int, default=150)
    ap.add_argument("--res-pct", type=int, default=25)
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--dicing", type=float, default=2.0)
    ap.add_argument("--elevation-deg", type=float, default=None)
    args = ap.parse_args(argv)
    run_sweep(args.camera, args.season, args.out_dir, args.steps,
              args.res_pct, args.samples, args.dicing, args.elevation_deg)


if __name__ == "__main__":
    main()
