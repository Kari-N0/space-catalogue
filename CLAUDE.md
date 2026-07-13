# Project: Space Engineering Catalogue

Visual-first web catalogue of space/future engineering concepts: Babylon.js + Gaussian splats (SOG) + PBR meshes, produced by a local RTX 4090 pipeline (WSL2 + Windows Blender). **PLAN.md** = full plan & budgets. **SETUP.md** = environment bootstrap doc. **setup-log.md** = what is actually installed, all versions, VERIFY results, and every deviation — read it before assuming anything about this machine. **ADDON.md** = spec for the "Catalogue Tools" Blender add-on (milestone M2.5, runs after the M3 vertical slice). **CAPTURE.md** = splat capture system (vantages, presets, preview/execute, envelope contract — supersedes ADDON.md §3's single-envelope model).

Stack (per PLAN.md): Vite + TypeScript + Babylon.js (v9, WebGPU→WebGL2 fallback), static site, content-driven from `content/concepts/*.json`. Web app lives in `apps/web` (npm workspace from repo root; **no Babylon on the landing route** — engine lazy-loads on first 3D interaction). **Current phases (2026-07-12): asset creation (Kari, in Blender) + web workstream (Claude owns `apps/web`; M1 resumed within it) running in parallel. Launch strategy: single-concept launch — PLAN.md §9 "Launch strategy" + M3.5.**

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

## Art direction boundaries (Kari, 2026-07-12 — absolute)

- **Claude never proposes or decides composition, camera angles, lenses, or shot framing.** Claude supports the camera envelope and shots Kari authors. Utility cameras for neutral review renders (turnarounds, validation views) are fine — they follow fixed documented defaults, never framing judgment.
- **Claude never modifies a .blend Kari has edited without asking first.** New work goes into new version files (`v002`, `v003`, …); the file Kari touched is theirs.
- **Claude never decides brand, theme, layout, or page sections (web).** Brand rules derive from vidro.fi via BRAND.md + design tokens that Kari approves; page/section structures are proposed as static mockups for Kari to pick from. Claude implements the approved choice and nothing beyond it.

## Web workstream rules (Kari in Blender in parallel — 2026-07-12)

- **All stand-in media comes from `apps/web/public/assets/placeholders/` exclusively; never generate or fetch other media. Go-live = JSON path swap + folder deletion.**
- Integration points only: `content/concepts/lunar-base.json`, Kari's drops into `assets/placeholders/`, and later final assets in `apps/web/public/assets/`. Never touch `assets_src/` or any `.blend` in this workstream.
- Commit often; push to `main` = continuous deploy to the dev URL (GitHub Pages) for Kari's phone review.
- Any placeholder file >20 MB: flag and STOP for Kari's compress-vs-LFS call before committing. (2026-07-12 round resolved: SOG renamed `-d` by Kari, video replaced by `rerender.mp4` 8.4 MiB; superseded `loop_video_placeholder.mp4` stays uncommitted.)
- **TEMPLATE LOCKED (Kari, 2026-07-13):** the production concept page is `apps/web/concept/` (`/concept/?id=<x>`), rendered 100 % from `content/concepts/<id>.json` by `src/catalogue/page.ts` + `src/styles/concept.css`. Kari edits JSON only (guide: `content/concepts/README.md`); new concept = new JSON file, zero code. `mockups/c2.html` is the frozen visual reference — visual changes must keep template and reference in agreement or retire the mockup with Kari's ok.
- **Viewer lazy boundary:** `apps/web/src/viewer/loadViewer.ts` is reached ONLY via dynamic `import()`; nothing under `src/viewer/` or `@babylonjs/*` may be statically imported from landing-route code. Engine chunks must keep "babylon" in their file names (budget-checker contract); Babylon deps stay exact-pinned; fflate is bundle-injected into the SOG loader and `spzLibraryUrl` pinned to undefined (never let it fetch from unpkg). Per Kari 2026-07-13: CONCEPT pages auto-init the viewer after the page `load` event (still via the dynamic boundary); the landing/grid route stays engine-free.

## Capture system rules (CAPTURE.md — workstream opened 2026-07-13)

- **The training envelope and the runtime camera envelope are always generated from the same source object** (a vantage's `ENV_`/`FOCUS_` pair). Never hand-sync limits between the rig and `content/concepts/*.json`; edits go into the .blend, then re-export (`pipeline/pack/envelope_to_concept.py`, dry-run first — it preserves Kari's authored fields).
- **Nothing renders without Kari's go**: preview prints a rig hash; `export_dataset.py`/`run_capture.py` refuse without `--approved-rig <that hash>` and on any mismatch.
- Splat training always runs `--no-normalize-world-space` (gsplat's default normalization bakes a recenter+rescale+rotation into the PLY and breaks the meter-true frame contract).
- SuperSplat pass on capture PLYs: **clean/crop only — never rotate/translate/set-pivot**; the capture frame is pre-oriented for the web viewer.
- Everything under the `capture` collection never renders (enforced at export); proxy/stand-in objects live outside it. `CAM_*` names remain Kari's.

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
5. Background: TRELLIS.2 activation when DINOv3 arrives (see setup-log.md Phase 5 for the exact procedure). 2026-07-12: Comfy-Org TRELLIS.2 repack ruled out on license grounds (setup-log.md entry + PLAN.md §5) — still TRELLIS 1 + Meta-direct application.
6. **Capture workstream opened 2026-07-13** (Kari's spec; CAPTURE.md). System BUILT + red-team-reviewed: `pipeline/blender/capture/` (bpy, ML-free), `pipeline/splats/run_capture.py`, `pipeline/pack/envelope_to_concept.py`, `pipeline/checks/check_capture.py` (all fixtures green), viewer `object_envelopes`/`focusObject` support (typecheck/lint/build/budgets green). Rehearsal vantage authored in `terrain_site11_v005.blend` (v003/v004 untouched — Kari's): draft preset, `proxy_boulder` child rig, merged assembly; preview run, rig hash `acb776ae19f9`. **GATE: awaiting Kari's preview sign-off — nothing renders until the hash is approved.** Then: execute → SuperSplat (clean/crop only) → .sog → placeholder swap + envelope `--apply`. Add-on (T02, ASSETS.md) gated on the rehearsal.
7. **Web workstream opened 2026-07-12** (see "Web workstream rules" above). Gates resolved 2026-07-12 evening: placeholders committed (SOG as `-d` tier), **BRAND.md APPROVED** (ref format "CONCEPT 001", credit nav+footer, single blue accent for status chips, two-tone hero yes), privacy draft approved. Still pending: **concept-page structure pick** (3 mockups at `/mockups/{a,b,c}.html` on the dev URL) and the **go-signal for creating the Brevo/analytics accounts** (services recommended: Brevo + Plausible or Simple Analytics; no accounts until Kari says so).
