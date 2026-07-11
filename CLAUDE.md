# Project: Space Engineering Catalogue

Visual-first web catalogue of space/future engineering concepts: Babylon.js + Gaussian splats (SOG) + PBR meshes, produced by a local RTX 4090 pipeline (WSL2 + Windows Blender). **PLAN.md** = full plan & budgets. **SETUP.md** = environment bootstrap doc. **setup-log.md** = what is actually installed, all versions, VERIFY results, and every deviation — read it before assuming anything about this machine. **ADDON.md** = spec for the "Catalogue Tools" Blender add-on (milestone M2.5, runs after the M3 vertical slice).

Stack (per PLAN.md): Vite + TypeScript + Babylon.js (v9, WebGPU→WebGL2 fallback), static site, content-driven from `content/concepts/*.json`. Web app lives in `apps/web` (npm workspace from repo root; **no Babylon on the landing route** — engine lazy-loads on first 3D interaction). **Current phase: asset creation (M1 viewer core ON HOLD per Kari, 2026-07-10).**

## Machine & environments (all verified 2026-07-09/10)

- Windows 11 25H2 + WSL2 Ubuntu 24.04, RTX 4090 (24 GB), driver CUDA 13.0. WSL disk is roomy (~850 GB free); **C: is nearly full — never stage files on C:**; Windows staging is `D:\renders`.
- CUDA toolkits side-by-side: **13.0 default** (`/usr/local/cuda`) and **12.4** (for TRELLIS builds; `CUDA_HOME=/usr/local/cuda-12.4`).
- conda (conda-forge ONLY — Anaconda ToS declined; never re-add `defaults`):
  - `splat` — py3.11, torch 2.13.0+cu130, **gsplat @ git main** (sm_89), gsplat-trainer deps. Training env.
  - `trellis1` — py3.10, torch 2.4.0+cu124. **Active image→3D generator** (TRELLIS 1, `~/apps/TRELLIS`).
  - `trellis2` — py3.10, torch 2.6.0+cu124. **DORMANT** (TRELLIS.2, `~/apps/TRELLIS.2` + 16 GB weights cached) — blocked on gated DINOv3 encoder (Meta rejected HF request; Meta-direct download pending). On grant: convert checkpoint to HF format, run `pipeline/checks/check_trellis2.py`, record DINOv3 license in provenance.
  - `py312` — utility interpreter that backs ComfyUI's venv. Don't delete.
  - `terrain` — py3.12, rasterio + pyproj + openexr-python + pillow. DEM→displacement tooling (`pipeline/terrain/`).
- ComfyUI `~/apps/ComfyUI` (own `.venv`, torch 2.13+cu130) with **Qwen-Image-2512** (fp8) and **FLUX.2 klein 4B** (+ 4-step Lightning LoRA for Qwen).
- Node LTS via nvm (non-interactive shells must `. ~/.nvm/nvm.sh` first): gltfpack, @playcanvas/splat-transform.
- Windows Blender **5.1.2** with Splats extension + Blender MCP addon (port 9876; `.mcp.json` configures the `blender` MCP server — Blender must be running with the addon connected).

## Commands

- Web app (repo root, needs `. ~/.nvm/nvm.sh` in non-interactive shells): `npm run dev` / `build` / `lint` / `typecheck` / `budgets` (budget checker: `pipeline/pack/check-budgets.mjs`, limits in `budgets.json` — CI-enforced, never raise a budget to pass)
- ComfyUI server: `scripts/comfy-server.sh` → txt2img: `scripts/comfy_txt2img.py "<prompt>" --template scripts/comfy-templates/{qwen2512,flux2_klein}.json` (qwen: `--steps 50 --cfg 4.0 --width 1328 --height 1328`; klein: `--steps 4 --cfg 1.0`)
- Windows Cycles render from WSL (full OptiX): `pipeline/blender/blender-win.sh -b --python <script>` (converts absolute path args via wslpath)
- Dataset D:→ext4: `pipeline/blender/sync-dataset.sh <scene>` (training I/O must be on ext4, never /mnt/*)
- Splat training: `cd ~/apps/gsplat/examples && ~/miniconda3/envs/splat/bin/python simple_trainer.py mcmc --data_dir <colmap-dir> --data_factor 1 --result_dir <out> --max_steps 10000 --save_ply --ply_steps 10000 --disable_viewer --strategy.cap-max 300000`
- Env smoke tests: `pipeline/checks/check_gsplat.py` (splat env), `check_trellis1.py` (trellis1 env, cwd ~/apps/TRELLIS, PYTHONPATH=~/apps/TRELLIS), `check_trellis2.py` (dormant)
- Rehearsal viewer: `cd pipeline/rehearsal/web && python3 -m http.server 8321` → http://localhost:8321/viewer.html (params: `f=`, `comp=0`, `kernel=`, `sogtex=1`)

## Hard rules (license — PLAN.md §5; violations = stop and report)

- **Never** Inria/graphdeco 3DGS code, incl. `diff-gaussian-rasterization` (TRELLIS 1's `--mipgaussian` flag — NOT installed). TRELLIS 1 must run `formats=['mesh', 'radiance_field']` — **never `'gaussian'`**.
- **Never** Hunyuan3D (EU-excluded), **never** FLUX [dev] weights — incl. the trap: official ComfyUI docs point the FLUX.2 klein VAE at `Comfy-Org/flux2-dev` (non-commercial); ours came from the Apache-2.0 klein repo.
- **Never** briaai RMBG-2.0 (CC BY-NC) — TRELLIS.2 code carries a guard substituting rembg/u2net (MIT).
- Every generated asset gets a provenance JSON (tool, model+version, prompt/seed, date, license at generation time) — pipeline/provenance/ (to be built in M2).
- Asset budgets in PLAN.md §6 are CI-enforced once M0 lands; never raise a budget to pass.

## Splat pipeline learnings (from the validated rehearsal, 2026-07-10)

- `pipeline/rehearsal/make_scene.py` is the seed of `pipeline/blender/export_dataset.py` (**M2 priority**): golden-angle hemisphere rig, COLMAP text export, OpenGL→OpenCV pose conversion (the one nontrivial bit — PSNR 38.5 proved it exact), init cloud from mesh vertices. Camera envelope definition must be shared with the web viewer limits.
- gsplat `examples/requirements.txt` pins `torch==2.9.1` — installing it verbatim would break the cu130 env. Trainer deps are already hand-installed; don't re-run their requirements file.
- Babylon splat rendering: set `material.compensation = true` (defaults false; without it splats look soft), `kernelSize` 0.3. SOG SH quantization can show as color mottling in Babylon: for diffuse scenes strip SH (`splat-transform -H 0`, huge size win); for hero scenes export cleaned **PLY** from SuperSplat and encode locally with `splat-transform -i 50`.
- Full chain timing (toy scene): render 120 views 3 min → train 10k iters 105 s (PSNR 38.5) → SOG 3.6 MB (0.8 MB without SH).

## Where we left off (2026-07-10, evening)

1. **M0 COMPLETE.** Public repo **https://github.com/Kari-N0/space-catalogue** (gh CLI authed as Kari-N0, credential helper wired), CI (lint/typecheck/build/budgets) + GitHub Pages deploy verified live: **https://kari-n0.github.io/space-catalogue/**. Push to `main` = deploy. CI builds with job-wide `BASE_PATH=/space-catalogue/` (Pages sub-path) — build and budget checker must share it; details in setup-log.md "M0" entry.
2. Rehearsal cosmetic question still open: user's verdict on `rehearsal-sh0.sog` / high-`-i` SOG variants (files in `pipeline/rehearsal/web/`, gitignored).
3. **Current phase: asset creation** (Kari's call, 2026-07-10) — **M1 (viewer core) is ON HOLD**; resume it when Kari says so. Asset work uses the already-validated tools: ComfyUI reference images, GN modeling in Blender, TRELLIS 1 image→3D (mesh+radiance_field only), rehearsal splat chain for scene tests. Outputs go to `assets_src/` (gitignored) / `D:\renders` staging; every generated asset still needs its provenance JSON (hard rule) even though the M2 provenance tooling isn't built yet — write them by hand.
4. After the asset phase: M1, then M2 scripts incl. `export_dataset.py`. **All M2 pipeline scripts must be importable functions with a thin argparse main (not just CLIs)** — the M2.5 Blender add-on (ADDON.md) calls them in-process; bpy-side scripts must stay ML-free so Blender never imports the ML stack.
5. Background: TRELLIS.2 activation when DINOv3 arrives (see setup-log.md Phase 5 for the exact procedure).
