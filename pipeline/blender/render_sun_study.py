"""render_sun_study.py — render N sun-azimuth steps from an audition .blend.

bpy script (ML-free), run headless on Windows Blender:
    pipeline/blender/blender-win.sh -b <terrain_site_v001.blend> \
        --python pipeline/blender/render_sun_study.py -- \
        --out-dir /mnt/d/renders/lunar-base/audition/<site> [--steps 24] [--elevation 1.5]

Rotates the "sun" object through the full azimuth circle at fixed grazing
elevation (SCENE-BIBLE.md §5: azimuth is art direction, elevation is physics)
and renders az_000.png ... az_345.png. Identical across sites by construction —
everything else lives in the .blend.

Importable API: render_sun_study(out_dir, steps=24, elevation_deg=1.5) -> list[str]
"""

import argparse
import math
import os
import sys
import time

import bpy


def render_sun_study(out_dir: str, steps: int = 24, elevation_deg: float = 1.5) -> list:
    scene = bpy.context.scene
    sun = bpy.data.objects["sun"]
    os.makedirs(out_dir, exist_ok=True)
    frames = []
    t0 = time.perf_counter()
    for i in range(steps):
        az = 360.0 * i / steps
        sun.rotation_euler = (math.radians(90.0 - elevation_deg), 0.0, math.radians(az))
        path = os.path.join(out_dir, f"az_{az:03.0f}.png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        frames.append(path)
        print(f"SUN STUDY {i + 1}/{steps}: az {az:.0f} deg -> {path}")
    print(f"SUN STUDY DONE: {steps} frames in {time.perf_counter() - t0:.0f}s")
    return frames


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--steps", type=int, default=24)
    ap.add_argument("--elevation", type=float, default=1.5)
    args = ap.parse_args(argv)
    render_sun_study(args.out_dir, args.steps, args.elevation)


if __name__ == "__main__":
    main()
