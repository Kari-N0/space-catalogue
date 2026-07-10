"""Phase 4 VERIFY (SETUP.md): torch CUDA + gsplat rasterization smoke test.

Run with the splat env's python. Exits non-zero on any failure.
"""

import sys

import torch


def main() -> int:
    ok = True

    # 1. CUDA available, device is the 4090
    cuda_ok = torch.cuda.is_available()
    name = torch.cuda.get_device_name(0) if cuda_ok else "<none>"
    print(f"torch {torch.__version__} | torch CUDA {torch.version.cuda}")
    print(f"cuda available: {cuda_ok} | device: {name}")
    if not cuda_ok:
        print("FAIL: torch.cuda.is_available() is False")
        ok = False
    elif "4090" not in name:
        print(f"FAIL: device name does not contain '4090': {name}")
        ok = False

    # 2. import gsplat
    try:
        import gsplat
        print(f"gsplat {gsplat.__version__}")
    except Exception as e:  # noqa: BLE001 - report any import failure
        print(f"FAIL: import gsplat: {e}")
        return 1

    if not ok:
        return 1

    # 3. rasterize 1,000 random Gaussians to 128x128 on CUDA
    device = "cuda"
    n = 1000
    torch.manual_seed(0)
    means = (torch.rand(n, 3, device=device) - 0.5) * 1.5
    means[:, 2] += 2.0  # in front of the camera (OpenCV +z)
    quats = torch.nn.functional.normalize(torch.rand(n, 4, device=device), dim=-1)
    scales = torch.rand(n, 3, device=device) * 0.05
    opacities = torch.rand(n, device=device)
    colors = torch.rand(n, 3, device=device)
    viewmats = torch.eye(4, device=device)[None]
    ks = torch.tensor(
        [[[100.0, 0.0, 64.0], [0.0, 100.0, 64.0], [0.0, 0.0, 1.0]]], device=device
    )

    renders, alphas, meta = gsplat.rasterization(
        means, quats, scales, opacities, colors, viewmats, ks, width=128, height=128
    )

    print(f"render shape: {tuple(renders.shape)} | alpha max: {alphas.max().item():.4f}")
    if renders.shape[:3] != (1, 128, 128):
        print("FAIL: unexpected render shape")
        ok = False
    if not torch.isfinite(renders).all():
        print("FAIL: non-finite values in render")
        ok = False
    if alphas.max().item() <= 0.0:
        print("FAIL: render is empty (max alpha == 0)")
        ok = False

    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
