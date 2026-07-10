"""Phase 5 VERIFY (SETUP.md): TRELLIS.2 example inference at 512^3 -> .glb.

Run with the trellis2 env's python, cwd = ~/apps/TRELLIS.2 (bundled assets).
Logs generation time and peak VRAM. Exits non-zero on failure.
"""

import os

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

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
    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    import o_voxel

    out_dir = os.path.expanduser("~/apps/TRELLIS.2/verify_out")
    os.makedirs(out_dir, exist_ok=True)
    glb_path = os.path.join(out_dir, "verify_512.glb")

    t0 = time.perf_counter()
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained("microsoft/TRELLIS.2-4B")
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
    mesh = pipeline.run(image, pipeline_type="512")[0]
    torch.cuda.synchronize()
    t_gen = time.perf_counter() - t1
    print(f"512^3 generation: {t_gen:.1f}s")

    t2 = time.perf_counter()
    mesh.simplify(16777216)
    glb = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices,
        faces=mesh.faces,
        attr_volume=mesh.attrs,
        coords=mesh.coords,
        attr_layout=mesh.layout,
        voxel_size=mesh.voxel_size,
        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=1000000,
        texture_size=4096,
        remesh=True,
        remesh_band=1,
        remesh_project=0,
        verbose=False,
    )
    glb.export(glb_path, extension_webp=True)
    t_glb = time.perf_counter() - t2
    print(f"glb export: {t_glb:.1f}s")

    stop.set()
    sampler.join(timeout=3)

    peak_torch = torch.cuda.max_memory_allocated() / 2**30
    peak_smi = max(peaks) / 1024 if peaks else float("nan")
    print(f"peak VRAM: torch allocator {peak_torch:.1f} GiB | nvidia-smi {peak_smi:.1f} GiB")

    ok = os.path.isfile(glb_path) and os.path.getsize(glb_path) > 1_000_000
    print(f"glb: {glb_path} ({os.path.getsize(glb_path) / 2**20:.1f} MiB)" if ok
          else f"FAIL: glb missing or too small at {glb_path}")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
