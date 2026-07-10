"""TRELLIS 1 VERIFY (mirrors check_trellis2.py): one image -> textured GLB.

License-clean path only: formats=['mesh', 'radiance_field'] and texture baking
via the radiance field (diffoctreerast, MIT). The 'gaussian' format is never
requested, so the Inria-derived diff-gaussian-rasterization (non-commercial,
NOT installed) is never imported. Do not add 'gaussian' to formats.

Run with the trellis1 env's python, cwd = ~/apps/TRELLIS (bundled assets).
Logs generation time and peak VRAM. Exits non-zero on failure.
"""

import os

os.environ["ATTN_BACKEND"] = "flash-attn"
os.environ["SPCONV_ALGO"] = "native"  # skip spconv's slow first-run benchmark

import subprocess
import sys
import threading
import time

from PIL import Image
import torch


def sample_smi(stop, peaks):
    while not stop.is_set():
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            peaks.append(int(out.splitlines()[0]))
        except Exception:
            pass
        time.sleep(0.5)


def main() -> int:
    from trellis.pipelines import TrellisImageTo3DPipeline
    from trellis.utils import postprocessing_utils

    out_dir = os.path.expanduser("~/apps/TRELLIS/verify_out")
    os.makedirs(out_dir, exist_ok=True)
    glb_path = os.path.join(out_dir, "verify_trellis1.glb")

    t0 = time.perf_counter()
    pipeline = TrellisImageTo3DPipeline.from_pretrained("microsoft/TRELLIS-image-large")
    pipeline.cuda()
    t_load = time.perf_counter() - t0
    print(f"model load: {t_load:.1f}s")

    stop = threading.Event()
    peaks: list[int] = []
    sampler = threading.Thread(target=sample_smi, args=(stop, peaks), daemon=True)
    sampler.start()
    torch.cuda.reset_peak_memory_stats()

    image = Image.open("assets/example_image/T.png")
    t1 = time.perf_counter()
    outputs = pipeline.run(image, seed=1, formats=["mesh", "radiance_field"])
    torch.cuda.synchronize()
    t_gen = time.perf_counter() - t1
    print(f"generation: {t_gen:.1f}s")

    t2 = time.perf_counter()
    glb = postprocessing_utils.to_glb(
        outputs["radiance_field"][0],
        outputs["mesh"][0],
        simplify=0.95,
        texture_size=1024,
        verbose=False,
    )
    glb.export(glb_path)
    t_glb = time.perf_counter() - t2
    print(f"glb export: {t_glb:.1f}s")

    stop.set()
    sampler.join(timeout=3)

    peak_torch = torch.cuda.max_memory_allocated() / 2**30
    peak_smi = max(peaks) / 1024 if peaks else float("nan")
    print(f"peak VRAM: torch allocator {peak_torch:.1f} GiB | nvidia-smi {peak_smi:.1f} GiB")

    ok = os.path.isfile(glb_path) and os.path.getsize(glb_path) > 500_000
    print(f"glb: {glb_path} ({os.path.getsize(glb_path) / 2**20:.1f} MiB)" if ok
          else f"FAIL: glb missing or too small at {glb_path}")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
