#!/usr/bin/env python
"""intake.py — image -> textured GLB via TRELLIS 1 (ADDON.md §8 intake, seed).

Runs in the `trellis1` conda env, cwd + PYTHONPATH = ~/apps/TRELLIS:
    cd ~/apps/TRELLIS && PYTHONPATH=~/apps/TRELLIS ATTN_BACKEND=flash-attn SPCONV_ALGO=native \
      ~/miniconda3/envs/trellis1/bin/python <repo>/pipeline/trellis/intake.py \
      --image <input.png> --out-dir <dir> --slug <name> [--seed 1]

LICENSE GUARD (CLAUDE.md hard rule): formats are HARDCODED to
['mesh', 'radiance_field'] — the string 'gaussian' must never be requested;
texture baking runs via the radiance field (diffoctreerast, MIT). The
Inria-derived rasterizer is not installed and must never be.

Outputs: <out-dir>/<slug>.glb + <slug>.provenance.json (tool, model, input
hash, seed, date, license snapshot — the shipping decision field defaults to
NOT CLEARED and is Kari's to change).

Importable: intake(image_path, out_dir, slug, seed=1, simplify=0.95,
                   texture_size=1024, license_note=None) -> dict
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import date

os.environ.setdefault("ATTN_BACKEND", "flash-attn")
os.environ.setdefault("SPCONV_ALGO", "native")

FORMATS = ["mesh", "radiance_field"]  # never 'gaussian' — see module docstring


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def intake(image_path: str, out_dir: str, slug: str, seed: int = 1,
           simplify: float = 0.95, texture_size: int = 1024,
           license_note: str | None = None) -> dict:
    from PIL import Image
    from trellis.pipelines import TrellisImageTo3DPipeline
    from trellis.utils import postprocessing_utils

    os.makedirs(out_dir, exist_ok=True)
    glb_path = os.path.join(out_dir, f"{slug}.glb")

    t0 = time.perf_counter()
    pipeline = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")
    pipeline.cuda()
    print(f"model load: {time.perf_counter() - t0:.1f}s", flush=True)

    image = Image.open(image_path)
    t1 = time.perf_counter()
    outputs = pipeline.run(image, seed=seed, formats=list(FORMATS))
    print(f"generation: {time.perf_counter() - t1:.1f}s", flush=True)

    t2 = time.perf_counter()
    glb = postprocessing_utils.to_glb(
        outputs["radiance_field"][0], outputs["mesh"][0],
        simplify=simplify, texture_size=texture_size, verbose=False,
    )
    glb.export(glb_path)
    print(f"glb export: {time.perf_counter() - t2:.1f}s -> {glb_path} "
          f"({os.path.getsize(glb_path) / 2**20:.1f} MiB)", flush=True)

    prov = {
        "type": "generated",
        "asset": glb_path,
        "tool": "TRELLIS 1 (microsoft/TRELLIS-image-large)",
        "model_version": "TRELLIS-image-large, trellis1 env (torch 2.4.0+cu124)",
        "prompt_or_input": f"{os.path.basename(image_path)} (sha256 {_sha256(image_path)})",
        "seed": seed,
        "formats": FORMATS,
        "date": date.today().isoformat(),
        "license_at_generation": license_note or (
            "TRELLIS 1 MIT; rembg/u2net MIT; INPUT IMAGE LICENSE GOVERNS THE OUTPUT — "
            "shipping NOT CLEARED until Kari rules on the input's terms"
        ),
        "notes": f"simplify {simplify}, texture {texture_size}px; radiance-field bake (diffoctreerast)",
    }
    prov_path = os.path.join(out_dir, f"{slug}.provenance.json")
    with open(prov_path, "w") as fh:
        json.dump(prov, fh, indent=2)
    print(f"provenance: {prov_path}", flush=True)
    return prov


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--image", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--simplify", type=float, default=0.95)
    ap.add_argument("--texture-size", type=int, default=1024)
    ap.add_argument("--license-note", default=None)
    args = ap.parse_args()
    intake(args.image, args.out_dir, args.slug, args.seed, args.simplify,
           args.texture_size, args.license_note)


if __name__ == "__main__":
    main()
