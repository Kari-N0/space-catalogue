# SETUP.md — Environment Bootstrap for the Space Engineering Catalogue

**Audience:** Part 1 is for the human. Part 2 onward is written for **Claude Code to execute**.
**Target machine:** Windows 11, RTX 4090 (24 GB), Ryzen 9 5950X, 128 GB RAM, WSL2 Ubuntu 24.04.
**Architecture:** Interactive Blender **5.1+** on Windows · ML/training/web stack in WSL2 · Claude Code (in WSL) orchestrates both via scripts and WSL↔Windows interop.
**Companion document:** `PLAN.md` (project plan, license rules, budgets). Read it before Phase 0.

---

## PART 1 — Human bootstrap (manual, ~45 min, do once)

These are the steps Claude Code cannot do for you (admin rights, GUI installers, its own login).

1. **NVIDIA driver (Windows):** update to the latest Studio or Game Ready driver from nvidia.com. Do **not** plan to install any GPU driver inside WSL — WSL2 gets CUDA from this Windows driver.
2. **Check Windows version:** run `winver`. Windows 11 22H2 or newer is needed for WSL *mirrored networking* (used later for Blender MCP). Note your build.
3. **Install WSL2 + Ubuntu 24.04:** in an *admin* PowerShell: `wsl --install -d Ubuntu-24.04`. Reboot if asked, then create your UNIX username/password.
4. **Create `C:\Users\<you>\.wslconfig`** with:
   ```ini
   [wsl2]
   memory=96GB
   processors=24
   swap=32GB
   networkingMode=mirrored
   ```
   Then run `wsl --shutdown` once so it applies. (If mirrored mode is unsupported on your build, delete that line — Phase 9 has a fallback.)
5. **Install Claude Code inside WSL:** open the Ubuntu terminal and run `curl -fsSL https://claude.ai/install.sh | bash`, then run `claude` and complete login in the browser (requires a Pro/Max subscription or an API key; the free plan does not include Claude Code).
6. **Install Blender 5.1+ on Windows:** `winget install BlenderFoundation.Blender` in PowerShell, or download from blender.org. Launch it once so it finishes first-run setup.
7. **Create the project folder in WSL:** `mkdir -p ~/dev/space-catalogue` and place `SETUP.md` + `PLAN.md` inside it.
8. **Start the run:** `cd ~/dev/space-catalogue && claude`, then paste the kickoff prompt from the end of this file.

Everything below this line is executed by Claude Code. You'll be asked to confirm at GATEs and to perform three short GUI tasks in Phase 9.

---

## PART 2 — Instructions for Claude Code

### GROUND RULES (apply to every phase)

1. **Execute phases in order.** Do not skip. Do not parallelize across phases.
2. **Idempotent:** before installing anything, check whether it is already present and working; if so, verify and move on.
3. **VERIFY blocks are mandatory.** After each phase, run its VERIFY. If a check fails, diagnose and fix before advancing. Never advance past a failing VERIFY.
4. **GATE = stop and ask the user.** Required before: first `sudo` use, any download > 5 GB, any license/terms acceptance, anything destructive.
5. **Logging:** append to `setup-log.md` after every phase: date, what was installed, exact versions, VERIFY results, deviations from this document.
6. **License hard rules (from PLAN.md §5):** never install or clone the Inria/graphdeco `gaussian-splatting` repository (non-commercial license); never install any Hunyuan3D model or code (license excludes the EU); never download FLUX `[dev]` weights (non-commercial) — only `schnell`/`klein`. If a dependency chain pulls any of these in, STOP and report.
7. **Versions drift.** Commands here are known-good guidance, not gospel. If a tool's current official docs differ (torch/CUDA combos, install URLs), follow the official docs and note the deviation in the log. The *goal state* of each phase is what matters.
8. **Windows GUI tasks:** never attempt to click through Windows installers. Print precise instructions for the user, wait for their confirmation, then verify programmatically (file paths, versions, socket checks).
9. **Filesystem rule:** all repos, datasets, and training data live in the WSL ext4 filesystem (`~/...`), never under `/mnt/c/...` (the 9P mount is too slow for ML I/O). `/mnt/c` is only for exchanging files with Windows apps.

---

### Phase 0 — Preflight

Goal: confirm the machine matches assumptions before touching anything.

```bash
nvidia-smi                                  # driver + CUDA visible inside WSL
uname -r                                    # should contain "microsoft" (WSL2 kernel)
df -h ~ /mnt/c                              # need ≥ 250 GB free in WSL, ≥ 50 GB on C:
cmd.exe /c ver                              # log the Windows build
ls "/mnt/c/Program Files/Blender Foundation/"   # find installed Blender versions
```

Also: `curl -sI https://huggingface.co | head -1` (network), `nproc`, `free -h` (confirm .wslconfig applied: ~24 CPUs, ~96 GB).

**VERIFY:** `nvidia-smi` shows the RTX 4090 and a driver CUDA version ≥ 12.x; a Blender directory ≥ 5.1 exists; disk thresholds met. **GATE:** print a preflight summary table and get user confirmation to proceed.

---

### Phase 1 — System packages (WSL)

```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install build-essential git git-lfs cmake ninja-build pkg-config \
    curl wget unzip aria2 ffmpeg \
    libgl1 libegl1 libxi6 libxxf86vm1 libxfixes3 libxrender1 libsm6 libxkbcommon0
git lfs install
```

(The libx*/libgl packages are required later for headless Blender and ComfyUI image ops.)

**VERIFY:** `gcc --version`, `git lfs version`, `cmake --version`, `ffmpeg -version` all succeed.

---

### Phase 2 — CUDA toolkit (WSL, toolkit ONLY — never a driver)

gsplat compiles CUDA kernels, so `nvcc` is required. **Order of operations:** first check the gsplat README (github.com/nerfstudio-project/gsplat) for the currently supported PyTorch/CUDA combination, then install the matching `cuda-toolkit-<ver>` from NVIDIA's **WSL-Ubuntu** apt repository (the WSL-specific repo omits the driver). Add `/usr/local/cuda/bin` to PATH in `~/.bashrc`.

**VERIFY:** `nvcc --version` prints the chosen toolkit version; `nvidia-smi` still works (if it broke, a driver package was installed by mistake — remove it).

---

### Phase 3 — Node.js stack (WSL)

```bash
# nvm → Node LTS
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/master/install.sh | bash
source ~/.nvm/nvm.sh && nvm install --lts
npm i -g gltfpack @playcanvas/splat-transform
```

**VERIFY:** `node -v` (LTS), `gltfpack` (prints usage+version), `splat-transform --help` succeed.

---

### Phase 4 — Miniconda + gsplat training environment (WSL)

```bash
# Miniconda, silent
wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/mc.sh
bash /tmp/mc.sh -b -p ~/miniconda3 && ~/miniconda3/bin/conda init bash && source ~/.bashrc

conda create -y -n splat python=3.11
conda activate splat
# Install torch matching the Phase 2 CUDA version (check pytorch.org for the current index URL),
# then gsplat — prefer their prebuilt wheel index for the torch/CUDA combo; fall back to source build.
pip install torch torchvision --index-url <current-cu-matching-index>
pip install gsplat plyfile opencv-python-headless numpy typer rich
```

**VERIFY (write and run `pipeline/checks/check_gsplat.py`):**
1. `torch.cuda.is_available()` is True and device name contains "4090";
2. `import gsplat` succeeds;
3. rasterize 1,000 random Gaussians to a 128×128 image via `gsplat.rasterization(...)` on CUDA and confirm a finite, non-empty output tensor. Log gsplat/torch/CUDA versions.

---

### Phase 5 — TRELLIS.2 (local AI 3D generation)

**GATE:** weights are ~10–20 GB and dependency compilation can take 30–60 min. Confirm with the user.

Clone `microsoft/TRELLIS.2` into `~/apps/TRELLIS.2`, create conda env `trellis`, and follow the repo's own setup script (rule 7 applies — that README is the source of truth; prefer prebuilt wheels for heavy deps like attention kernels over source builds where offered). Download the `microsoft/TRELLIS.2-4B` weights via `huggingface-cli` (or let the pipeline auto-download on first run).

**VERIFY:** run the repo's example inference on one bundled sample image at **512³** resolution; confirm a `.glb` is produced; log generation time and peak VRAM (`nvidia-smi` during run). If VRAM is exceeded at higher resolutions, note that 1024³ is our production default and quantized community workflows exist — do not chase 1536³ now.

---

### Phase 6 — ComfyUI + image models

```bash
git clone https://github.com/comfyanonymous/ComfyUI ~/apps/ComfyUI
cd ~/apps/ComfyUI && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # torch per its README for CUDA
git clone https://github.com/ltdrdata/ComfyUI-Manager custom_nodes/ComfyUI-Manager
```

**GATE — model downloads (user picks, sizes approximate):**
| Model | Purpose | License | Size |
|---|---|---|---|
| Qwen-Image-2.0 (recommended) | Photoreal gen + edit, native 2K | Apache-2.0 | ~15–20 GB |
| FLUX.2 [klein] 4B *or* FLUX.1 [schnell] | Fast general gen | Apache-2.0 | ~8–13 GB |
| Z-Image Turbo (optional) | High-throughput batches | Apache-2.0 | ~6–12 GB |

Download with `huggingface-cli download` into the model directories the respective ComfyUI docs specify. **Never FLUX [dev].** If any repo is gated behind a click-through, stop at a GATE and have the user accept it on huggingface.co themselves.

Write two helpers: `scripts/comfy-server.sh` (launches `python main.py --listen 127.0.0.1 --port 8188`) and `scripts/comfy_txt2img.py` (queues a minimal text-to-image workflow via the HTTP API, polls `/history`, saves the PNG — this becomes the pipeline's programmatic entry point).

**VERIFY:** server starts; `curl 127.0.0.1:8188/system_stats` reports the 4090; `comfy_txt2img.py "a lunar habitat at dawn"` produces a PNG for at least one installed model.

---

### Phase 7 — KTX-Software (toktx)

Install the latest KTX-Software release for Ubuntu from github.com/KhronosGroup/KTX-Software/releases (`.deb`).

**VERIFY:** `toktx --version` succeeds; compress any test PNG to `.ktx2` (ETC1S) and confirm the file is valid via `ktxinfo`.

---

### Phase 8 — Windows↔WSL bridges & glue scripts

**8a — Windows Blender headless wrapper** (`pipeline/blender/blender-win.sh`): resolves the newest `blender.exe` under `/mnt/c/Program Files/Blender Foundation/Blender 5.*/`, converts path arguments with `wslpath -w`, and invokes it. This lets WSL-side automation run Cycles renders on Windows at full **OptiX** speed. (Rationale: OptiX under WSL is historically unreliable; Windows-side rendering avoids the issue entirely.)

**VERIFY:** `blender-win.sh -b --version` prints Blender ≥ 5.1; then render a 64×64 Cycles frame of the default scene via a tiny bpy script (`--background --python`), with output to a Windows temp dir, copy it back, confirm the PNG exists. Log whether OptiX device was used.

**8b — Dataset sync helper** (`pipeline/blender/sync-dataset.sh`): copies a finished render dataset from a Windows folder (e.g. `D:\renders\<scene>`) into `~/datasets/<scene>` (ext4) before training. Verify with a dummy folder round-trip.

**8c — Optional: Linux Blender in WSL** (`~/apps/blender/`, official 5.1+ Linux tarball): only as fallback; if used for Cycles, set the compute device to **CUDA, not OptiX**. VERIFY `-b --version`. Skip unless 8a fails.

**8d — MCP configuration:** install uv in WSL (`curl -LsSf https://astral.sh/uv/install.sh | sh`, new shell). Write `.mcp.json` at the repo root:

```json
{
  "mcpServers": {
    "blender": { "command": "uvx", "args": ["blender-mcp"] },
    "chrome-devtools": { "command": "npx", "args": ["chrome-devtools-mcp@latest"] }
  }
}
```

Live verification of the `blender` server is deferred to Phase 9 (needs the Windows-side addon running).

---

### Phase 9 — Windows assisted steps (print instructions, wait, then verify)

Print the following for the user, one block at a time, and wait for confirmation after each:

1. **Splats extension:** In Blender 5.1+ → Edit → Preferences → Get Extensions → search **"splats"** → Install + enable. (Official catalog only offers versions compatible with the running Blender.)
2. **Optional COLMAP-dataset add-on:** `neroforgeyt/gaussian_splat_add_on` (GitHub) explicitly requires Blender ≥ 5.1 and exports COLMAP-format 3DGS training datasets — install from its release .zip via Install from Disk if the user wants a second exporter. **BlenderNeRF:** only install if its releases explicitly state Blender 5.x support; otherwise skip — our own exporter (see Phase 10 note) replaces it.
3. **Blender MCP:** download `addon.py` from `ahujasid/blender-mcp` → Blender → Edit → Preferences → Add-ons → Install from Disk → enable "Blender MCP" → in the 3D viewport press N → BlenderMCP panel → **Connect** (starts the socket server on port 9876). Leave the panel's **Hyper3D** and **Hunyuan3D** checkboxes OFF (license policy, PLAN.md §5).

**VERIFY:** with Blender running and the addon connected, start a session using the `blender` MCP server and call its scene-info tool; confirm a valid response. If connection fails: (a) confirm `networkingMode=mirrored` took effect (`cat /etc/resolv.conf` trick no longer needed — just test `curl` to a Windows-bound port), or (b) fallback: set `BLENDER_HOST` in `.mcp.json` env to the Windows host IP. Log which path worked.

---

### Phase 10 — Final verification & handover

1. Re-run every VERIFY from Phases 2–9; write the full matrix (component / version / check / result) into `setup-log.md`.
2. Print a human-readable summary: what's installed, versions, disk used, any deviations.
3. **Handover pointer:** next session starts `PLAN.md` milestone **M0** (repo scaffold). Flag one priority task for M2: write `pipeline/blender/export_dataset.py` — our *own* bpy camera-rig + dataset exporter (Fibonacci-sphere cameras, `transforms.json`/COLMAP output, init point cloud), targeting the Blender 5.1 / Python 3.13 API — so dataset export never depends on third-party add-on compatibility again.

---

## Appendix — Troubleshooting quick reference

- **`nvidia-smi` missing in WSL** → update the *Windows* NVIDIA driver; never `apt install` a driver in WSL.
- **gsplat build fails** → nvcc/torch CUDA mismatch; reinstall torch for the toolkit version from Phase 2, or use gsplat's prebuilt wheel index.
- **Training I/O is slow** → dataset is sitting under `/mnt/c`; move it to `~` (ext4). Rule 9.
- **Cycles GPU render fails in WSL** → expected with OptiX; use CUDA there, or (default) render via `blender-win.sh` on Windows.
- **Blender MCP can't connect from WSL** → mirrored networking not active; use the Windows host IP as `BLENDER_HOST`, or run Blender MCP from Claude Desktop on Windows instead.
- **An add-on breaks after a Blender upgrade** → 5.x updates library versions (Python 3.13 in 5.1); check the extension page for an update, and remember our own `export_dataset.py` is the dependency-free path.

---

## Kickoff prompt (paste into Claude Code in `~/dev/space-catalogue`)

```
Read SETUP.md fully, then execute it phase by phase starting at Phase 0.
Follow the GROUND RULES section exactly: stop at every GATE, run every VERIFY,
never advance past a failing VERIFY, and log everything to setup-log.md.
Hardware: RTX 4090, Ryzen 9 5950X, 128 GB RAM, Windows 11 + WSL2 Ubuntu 24.04.
Blender 5.1+ is installed on Windows. Begin with Phase 0 now.
```
