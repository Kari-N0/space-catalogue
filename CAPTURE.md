# CAPTURE.md — splat capture system

Vantages are authored **visually in Blender** (Kari); the tools sample, validate,
preview, render, train, and export — they never make framing decisions. This doc
is the contract for `pipeline/blender/capture/` (bpy side, ML-free),
`pipeline/splats/run_capture.py` (WSL execute), and
`pipeline/pack/envelope_to_concept.py` (web contract merge).

**The hard rule (also in CLAUDE.md): the training envelope and the runtime
camera envelope are always generated from the same source object** — the
`ENV_`/`FOCUS_` pair of a capture vantage. Nobody hand-syncs limits.

## 1. Authoring convention (in the .blend)

```
capture                          ← root collection (never renders — enforced)
  CAPTURE_<vantage>              ← one collection per vantage; config lives here
    ENV_<vantage>                ← envelope volume mesh: WHERE CAMERAS MAY EXIST.
    FOCUS_<vantage>              ← look-at empty = orbit target = dataset origin
    PREVIEW_<vantage>            ← transient frustum markers (tool-owned)
    CAPTURE_<vantage>__<object>  ← nested child rig (close-up orbit of one object)
      ENV_<vantage>__<object>    ← auto-fitted sphere (bounds + standoff), editable
      FOCUS_<vantage>__<object>  ← auto at object bounds center, editable
```

- Vantage names: `[a-z0-9-]+` (they become dataset paths + JSON keys).
- **ENV meshes**: closed volumes, any shape, modifier-free; move/scale/sculpt
  freely. Wireframe display, never rendered.
- Config = custom properties on the `CAPTURE_` collection: select it in the
  Outliner → Properties ▸ Collection ▸ Custom Properties (each key has a
  tooltip). `preset` picks the quality tier; `views`/`resolution`/`samples` = 0
  means "use the preset"; `distance_shells_m` are the orbit radii from FOCUS.
- Proxy/stand-in objects are scene content — never under `capture/`.
- `CAM_*` names stay Kari's; the tools use `CAPTURE_/ENV_/FOCUS_/PREVIEW_/PRV_*`
  and a temporary `capture_cam` during headless renders only.

Create things (MCP or Python console; the future N-panel wraps the same calls):

```python
import sys; sys.path.insert(0, r"\\wsl.localhost\Ubuntu-24.04\home\karin\dev\space-catalogue")
from pipeline.blender.capture import convention, preview
convention.create_vantage("overlook", focus=(5842.5, -4882.5, 1662.0), preset="draft")
convention.create_child_rig("overlook", "fsh_base")     # from an object in the scene
preview.run_preview("overlook")                          # markers + stats, no renders
```

## 2. Quality presets & expected times (this machine)

| preset   | views (parent/child/bridge) | render      | Cycles smp | train (MCMC)        | est. render | est. train |
|----------|-----------------------------|-------------|------------|---------------------|-------------|------------|
| draft    | 100 / 60 / 15               | 1080×1080   | 64         | 10k iters, cap 500k | ~25–35 min  | ~4 min     |
| standard | 200 / 120 / 25              | 1440×1440   | 128        | 20k iters, cap 1.0M | ~2–2.5 h    | ~20 min    |
| hero     | 320 / 180 / 40              | 1920×1920   | 192        | 30k iters, cap 2.0M | ~5–6 h      | ~45–60 min |

Estimates anchor on two measurements: the terrain audition (7 s/frame @
1280×720, 64 smp, this terrain, OptiX) and the rehearsal training run (105 s /
10k iters @ cap 300k, 800²). Renders scale ≈ linearly with pixels × samples;
`use_persistent_data` is on so re-export overhead stays flat. **The draft
rehearsal re-measures both numbers; update this table from its
`capture-meta.json` timing block.** Margins: every dataset renders slightly
past the playback envelope (`train_margin_radius_pct` ±5 %, plus one ring
`train_margin_beta_deg` 5° below the lowest playback ring) so splat quality
doesn't collapse exactly at the runtime clamp. Margin samples relax the height
floor to `max(clearance_m, min_height_m/2)` — a height-limited playback edge
(the flat-terrain norm) would otherwise reject every below-the-edge sample.
Margins never widen viewer limits.

## 3. Coordinate contract (single source: `capture/frames.py`)

```
capture/COLMAP frame:  p_d = RX90 · (p_blender − FOCUS)      RX90: (x,y,z)→(x,−z,y)
Babylon viewer world:  p_v = (dx, dz, dy) of d = p_blender − FOCUS
                       (the SOG loader applies node scaling.y = −1; pinned @babylonjs 9.16.1)
envelope terms:        beta_deg  = angle from Blender +Z   (90 = horizon)
                       alpha_deg = atan2(d.y, d.x)          (Blender azimuth from +X)
```

Consequences:
- The trained PLY/SOG is **already correctly oriented and meter-true**; the
  splat needs no manual reorientation anywhere (verified in the 2026-07-14
  rehearsal: dataset loads upright in LichtFeld Studio, no orient step).
- **Splat editing (LichtFeld Studio / SuperSplat) = clean/crop ONLY. Never
  rotate, translate, or set pivot/orientation** — the frame IS the contract.
- **The optional gsplat path must run with `--no-normalize-world-space`**
  (run_capture pins it). gsplat's default world normalization bakes a
  recenter+rescale+PCA rotation into the PLY and silently breaks everything
  above. The same trap must be ruled out for any new trainer: **the first
  .sog exported from a new tool gets verified meter-true + upright in the web
  viewer before anything ships.**
- `content/concepts/<id>.json` gets the friendly camera block from the SAME rig
  samples (playback set only): `look_at_m` `[0,0,0]`-centered on FOCUS,
  `distance_m` min/max, `angle_up_down_deg` (floored at 2° from zenith),
  `angle_around_deg` (free 360° when azimuth coverage has no gap ≥ 30°,
  else the covered arc re-anchored near the viewer's default −90°),
  child rigs → `camera.object_envelopes.<key>`.
- `pipeline/checks/check_capture.py` pins all of this with fixtures — run it on
  plain python3 after touching frames.py, and re-review
  `apps/web/src/viewer/cameraEnvelope.ts` together with it.

## 4. Preview mode (nothing renders without Kari's go)

`preview.run_preview("<vantage>")` samples the rig (deterministic: fibonacci
shells → validity filters → farthest-point downsample), spawns color-coded
frustum markers (parent shells blue→green ramp, child rigs purple/red ramp,
bridge yellow, margins gray) and prints + stores (`CAPTURE_STATS_<vantage>`
text block) the stats readout: per-shell kept/requested with rejection
breakdown (outside_env / below_terrain / low_height / clearance / standoff /
los), max azimuth gap, the derived runtime envelope, and warnings.

Validity: cameras must be inside ENV, ≥ `min_height_m` above terrain
(evaluated mesh; interactive preview tightens all thresholds by ±2 m for the
viewport-vs-render subdiv gap, headless export re-validates at render subdiv),
≥ `clearance_m` from all render geometry, ≥ `standoff_min_m` from a child rig's
target, and (when `require_los`) with an unobstructed line to FOCUS.

Adjust ENV/FOCUS/properties → re-run → repeat until happy. The readout prints a
**rig hash** — that hash is the approval token: give it with your go, and
execute refuses to render anything else (Blender runs with `--python-exit-code`
so a refusal also fails the job). The hash covers configs, ENV meshes, FOCUS
positions, seed, AND the render-visible scene objects — hiding/moving geometry
after approval voids it. Note: export re-validates at render-subdiv fidelity,
so its accepted set can differ from the preview's within the ±2 m tolerance
band; the envelope in the dataset's own `capture-meta.json` is the
authoritative one (it describes the views actually trained).

## 5. Execute mode

```
python3 pipeline/splats/run_capture.py --blend <path.blend> --vantage <name> \
        --approved-rig <hash>     # [--train-gsplat] [--dry-run] [--skip-render/-sync/-train]
```

**Default flow (LichtFeld Studio — Kari's training/cleaning tool, 2026-07-14):**
render-dataset (blender-win.sh `--factory-startup`, Windows Cycles/OptiX,
capture/ force-hidden, scene look untouched) →
`D:\renders\<concept>\capture\<vantage>\lichtFeld\` — a **drag-and-drop LFS
dataset**: `cameras.txt`/`images.txt`/`points3D.txt` at the folder root +
`images/` + `output/` (plus a `sparse/0/` twin of the text files so the same
folder is a standard COLMAP root). Kari drops the folder into LFS, trains,
cleans (crop/clean ONLY), exports `.sog` directly. LFS is a native Windows app
reading D:\ — the ext4 rule governs WSL-side training only. LFS license
checked 2026-07-14: GPLv3 app (fine for producing commercial assets), gsplat/
Apache-2.0 rasterizer lineage, Inria cited as research only — nothing
non-commercial in THIRD_PARTY_LICENSES.md.

**`--train-gsplat` (validation/automation path):** + sync-dataset.sh (ext4) →
gsplat MCMC (splat env, preset params, `--no-normalize-world-space`) → PLY
copied to `D:\...\<vantage>_<preset>.ply`; report adds splat counts + PSNR.

Job status: `jobs/<yyyymmdd-hhmmss>-capture/status.json` (ADDON.md §6 schema —
the future add-on panel polls it unchanged; write `cancel` into `control` to
stop between stages).

After Kari's LFS pass: name the shipped file `<something>-d.sog` for the
desktop budget tier (40 MiB raw; anything else is checked as mobile, 15 MiB),
respect the >20 MB placeholder STOP rule, and record the pack stage (LFS
version, training/export settings, "clean by Kari <date>") in
`pipeline/provenance/<concept>/capture-<vantage>.json` — its `pending_stages`
lists exactly what to fill in. The `splat-transform` re-encode path (`-i 50`
hero / `-H 0` diffuse) remains available for tuning SOG compression from an
LFS-exported PLY. Then merge the envelope:

```
python3 pipeline/pack/envelope_to_concept.py \
    --meta pipeline/provenance/<concept>/capture-<vantage>.envelope.json   # dry-run diff
    --apply                                                                # after review
```

The merge writes only the generated fields (target, distance min/max, angles,
object_envelopes, an audit note) and preserves everything Kari authored
(`start`, `controls`, `move_limit_m`, pins, copy, `zoom_fov_deg` unless
`--set-fov`), warning about stranded pins, out-of-arc feature angles, and
pan reach vs. the trained region.

## 6. Nested child rigs & assembly

`create_child_rig(vantage, object)` builds `CAPTURE_<vantage>__<object>`: a
spherical ENV auto-fitted to the object's evaluated bounds (shells =
bounds-radius × [2.5, 4, 6], standoff guard = max(0.5 m, 0.35 × radius) against
clipping into geometry), denser sampling (preset child counts), optional own
`resolution` override (multi-camera COLMAP datasets are supported by the gsplat
parser but flagged experimental until validated — the rehearsal keeps one
resolution). A **bridge shell** of intermediate views (geometric mean of the
parent's closest approach and the child's outer shell, aimed at the child
focus) is always generated — training glue between the two scales, exempt from
both ENV volumes, safety-checked like everything else.

`assembly` (parent vantage property):
- **merged** (default): one combined dataset → one training run → single splat.
  Pairs with streamed-SOG LOD for very large scenes (PLAN §4.5 step 6) — the
  draft rehearsal ships a flat single .sog; streamed-SOG bundling is decided
  together with the merged-vs-separate call after the rehearsal.
- **separate**: per-rig training → per-object splats carved and composited in
  the viewer (Babylon compound scene). **Not implemented yet** — schema slot
  reserved; build it only if the rehearsal's merged results argue for it.

Runtime side: child envelopes land in `camera.object_envelopes` and the viewer
exposes `focusObject(name)`/`clearObjectFocus()` (animated envelope swap, no
snap). **No page UI triggers them yet** — wiring (pin click? button?) is
Kari's interaction decision.

## 7. Rehearsal (status 2026-07-14: dataset rendered + approved, LFS pass running)

Progress log: rig approved (`8b70305046fb`, 227 views), rendered in 17 min
(4.4 s/frame @ 1080²/64 smp — preset table to be recalibrated), orientation
verified upright in LichtFeld Studio with zero manual orient steps. gsplat
validation train: 253,809 splats, 58,962 inside the boulder zoom envelope,
val PSNR 26.0 (draft). Kari trains/cleans/exports in LFS; remaining checks:
meter-true scale of the first LFS .sog in the web viewer, scale-gap
inspection at 30 m / 19 m / 5.4 m, merged-vs-separate call, placeholder swap.

Original plan:

Plan (Kari 2026-07-13): one vantage on the bare site11 terrain, draft preset,
one placeholder proxy object with a child rig, **merged** path end-to-end
through Kari's SuperSplat pass to a .sog — then STOP. Production captures wait
until the scene is dressed and lookdev locks the sun.

- Working file: `terrain_site11_v004.blend` (v003 untouched — Kari's file).
- FOCUS position and the proxy (`proxy_boulder`) placement are **utility
  defaults** presented at the preview STOP for Kari to move; in production,
  parent FOCUS placement is always Kari's.
- Report template for the merged-vs-separate judgment: total splats, splats
  within the child ENV radius, PSNR, s/frame, plus viewer screenshots at
  parent-min / bridge / child-min distances (scale-gap artifact check).
- If the SOG is decent: swap it in as the template placeholder (JSON
  `scene_file` path change; `-d.sog` naming; budgets + 20 MB placeholder gate),
  run `envelope_to_concept.py --apply`, proxy provenance recorded as
  non-deliverable rehearsal prop inside `capture-rehearsal.json`.

## 8. Catalogue Tools add-on (after the rehearsal survives)

Capture becomes **module 1** of the "Catalogue Tools" Blender 5.1 extension
(ADDON.md): N-panel tab in the 3D viewport, thin UI over exactly the functions
above (create/duplicate vantage, add child rig from selection, preset dropdown,
Preview + stats, Execute with confirm → launches run_capture headless, job
status from `jobs/*/status.json`, export-envelopes button). No logic forks into
the add-on; it never imports the ML stack (ADDON.md §1 rules). Location: Kari's
spec says `pipeline/blender/addons/catalogue_tools/`, ADDON.md §2 said
`addon/` — **pending Kari's call** (newer spec text favors `addons/`).
Tracked as a deliverable in `assets_src/lunar-base/ASSETS.md`.

## 9. Module map

```
pipeline/blender/capture/
  frames.py           pure math — THE coordinate/envelope contract (+ hashes)
  presets.py          pure — preset table + config resolution (render AND train)
  convention.py       bpy — create/find vantages & child rigs, config, checks
  validity.py         bpy — world-space BVHs: terrain height, clearance, LOS,
                      ENV containment (scene.ray_cast is banned here)
  rig.py              bpy — deterministic sampling: shells, margins, bridges
  preview.py          bpy — markers + stats + approval hash
  export_dataset.py   bpy headless — renders + COLMAP + meta (gate enforced)
  export_envelope.py  bpy — envelope sidecar without rendering
  _reload.py          dev — reload package in a live Blender session
pipeline/splats/run_capture.py    WSL execute orchestrator (job status files)
pipeline/pack/envelope_to_concept.py   sidecar → concept JSON merge (dry-run first)
pipeline/checks/check_capture.py  contract fixtures (plain python3)
```
