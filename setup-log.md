# setup-log.md — Space Engineering Catalogue environment bootstrap

Machine: RTX 4090 (24 GB) · Ryzen 9 5950X · 128 GB RAM · Windows 11 25H2 + WSL2 Ubuntu 24.04
Executor: Claude Code (WSL). Companion docs: SETUP.md, PLAN.md.

---

## Phase 0 — Preflight — 2026-07-09

**Installed:** nothing (read-only checks).

**Results:**

| Check | Expected | Actual | Result |
|---|---|---|---|
| `nvidia-smi` GPU | RTX 4090 visible | NVIDIA GeForce RTX 4090, 24564 MiB | ✅ |
| Driver / CUDA (from Windows driver) | CUDA ≥ 12.x | Driver 581.57 (WSL lib 580.102.01), CUDA 13.0 | ✅ |
| Kernel | contains "microsoft" | 6.18.33.2-microsoft-standard-WSL2 | ✅ |
| WSL disk free (`~`, ext4) | ≥ 250 GB | 955 GB avail (/dev/sdd, VHDX on D:) | ✅ |
| C: free | ≥ 50 GB per SETUP.md; **user-adjusted threshold ≥ 20 GB** | 37 GB | ✅ (see deviation 1) |
| D: free (render staging `D:\renders`) | informational | 462 GB | ✅ |
| Windows build | 22H2+ (mirrored networking) | 10.0.26200.8655 (Windows 11 25H2) | ✅ |
| Blender ≥ 5.1 on Windows | dir exists | `Blender 5.1.2` (also 5.0.0, 4.x, 3.x present) | ✅ |
| Network (huggingface.co) | reachable | HTTP/2 200 | ✅ |
| CPUs (.wslconfig processors=24) | ~24 | 24 | ✅ |
| RAM (.wslconfig memory=96GB) | ~96 GB | 94 Gi total, 32 Gi swap | ✅ |

**Deviations from SETUP.md:**
1. C: free-space threshold relaxed from ≥ 50 GB to ≥ 20 GB per user instruction (C: is small by design; all large files stage on D: — WSL distro VHDX at `D:\WSL\Ubuntu-24.04`, renders at `D:\renders`). Nothing large will ever be staged on C:.

**VERIFY:** PASS (all checks green under the adjusted threshold).
**GATE:** preflight summary presented — user approved "Proceed to Phase 1" (full apt upgrade included; first sudo use approved). 2026-07-09.

---

## Phase 1 — System packages (WSL) — 2026-07-09

**Installed:** `apt update && apt -y upgrade`, then `build-essential git git-lfs cmake ninja-build pkg-config curl wget unzip aria2 ffmpeg libgl1 libegl1 libxi6 libxxf86vm1 libxfixes3 libxrender1 libsm6 libxkbcommon0`; `git lfs install` run as user.

**Versions:** gcc 13.3.0 · git 2.43.0 · git-lfs 3.4.1 · cmake 3.28.3 · ninja 1.11.1 · pkg-config 1.8.1 · ffmpeg 6.1.1 · aria2 1.37.0 · unzip 6.00 · curl 8.5.0 · wget 1.21.4.

**VERIFY:** PASS — `gcc --version`, `git lfs version`, `cmake --version`, `ffmpeg -version` all succeed; all 8 GL/X11 runtime libs report installed via dpkg.

**Deviations:**
1. Claude Code's shell cannot answer sudo password prompts (no TTY), and the in-session `!` prefix can't either. The two sudo commands were run by the user in a separate Ubuntu terminal, verbatim from SETUP.md. Same procedure planned for the remaining sudo points (Phases 2 and 7). User declined an optional temporary NOPASSWD sudoers rule — no sudoers changes made.

---

## Phase 2 — CUDA toolkit (WSL, toolkit only) — 2026-07-09

**Research first (per SETUP.md order of operations):** 4-agent workflow verified gsplat README/wheel index, PyTorch install matrix, and the NVIDIA WSL-Ubuntu repo live, then cross-checked. Findings:
- gsplat prebuilt wheels top out at torch 2.4 / cu124 / **cp310 only** — incompatible with any 2026 stable torch. Source build is required (SETUP.md's sanctioned fallback).
- gsplat's released 1.5.3 (July 2025) predates CUDA 13 support; CUDA 13 + NumPy 2 support is on main branch only → **Phase 4 must install gsplat from git main, not PyPI.**
- Windows driver 581.57 exposes CUDA 13.0 → toolkit and torch wheels must be ≤ 13.0 (current torch default cu132 would NOT work).
- WSL-Ubuntu apt repo verified to contain zero driver packages (Packages index fetched and grepped); gcc 13.3 is a supported host compiler for nvcc 13.0; torch cu130 major matches toolkit 13.0 (required by torch.utils.cpp_extension).

**Pinned combo:** cuda-toolkit-13-0 (apt) + torch 2.13.0 cu130 (pip) + gsplat from git main with `TORCH_CUDA_ARCH_LIST=8.9`.

**Installed:** `cuda-keyring_1.1-1_all.deb` + `cuda-toolkit-13-0` (13.0.x) from the WSL-Ubuntu repo — run by user in their terminal (sudo point). `/usr/local/cuda/bin` appended to `~/.bashrc` PATH.

**VERIFY:** PASS — `nvcc --version` → release 13.0, V13.0.88; `nvidia-smi` still works (RTX 4090, driver 581.57); dpkg shows no driver packages (only `cuda-driver-dev-13-0`, the linker stub library — expected toolkit component, not a driver).

**Deviations:**
1. SETUP.md's expectation of using gsplat's prebuilt wheel index cannot be satisfied (index abandoned at torch 2.4/cu124/cp310); source-build route selected per ground rule 7 with justification above.

---

## Phase 3 — Node.js stack (WSL) — 2026-07-09

**Installed:** nvm 0.40.5 → Node v24.18.0 (LTS) + npm 11.16.0; global npm packages `gltfpack` 1.2 and `@playcanvas/splat-transform` 3.0.0.

**VERIFY:** PASS — `node -v` v24.18.0 (LTS), `gltfpack` prints usage+version, `splat-transform --help` prints usage.

**Deviations:**
1. Claude Code's auto-mode permission classifier refused to execute the external nvm installer script (both `curl | bash` and download-then-run). The user ran the Phase 3 block verbatim in their own terminal; Claude verified afterwards. No content deviation from SETUP.md.

---

## Phase 4 — Miniconda + gsplat training environment — 2026-07-09

**Installed:** Miniconda (conda 26.5.3) at `~/miniconda3`, `conda init bash` applied; conda env `splat` (Python 3.11.15, conda-forge); pip: torch 2.13.0+cu130, torchvision 0.28.0+cu130, numpy 2.4.4, gsplat 1.5.3 (built from git main), ninja 1.13.0, jaxtyping 0.3.11, rich 15.0.0, plyfile 1.1.4, opencv-python-headless 5.0.0.93, typer 0.26.8.

**gsplat build:** compiled from `git+https://github.com/nerfstudio-project/gsplat.git` (main) with `TORCH_CUDA_ARCH_LIST=8.9 CUDA_HOME=/usr/local/cuda-13.0 --no-build-isolation` — native sm_89 binary against nvcc 13.0 / gcc 13.3.

**VERIFY (`pipeline/checks/check_gsplat.py`):** PASS —
1. `torch.cuda.is_available()` True; device "NVIDIA GeForce RTX 4090";
2. `import gsplat` OK (1.5.3);
3. `gsplat.rasterization` of 1,000 random Gaussians → (1,128,128,3) render, all finite, max alpha 0.9978 (non-empty).
Versions logged: torch 2.13.0+cu130 / torch-CUDA 13.0 / gsplat 1.5.3@main.

**GATE (license/terms):** Anaconda's `defaults` channels now demand ToS acceptance (`CondaToSNonInteractiveError`). Presented to user; user chose **conda-forge only** — `defaults` removed from all condarc levels (`~/.condarc` and `~/miniconda3/.condarc` set to conda-forge, strict priority). No Anaconda ToS accepted.

**Deviations:**
1. conda channels switched from Anaconda defaults to conda-forge (user decision at gate, above).
2. gsplat installed from git main instead of PyPI/wheel index (required for CUDA 13 + NumPy 2 support — see Phase 2 research). Version string still reads 1.5.3; the installed build is newer than the 1.5.3 release.
3. Torch installed pinned (`torch==2.13.0`) from the cu130 index per Phase 2 research, not the SETUP.md placeholder command.

---

## Phase 5 — TRELLIS.2 — 2026-07-09 (install complete; VERIFY pending external approval)

**GATE:** user approved install (~10–20 GB weights + long compile) 2026-07-09.

**Installed:**
- `~/apps/TRELLIS.2` (git clone, main; eigen submodule initialized).
- conda env `trellis2` (Python 3.10, conda-forge) — name per the repo's setup.sh, not SETUP.md's "trellis".
- torch 2.6.0+cu124 + torchvision 0.21.0 (repo-pinned versions).
- CUDA 12.4 compile stack side-by-side with 13.0 (README-documented): `cuda-nvcc-12-4` + dev headers (user-run sudo). `/usr/local/cuda` still → 13.0; TRELLIS builds use explicit `CUDA_HOME=/usr/local/cuda-12.4`.
- setup.sh equivalents: basic deps (transformers 5.13.0, gradio 6.0.1, utils3d @pinned commit, kornia, timm…), flash-attn 2.7.3, nvdiffrast 0.4.0, nvdiffrec_render, cumesh 0.0.1, flex_gemm 1.0.0, o_voxel 0.0.1 — all compiled with nvcc 12.4, `TORCH_CUDA_ARCH_LIST=8.9`.
- Weights: `microsoft/TRELLIS.2-4B` — 16 GB in `~/.cache/huggingface`.

**Deviations:**
1. `cuda-toolkit-12-4` metapackage uninstallable on Ubuntu 24.04 (nsight-systems-2023.4.4 → libtinfo5, dropped in noble). Installed the compiler/header component packages instead (nvcc, cudart-dev, cccl, nvrtc-dev, cublas/cusparse/cusolver/curand dev, nvtx, profiler-api). No profiler installed — not needed.
2. **pillow-simd skipped** (build fails: zlib dev headers absent; package is an unmaintained Pillow-9-era fork that would downgrade Pillow 12.2.0 and risk transformers-5/gradio-6 breakage; it is a pure CPU-speed optimization). Standard Pillow retained.
3. flash-attn required `--no-build-isolation` (+packaging, psutil) — its setup.py imports torch; this matches flash-attn's own install docs.
4. nvdiffrec link failed with `cannot find -lcuda`; fixed by `LIBRARY_PATH=/usr/lib/wsl/lib` (real WSL driver lib) during builds — WSL-specific, no stub package needed.
5. Extension clones placed under the job tmp dir instead of setup.sh's `/tmp/extensions`.
6. **NEW GATE discovered:** TRELLIS.2's image encoder is `facebook/dinov3-vitl16-pretrain-lvd1689m` — a gated HF repo (Meta DINOv3 license click-through). User accepted terms + authenticated (`hf auth login`, user KariVidro); access request **awaiting Meta's review**. VERIFY blocked on that approval; a 5-min poller is watching and VERIFY re-runs automatically when granted.

**VERIFY:** PENDING — 512³ example inference blocked at DINOv3 download. Install itself complete.

**FINAL STATUS (2026-07-09): DEFERRED by user.** Meta's HF gate rejected access; user chose Meta-direct download, then decided not to wait and **declined the TRELLIS 1 fallback** — 3D generation is skipped entirely for now. TRELLIS.2 install retained dormant (repo, env, 16 GB weights); activation once DINOv3 is obtained = convert checkpoint to HF format + re-run `pipeline/checks/check_trellis2.py`. DINOv3 access poller left running (informational only). Phase 10 matrix will carry Phase 5 as "deferred (user decision)".

**DINOv3 gate timeline:** HF access request → status "awaiting review" → **rejected by Meta** (2026-07-09). User declined mirror workarounds (license-hygiene). Decision at gate: obtain the identical checkpoint via **Meta's direct distribution** (ai.meta.com DINOv3 form, same license, separate approval queue); Claude will convert `dinov3_vitl16_pretrain_lvd1689m.pth` to HF format via transformers' conversion script and point the pipeline at the local encoder. Setup holds at Phase 5 until then; HF poller kept running in case a re-request is granted.

**License review (user question):** DINOv3 License read from facebookresearch/dinov3 LICENSE.md — commercial use permitted, worldwide (no EU exclusion), royalty-free; outputs owned by user; restrictions: no military/ITAR/nuclear/espionage use, acknowledgment in publications, license must accompany redistributed weights/derivatives. Fits the project's use (inference-time encoder). Provenance-log line prescribed. Not legal advice; include in pre-launch legal review per PLAN.md §5.

**Deviation 7 (phase order):** user explicitly authorized continuing to Phase 6 while Phase 5's VERIFY awaits the external DINOv3 approval ("you can continue with other tasks", 2026-07-09). Phase 5 VERIFY remains an open item; will be closed before Phase 10's final matrix.

---

## Phase 6 — ComfyUI + image models — 2026-07-09 (in progress)

**Installed so far:**
- `~/apps/ComfyUI` (git clone, ComfyUI 0.27.0) + ComfyUI-Manager in `custom_nodes/`.
- `.venv` created from a conda-provisioned Python 3.12.13 (system python3 lacks `python3.12-venv`/ensurepip — avoided a sudo round-trip; Miniconda base is 3.14.6, too new for the dependency ecosystem). torch 2.13.0+cu130 + torchvision + torchaudio + requirements.txt + Manager requirements.
- Helpers written: `scripts/comfy-server.sh` (127.0.0.1:8188) and `scripts/comfy_txt2img.py` (HTTP API: queue → poll /history → save PNG; supports API-format workflow templates with placeholders).

**VERIFY part 1:** PASS — server starts; `/system_stats` reports "cuda:0 NVIDIA GeForce RTX 4090", 24 GiB VRAM. Part 2 (txt2img PNG) pending model downloads.

**GATE (models):** user selected **Qwen-Image-2.0** and **FLUX.2 [klein] 4B**. Research agents verified current install facts (all claims cited against HF API/file trees and docs.comfy.org):

1. **Qwen-Image-2.0 weights were never released** (API-only product; verified: no such HF repo exists). Substituted **Qwen-Image-2512** (Dec 2025 open release, Apache-2.0, PLAN.md §4.1 lists it explicitly). Files (Comfy-Org/Qwen-Image_ComfyUI, not gated): `qwen_image_2512_fp8_e4m3fn.safetensors` (20.4 GB → diffusion_models/), `qwen_2.5_vl_7b_fp8_scaled.safetensors` (9.4 GB → text_encoders/), `qwen_image_vae.safetensors` (254 MB → vae/), plus optional `Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors` LoRA (1.7 GB → loras/, lightx2v repo, Apache-2.0). Real size ~32 GB vs table's ~15–20 GB estimate — noted.
2. **FLUX.2 klein license trap averted:** official ComfyUI docs/template point the VAE at `Comfy-Org/flux2-dev` — tagged **flux-1-dev-non-commercial-license** (banned, rule 6). Pulled instead from Apache-2.0 sources: `black-forest-labs/FLUX.2-klein-4B` `flux-2-klein-4b.safetensors` (7.75 GB, distilled bf16 → diffusion_models/) + `Comfy-Org/vae-text-encorder-for-flux-klein-4b` `qwen_3_4b.safetensors` (8.04 GB → text_encoders/) and `flux2-vae.safetensors` (336 MB → vae/). Not gated, no click-through.

**Workflow settings (from official templates):** Qwen-2512: UNETLoader + CLIPLoader(type qwen_image) + ModelSamplingAuraFlow(shift 3.1) + EmptySD3LatentImage, KSampler euler/simple, steps 50 cfg 4.0 (Lightning: steps 4 cfg 1.0). klein distilled: UNETLoader + CLIPLoader(type flux2) + EmptyFlux2LatentImage, CFGGuider cfg 1 + SamplerCustomAdvanced/Flux2Scheduler steps 4, negative via ConditioningZeroOut. Templates written to `scripts/comfy-templates/{qwen2512,flux2_klein}.json` (API format, placeholder-driven).

**VERIFY (complete):** PASS —
1. Server starts (`scripts/comfy-server.sh`), `/system_stats` reports cuda:0 RTX 4090, 24 GiB.
2. `comfy_txt2img.py "a lunar habitat at dawn" --template flux2_klein.json` → valid 1024×1024 PNG (4 steps).
3. `comfy_txt2img.py --template qwen2512.json` → valid 1328×1328 PNG (50 steps, cfg 4.0). Both images visually inspected — coherent photoreal lunar-habitat scenes.

**Phase 6 complete** 2026-07-09. Downloads: Qwen set ~32 GB + klein set ~16 GB into `~/apps/ComfyUI/models/` (ext4, rule 9 respected).

---

## Phase 8 — Windows↔WSL bridges & glue scripts — 2026-07-09

*(Phase 7 pending user's sudo for the KTX .deb — .deb already downloaded; Phase 8 executed meanwhile under the user's standing "continue with other tasks" authorization, deviation 7.)*

**8a — `pipeline/blender/blender-win.sh`:** resolves newest `blender.exe` under `/mnt/c/Program Files/Blender Foundation/Blender 5.*`, converts absolute path args via `wslpath -w`, execs via WSL interop.
**VERIFY:** PASS — `-b --version` → **Blender 5.1.2** (Windows build); 64×64 Cycles render of default scene via `pipeline/blender/verify_render.py` → **OPTIX device "NVIDIA GeForce RTX 4090" use=True** (CPU/CUDA off), saved to `D:\renders\_verify\blender_win_64.png`, copied back to `~/datasets/_verify/`, valid 64×64 PNG. OptiX confirmed in use.

**8b — `pipeline/blender/sync-dataset.sh`:** rsync (cp fallback) from `D:\renders\<scene>` → `~/datasets/<scene>`.
**VERIFY:** PASS — dummy folder round-trip, `diff -r` clean.

**8c — Linux Blender in WSL:** SKIPPED per SETUP.md (only a fallback if 8a fails; 8a passed).

**8d — uv + MCP config:** uv/uvx 0.11.28 installed (`~/.local/bin`); `.mcp.json` written at repo root with `blender` (uvx blender-mcp) and `chrome-devtools` (npx chrome-devtools-mcp@latest) servers. Live `blender` server VERIFY deferred to Phase 9 as specified.

---

## Phase 7 — KTX-Software (toktx) — 2026-07-09

**Installed:** KTX-Software **4.4.2** (latest GitHub release, `KTX-Software-4.4.2-Linux-x86_64.deb`; .deb fetched by Claude, installed by user via sudo).

**VERIFY:** PASS — `toktx --version` → v4.4.2; 1024×1024 test PNG → `.ktx2` with `--encode etc1s`; `ktxinfo` parses it (KTX 20 identifier, supercompression KTX_SS_BASIS_LZ).

*(Executed after Phase 8 chronologically — sudo wait; content order per SETUP.md maintained in this log.)*

---

## Phase 9 — Windows assisted steps — 2026-07-09

**Block 1 — Splats extension:** installed by user via Get Extensions; verified on disk at `AppData\Roaming\Blender Foundation\Blender\5.1\extensions\blender_org\splats`.
**Block 2 — second COLMAP exporter (optional):** SKIPPED by user choice (Splats + planned own `export_dataset.py` suffice). BlenderNeRF not installed.
**Block 3 — Blender MCP addon:** `addon.py` fetched from ahujasid/blender-mcp to `C:\Users\karin\Downloads\blender-mcp-addon.py`; user installed via Install from Disk, enabled, clicked Connect. **Hyper3D and Hunyuan3D checkboxes confirmed OFF** (license policy PLAN.md §5).

**VERIFY:** PASS — raw-socket `get_scene_info` from WSL to `127.0.0.1:9876` returned `status: success` with the default scene (3 objects). **Mirrored networking works** (SETUP.md path (a)); no `BLENDER_HOST` fallback needed. The `.mcp.json` `blender` server (uvx blender-mcp, stdio→this socket) loads on next Claude Code session start in the repo.

---

## Phase 10 — Final verification & handover — 2026-07-09

All Phase 2–9 VERIFYs re-run in one batch (`phase10-verify.sh`). One check initially false-passed (gltfpack behind a pipe that masked its exit code); corrected and re-run strictly.

| Component | Version | Check | Result |
|---|---|---|---|
| CUDA toolkit (WSL) | nvcc 13.0 V13.0.88 | `nvcc --version` | ✅ |
| NVIDIA driver (Windows→WSL) | 581.57 / CUDA 13.0 | `nvidia-smi` shows RTX 4090 | ✅ |
| Node.js | v24.18.0 (LTS, nvm 0.40.5) | `node -v` | ✅ |
| gltfpack | 1.2 | usage+version output | ✅ (re-run strict) |
| splat-transform | 3.0.0 | `--help`/`--version` | ✅ |
| splat env: torch | 2.13.0+cu130 | check_gsplat.py | ✅ |
| splat env: gsplat | 1.5.3 @ git main, sm_89 | 1k-Gaussian rasterization finite/non-empty | ✅ |
| TRELLIS.2 | installed, dormant | — | ⏸ DEFERRED (user; DINOv3 gate) |
| ComfyUI | 0.27.0, torch 2.13.0+cu130 | `/system_stats` → RTX 4090 24 GiB | ✅ |
| Qwen-Image-2512 (fp8) | 2512, Apache-2.0 | txt2img 1328² PNG (50 steps) | ✅ |
| FLUX.2 klein 4B (bf16) | Apache-2.0 (VAE from klein repo, NOT flux2-dev) | txt2img PNG (4 steps) | ✅ |
| KTX-Software | toktx v4.4.2 | PNG→ETC1S ktx2 + ktxinfo | ✅ |
| blender-win.sh | Blender 5.1.2 (Windows) | `-b --version`; 64² Cycles render, OPTIX use=True | ✅ |
| sync-dataset.sh | — | D:→ext4 round-trip diff clean | ✅ |
| uv/uvx | 0.11.28 | `--version` | ✅ |
| .mcp.json | blender + chrome-devtools | file present | ✅ |
| Blender MCP (Phase 9) | addon connected, port 9876 | `get_scene_info` success via mirrored networking | ✅ |
| Splats extension | installed (blender_org/splats) | on-disk check | ✅ |

**Disk after setup:** WSL ext4 103 G used / 854 G free; C: 29 G free (above the 20 G user threshold; note C: dropped ~8 G during setup from Windows-side activity — nothing was staged there by this setup); D: 361 G free.

**Environment summary:** three isolated Python stacks — `splat` (conda, py3.11, torch cu130 + gsplat@main), `trellis2` (conda, py3.10, torch cu124 + compiled extensions, dormant), ComfyUI `.venv` (py3.12, torch cu130). CUDA toolkits 13.0 (default, gsplat) and 12.4 (TRELLIS builds) side-by-side. Node via nvm. Windows Blender 5.1.2 is the render engine (OptiX), bridged by `pipeline/blender/blender-win.sh`; datasets sync to ext4 via `pipeline/blender/sync-dataset.sh`.

**Open items:**
1. Phase 5 VERIFY deferred — TRELLIS.2 dormant pending DINOv3 (HF re-request or Meta-direct download; poller was left running, expires ~12 h from launch). Activation: convert checkpoint → HF format, point pipeline at local encoder, run `pipeline/checks/check_trellis2.py`.
2. ComfyUI server was stopped after verification; start with `scripts/comfy-server.sh`.
3. Blender must be running with the MCP addon connected for the `blender` MCP server to work in future sessions.

**Handover:** next session starts PLAN.md milestone **M0** (repo scaffold: Vite+TS app, CI with lint/typecheck/budget-check, deploy). **Priority flag for M2:** write `pipeline/blender/export_dataset.py` — our own bpy camera-rig + dataset exporter (Fibonacci-sphere cameras, `transforms.json`/COLMAP output, init point cloud) targeting Blender 5.1 / Python 3.13, so dataset export never depends on third-party add-on compatibility.

---

## Post-setup task — TRELLIS 1 activation (Phase 5 fallback) — 2026-07-10

**Goal:** activate TRELLIS 1 (MIT) as the working image→3D generator while TRELLIS.2 stays dormant pending DINOv3 access.

**License recon before install (rule 6):**
- TRELLIS 1's `setup.sh --mipgaussian` installs `diff-gaussian-rasterization` from autonomousvision/mip-splatting — **Inria-derived, non-commercial. EXCLUDED from install.**
- Verified the exclusion is safe: the Inria import is lazy (only inside `GaussianRenderer.render`); `to_glb` accepts a `Strivec` radiance field rendered by **diffoctreerast (Microsoft, MIT)**. Rule for all TRELLIS 1 use: `formats=['mesh', 'radiance_field']`, **never `'gaussian'`** (enforced by the package simply not being installed — requesting it raises ImportError).
- Encoder: DINOv2 `dinov2_vitl14_reg` via torch.hub (facebookresearch/dinov2, Apache-2.0, ungated) — confirmed, no gated model anywhere in the chain.
- Background removal: TRELLIS 1 natively uses **rembg/u2net (MIT)** — no RMBG anywhere in its code.
- xformers skipped (flash-attn is the attention backend); log deviation from README's example flags.

**Installed:** `~/apps/TRELLIS` (git clone --recursive, flexicubes submodule); conda env `trellis1` (Python 3.10, conda-forge); torch 2.4.0+cu124 + torchvision 0.19.0 (nvcc 12.4 aligned); flash-attn (prebuilt wheel); kaolin 0.18.0 (NVIDIA torch-2.4.0 wheel index); spconv-cu120 2.3.6; nvdiffrast 0.4.0; diffoctreerast (source, MIT); rembg + onnxruntime; utils3d @pinned commit. Weights: `microsoft/TRELLIS-image-large` (3.07 GiB — under the 5 GB gate threshold, no GATE required; largest single download torch ~3 GB). Post-install check: `pip list` contains no diff-gaussian/mip/RMBG packages.

**VERIFY (`pipeline/checks/check_trellis1.py`):** PASS —
- model load 56.8 s (first run incl. DINOv2 + u2net auto-download); generation **6.9 s**; GLB export (100-view radiance-field texture bake + xatlas UV) **18.6 s**;
- peak VRAM: 10.4 GiB (torch allocator) / 17.3 GiB (nvidia-smi, whole GPU);
- output `~/apps/TRELLIS/verify_out/verify_trellis1.glb`, 2.4 MiB, valid.

**TRELLIS.2 rembg patch (dormant repo):**
- Upstream `pipeline.json` (HF snapshot) requests `briaai/RMBG-2.0` for background removal — **CC BY-NC 4.0, non-commercial, banned.** Never downloaded on this machine.
- Added `trellis2/pipelines/rembg/rembg_mit.py` (class `RembgU2Net`, rembg/u2net, MIT; BiRefNet-compatible interface) and a license guard in `trellis2_image_to_3d.py::from_pretrained` that substitutes it whenever the config requests RMBG-2.0 (survives HF cache refreshes, unlike editing the hash-linked snapshot JSON). `rembg`+`onnxruntime` installed into the trellis2 env; import smoke-tested.
- **TRELLIS.2 pending DINOv3 access; on grant, review Meta's DINOv3 license terms and record them in provenance before commercial use.**

**PLAN.md §5 updated:** matrix rows added/split — TRELLIS 1 active (✅ with notes), TRELLIS.2 dormant (⏸ pending DINOv3), briaai RMBG-2.0 (❌ never), mip-splatting diff-gaussian-rasterization (❌ never); stack notes paragraph added above the hygiene rules.

---

## Rehearsal — end-to-end pipeline dry run (PLAN.md §11) — 2026-07-10

Chain: Blender scene → known-pose dataset → gsplat train → SuperSplat (user) → SOG → Babylon viewer.

**Stage 1 — dataset (`pipeline/rehearsal/make_scene.py`, seed of the future `export_dataset.py`):**
primitives + sun + Cycles/OptiX on Windows Blender via `blender-win.sh`; 120 golden-angle hemisphere cameras (elev 15–70°, r=8, aimed at scene center); 800×800, 64 samples + denoise. Output: COLMAP text dataset (PINHOLE f≈888.9 px; world→cam OpenGL→OpenCV conversion) + 1,540-point init cloud from mesh vertices with material colors. **Render 179 s total (~1.5 s/frame).** Synced D:→ext4 with `sync-dataset.sh` (66 MB).

**Stage 2 — training (`splat` env, gsplat simple_trainer MCMC, cap 300k, 10k iters):**
**1 min 45 s** (94.7 it/s). Val: **PSNR 38.5 / SSIM 0.994 / LPIPS 0.018**; 150,243 gaussians → `~/datasets/rehearsal/results/ply/point_cloud_9999.ply` (35.5 MB). The high PSNR confirms the pose-export math is exact (no COLMAP solve anywhere).

**Stage 3 — SuperSplat cleanup (user, superspl.at/editor):** 150,243 → **99.3K** splats; exported `D:\renders\rehearsal\rehearsal.sog` — **3.57 MB (~90% smaller than the PLY)**.

**Stage 4 — SOG → web:** `splat-transform` round-trip verified the SOG (99.3K gaussians, 3 SH bands, parsed in 0.125 s). `pipeline/rehearsal/web/viewer.html` (Babylon.js CDN, ArcRotateCamera) served at `http://localhost:8321/viewer.html` via python http.server (reachable from the Windows browser thanks to mirrored networking). Visual confirmation: pending user.

**Friction log (for M2 automation):**
1. gsplat `examples/requirements.txt` pins `torch==2.9.1` — installing it verbatim would have downgraded/broken the cu130 gsplat build. Installed a hand-picked dep subset instead; `nvidia-ncore`, `ppisp`, `fused_bilagrid` are optional backends (unused, licenses unreviewed) — skipped.
2. `fused-ssim` needs `--no-build-isolation` (torch import at build time), same pattern as flash-attn.
3. The OpenGL→OpenCV pose conversion in make_scene.py is the one piece of nontrivial math; keep it in one place when it grows into `export_dataset.py`.
4. LPIPS weights auto-download on first trainer run (~0.5 GB, one-time).
5. Whole chain, excluding user editing time: **~6 minutes**. No blockers.

**Stage 4 addendum — Babylon viewer quality investigation (2026-07-10):**
Symptom: SOG (and to a lesser degree PLY) looked softer in Babylon than in SuperSplat; SOG additionally showed color mottling (blotchy background, noisy sphere). Diagnosis via A/B files + screenshots + Babylon source reading:
1. **Sharpness:** Babylon's `GaussianSplattingMaterial.compensation` (dilation opacity compensation, PlayCanvas-style) defaults to **false** → fat/soft splats. Setting `compensation = true` (viewer default now) matches SuperSplat's look. `kernelSize` 0.3 and `minPixelSize` 0 already match PlayCanvas.
2. **SOG mottling:** SH loads correctly everywhere (shDegree 3 confirmed in HUD for PLY and SOG, CPU and GPU decode paths) — the mottling is **SOG SH quantization** rendered less forgivingly by Babylon. Fix for diffuse scenes: strip SH (`splat-transform -H 0`) → `rehearsal-sh0.sog`, **3.57 MB → 0.79 MB**, mottling source removed. Fix for hero scenes: export cleaned **PLY** from SuperSplat and encode SOG locally with `splat-transform -i 50` (SH compression iterations; SuperSplat's own export uses few). User visual confirmation of sh0 variant: pending (session ended here).
3. Viewer (`pipeline/rehearsal/web/viewer.html`) now has URL toggles: `f=` file, `comp=0`, `kernel=`, `sogtex=1`; HUD reports engine/kernel/comp/shDegree. Serve with `cd pipeline/rehearsal/web && python3 -m http.server 8321`.

**Session end 2026-07-10:** rehearsal validated through all joints (dataset → train → clean → SOG → web); remaining cosmetic item is the user's verdict on the sh0/high-iteration SOG variants. Continuation notes in CLAUDE.md.

---

## M0 — repo, CI, GitHub Pages deploy — 2026-07-10

**Repo:** `git init -b main` in `~/dev/space-catalogue`; repo-local identity Kari Nöjd <kari.nojd@vidro.fi> (no global git identity on this machine). Heavy dirs gitignored: `assets_src/`, `jobs/`, rehearsal `*.ply`/`*.sog`, `.claude/settings.local.json`.

**Web app:** `apps/web` — Vite 7 + TypeScript 5.8 (strict) + ESLint 9 flat config, npm workspace from repo root (root scripts: `dev/build/lint/typecheck/budgets`; non-interactive shells need `. ~/.nvm/nvm.sh`). Node v24.18.0 / npm 11.16.0. No Babylon on the landing route (lazy-loads in M1, PLAN.md §3). esbuild postinstall needed `npm approve-scripts esbuild` (allow-scripts guard).

**Budget checker:** `pipeline/pack/check-budgets.mjs` + `budgets.json` (PLAN.md §6 values; gz initial route, engine chunk by `/babylon/i` name, `.sog`/`.glb` tiered by `-m`/`-d` suffix, untiered ⇒ mobile budget). Fail path VERIFIED locally: 5 MB fake GLB passes as `-d`, fails as `-m` with exit 1.

**GitHub:** gh CLI 2.45.0 (Ubuntu apt, `noble-updates`). Device-flow auth as **Kari-N0**; default scopes lacked `workflow` (push containing `.github/workflows/` was rejected) → `gh auth refresh -s workflow` second device-flow round. `gh auth setup-git` wires the credential helper. Public repo: **https://github.com/Kari-N0/space-catalogue**. Pages enabled via API (`gh api -X POST repos/…/pages -f build_type=workflow`) — no UI clicks needed.

**CI (`.github/workflows/ci.yml`):** lint → typecheck → build → budgets on push/PR; Pages deploy from `main`. First run FAILED — real bug: build uses job-wide `BASE_PATH=/space-catalogue/` (Pages project-site sub-path), checker joined the `/space-catalogue/assets/…` URL refs onto `dist/` verbatim (ENOENT). Fixed: checker strips the `BASE_PATH` prefix (build and checker share the job-wide env); verified locally under both base-path and root builds. Second run: **success**, checks 26 s + deploy.

**VERIFY (live):** https://kari-n0.github.io/space-catalogue/ → 200, correct title, JS (825 B) and CSS (661 B) both 200. Initial route 1.3 KB gz of 200 KB budget. **M0 done-criterion met: push to main → automatic deploy.**
