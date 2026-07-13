# ADDON.md — "Catalogue Tools" Blender add-on (milestone M2.5)

Spec for the artist cockpit of the space-catalogue pipeline: a Blender 5.1 add-on that
puts envelope design, hotspot authoring, validation, dataset export, job control, the
GN megastructure library and TRELLIS prop intake into one N-panel tab — without moving
any pipeline logic into Blender. Status: **design only; no implementation yet.**
Scheduled as **M2.5**, after the M3 vertical slice (PLAN.md §9): the slice proves the
pipeline by hand first, then this add-on packages it.

---

## 1. Core principles (non-negotiable)

1. **Every operator is a thin wrapper.** All logic lives in `pipeline/` modules that run
   headless (via `blender-win.sh -b --python …` for bpy code, or plain WSL Python for the
   rest). An operator body is UI glue only: gather parameters from the scene/panel, call
   the same function the CLI calls, report. If a behavior exists only inside an operator,
   that's a bug. Corollary for M2: **every pipeline script exposes an importable function
   with a thin `argparse` main** — the add-on imports the function; CI and headless runs
   use the CLI.
2. **Blender never imports the ML stack.** No torch, no gsplat, no TRELLIS, no ComfyUI
   client libraries inside Blender's Python. Anything that needs a conda env runs as a
   WSL process launched by the job runner (§6).
3. **Long jobs are asynchronous, reported via status files.** The add-on launches a WSL
   job, gets a job id back immediately, and a `bpy.app.timers` poll reads
   `jobs/<id>/status.json`. No modal operators that lock the UI, no pipes to keep alive —
   Blender can crash or close and the job keeps running.
4. **Stage gates by default.** Multi-stage chains (render → sync → train → pack) pause at
   stage boundaries with inspectable outputs; the artist reviews, then continues from the
   panel. Matches the working style used throughout setup: no silent multi-hour pipelines.
5. **One envelope definition.** The camera envelope is authored once in Blender and the
   same JSON drives the trainer rig and the web viewer camera limits (PLAN.md §10 risk:
   "splat artifacts outside the trained envelope" — solved structurally here).
6. **License rules apply inside the add-on too.** TRELLIS intake never requests
   `'gaussian'` format; every generated asset the add-on touches gets a provenance JSON
   (CLAUDE.md hard rules).

## 2. Environment & packaging

- **Target:** Windows Blender 5.1.2 (the Cycles/OptiX side of the pipeline). The repo is
  reached from Windows via `\\wsl.localhost\<distro>\home\karin\dev\space-catalogue`.
- **Packaging:** Blender extension format (`blender_manifest.toml`), source at
  `pipeline/blender/addon/catalogue_tools/`, installed as a local (unlisted) extension —
  during development via "Install from Disk" pointing at the WSL path, or a Windows
  junction into the extensions dir. Pure-Python, no wheels (principle 2 makes this easy).
- **Add-on preferences:**
  - `repo_path_windows` (e.g. `\\wsl.localhost\Ubuntu-24.04\home\karin\dev\space-catalogue`)
  - `repo_path_wsl` (`/home/karin/dev/space-catalogue`)
  - `wsl_distro` (for `wsl.exe -d`)
  - `staging_dir_windows` (`D:\renders` — **never C:**, per CLAUDE.md)
  - poll interval (default 2 s)
- **Path mapping:** one utility module `catalogue_tools/paths.py` owns Windows↔WSL
  conversion (mirror of what `blender-win.sh` does with `wslpath`). Nothing else
  concatenates paths across the boundary.
- **Importing pipeline code:** the add-on prepends `repo_path_windows` to `sys.path` and
  imports `pipeline.blender.*` modules directly (they are bpy-safe by construction).
  Non-bpy pipeline modules (`pipeline/splats`, `pipeline/pack`) are *never* imported in
  Blender — they run WSL-side via the job runner.
- **UI shell:** one N-panel tab **"Catalogue"** in the 3D viewport with sub-panels in the
  module order below, plus a persistent job-status footer.

## 3. Module: Camera-envelope designer

> **SUPERSEDED (2026-07-13) by the capture system — see CAPTURE.md.** Kari's
> capture spec replaced the single parameterized `ENV_<concept-id>` empty below
> with multi-vantage `CAPTURE_<name>` collections (envelope volume **mesh** +
> FOCUS empty + nested per-object child rigs), implemented in
> `pipeline/blender/capture/`. This module is now "capture panel, module 1"
> wrapping those functions (CAPTURE.md §8); the envelope-JSON path below is
> replaced by `capture-meta.json` / `capture-<vantage>.envelope.json` under
> `pipeline/provenance/`, merged into the concept page by
> `pipeline/pack/envelope_to_concept.py`. The trainer-margin concept and the
> single-source rule stand, and are implemented. §2's source path
> `pipeline/blender/addon/` vs the capture spec's `addons/` is pending Kari's
> call. §6's runner: `pipeline/splats/run_capture.py` already implements the §6
> job-directory contract for capture jobs and is the seed of the generic
> `run_job.py`.

The envelope is the contract between training and playback. It is authored visually,
stored in the .blend, and exported to a single JSON consumed by both sides.

**Authoring model.** One envelope object per scene: an empty named `ENV_<concept-id>`
carrying custom properties, managed through the panel (artists never edit raw props):

- `target` (Vector, world meters) — orbit/look-at point
- `radius_min`, `radius_max` (m)
- `elevation_min_deg`, `elevation_max_deg`
- `azimuth_min_deg`, `azimuth_max_deg` (full circle default)
- `focal_mm`, `sensor_mm` (defaults 40/36, per rehearsal)
- `views` (default 150), `resolution` (default 1600)

**Visualization.** A non-rendering Geometry Nodes preview mesh (spherical band clipped to
the ranges) parented to the envelope empty, regenerated on property change; plus a
"Preview camera" operator that binds a scrub slider (azimuth/elevation/radius) to the
active camera so the artist can *fly the limits* and check what the user will and won't
see. A "Frame worst case" button jumps to min-radius/min-elevation, where splat quality
is most at risk.

**Export.** `Export envelope` writes `assets_src/scenes/<concept>/envelope.json`:

```json
{
  "version": 1,
  "space": "blender-world", "up": "+Z", "units": "m",
  "target": [0.0, 0.0, 0.6],
  "radius": { "min": 6.0, "max": 10.0 },
  "elevation_deg": { "min": 15.0, "max": 70.0 },
  "azimuth_deg": { "min": -180.0, "max": 180.0 },
  "camera": { "focal_mm": 40.0, "sensor_mm": 36.0 },
  "dataset": { "views": 150, "resolution": 1600 }
}
```

**Consumers (both read this file; neither re-derives it):**

| Consumer | Use |
|---|---|
| `pipeline/blender/export_dataset.py` | Samples the golden-angle rig strictly inside the band (generalizes `make_scene.py`'s hardcoded 15–70° hemisphere) |
| Web viewer (M1) | Pack step embeds derived `ArcRotateCamera` limits into the concept JSON (`assets.hero_camera`): `lowerRadiusLimit/upperRadiusLimit`, `lowerBetaLimit/upperBetaLimit` (beta = 90° − elevation), alpha limits, target — converted from Z-up Blender world to the viewer's Y-up space in **one** documented function in `pipeline/pack/` |

The coordinate conversion (Z-up → Y-up, matching how the trained splat lands in Babylon)
lives in exactly one place and is covered by a round-trip test; the rehearsal already
proved the analogous OpenGL→OpenCV conversion with PSNR 38.5.

Trainer *margin* (rendering slightly beyond the playback envelope so quality doesn't
degrade exactly at the clamp) is a parameter of the dataset exporter (default e.g. +5°
elevation / ±5% radius), never of the viewer limits.

**v2, out of scope now:** spline-path envelopes for interior fly-throughs (O'Neill
valley), multiple envelopes per scene. Schema `version` field exists for this.

## 4. Module: Hotspot authoring

Hotspots (PLAN.md §7 `hotspots[]`) are authored as empties, exported into the concept
JSON.

- A collection `Hotspots` per scene; each hotspot is an empty named `HS_<slug>` with
  custom props `hs_title` (string) and `hs_body` (string, or `hs_body_file` pointing at
  a markdown snippet under `content/concepts/<id>/` for longer text).
- Panel operators: *Add hotspot at cursor*, *Add hotspot on face* (snaps to surface under
  mouse), list widget with select/rename/delete.
- **Sync to JSON** calls `pipeline.blender.hotspots.export_hotspots(scene, concept_json)`:
  - positions converted with the *same* Z-up→Y-up convention as the GLB export, so a
    hotspot authored on the inspect mesh lands on the mesh in Babylon;
  - merge by `HS_` slug: Blender owns `position` and `title`; `body` is taken from the
    prop/file but existing hand-edited JSON `body` text wins if the Blender prop is empty;
    unknown/extra JSON fields are preserved verbatim;
  - deleted empties → sync reports orphaned JSON hotspots and asks before removing.
- Validator (§5) checks hotspot positions sit within the inspect model's bounds.

## 5. Module: Scene validator

One operator, `Validate scene`, calling `pipeline.blender.validate.run_checks(scene)
-> list[Finding]`; findings render in the panel as error/warning rows with a *Select
offenders* button each. The same function runs headless in CI-ish batch mode over
`assets_src/**/*.blend` (via `blender-win.sh -b`). Checks (initial set — each has an id
so suppressions can be recorded per scene):

| ID | Check | Severity |
|---|---|---|
| V001 | Scene units = metric, scale 1.0; real-world meters plausible for the concept | error |
| V002 | Unapplied object scale on render geometry | error |
| V003 | Envelope empty exists, exported JSON up to date (hash of props vs file) | error |
| V010 | Camera envelope: no geometry closer than *r*·k to min-radius shell (splat quality) | warn |
| V020 | Poly count vs PLAN §6 inspect budget (pre-`gltfpack` heuristic) | warn |
| V021 | Texture sizes / count vs KTX2 budget heuristic | warn |
| V030 | Every AI-generated/linked asset in the scene has a provenance JSON | error |
| V031 | No objects sourced from non-cleared libraries (checks provenance `license` field against PLAN §5 blocklist) | error |
| V040 | Hotspots inside inspect-model bounds; unique slugs; non-empty titles | warn |
| V050 | GN generator instances carry `dimension_source` (see §7) | warn |
| V060 | Naming: renderable collections/objects follow `<concept-id>` conventions | warn |

*Done-when for this module:* a scene that passes validation exports a dataset that trains
without manual fixes.

## 6. Module: Job panel & job runner (shared infrastructure)

The panel is a front-end to a new WSL-side runner, **`pipeline/jobs/run_job.py`** (an M2.5
deliverable, but designed here because every module uses it).

**Launch.** From Windows Blender:
`subprocess.Popen(["wsl.exe", "-d", <distro>, "--", "bash", "-lc", "<repo>/pipeline/jobs/run_job.py start <kind> --params <file> --detach"])`.
The runner allocates `jobs/<yyyymmdd-hhmmss>-<kind>/`, double-forks (survives Blender),
sources what the stage needs (nvm for node stages, the right conda env for training),
and returns the job id on stdout.

**Job directory contract:**

```
jobs/<id>/
├── status.json      # atomic (write tmp + rename); the ONLY thing Blender polls
├── params.json      # exact inputs, for reproducibility
├── control          # Blender writes "cancel" or "continue" here; runner polls
├── log.txt          # combined stdout/stderr
└── artifacts/       # or pointers into assets_src/ / staging
```

`status.json` schema:

```json
{
  "job_id": "20260712-1130-train-splat",
  "kind": "train-splat",
  "state": "running",            // queued|running|gate|done|failed|cancelled
  "stage": "train", "stages": ["train", "pack-sog"],
  "progress": 0.62,               // best-effort, -1 if unknown
  "message": "iter 6200/10000, loss 0.031",
  "metrics": {},                  // e.g. {"psnr": 38.5} when done
  "gate": null,                   // when state=gate: {"prompt": "...", "inspect": ["path", "url"]}
  "pid": 12345,
  "started_at": "2026-07-12T11:30:00+03:00", "updated_at": "..."
}
```

**Job kinds (initial):**

| Kind | Wraps | Env / side |
|---|---|---|
| `render-dataset` | `blender-win.sh -b <scene.blend> --python export_dataset.py` → `D:\renders\<scene>` | headless *Windows* Blender, launched via the runner for uniform status handling |
| `sync-dataset` | `pipeline/blender/sync-dataset.sh <scene>` (D: → ext4; training I/O never on /mnt/*) | WSL |
| `train-splat` | gsplat `simple_trainer.py mcmc` with CLAUDE.md's canonical flags; parses stdout for iter/PSNR progress | conda `splat` |
| `pack-sog` | SuperSplat-cleaned PLY (or trainer PLY) → `splat-transform` tiers per PLAN §6; `-H 0` / `-i 50` per rehearsal learnings | WSL node (nvm) |
| `pack-glb` | `pipeline/pack/pack-glb` (gltfpack + toktx + budget check) | WSL node |
| `trellis-intake` | §8 | conda `trellis1` |
| `chain` | render → sync → train → pack-sog with a **gate** after each stage | mixed |

**Gates.** At a boundary the runner writes `state: "gate"` with an inspect hint (e.g. the
dataset directory after render, the trainer PSNR + PLY after train, rehearsal-viewer URL
after pack) and blocks until `control` says `continue` (or `cancel`). The panel shows a
prominent *Continue* button with the inspect links. A per-launch "run unattended"
checkbox skips gates for a chain the artist already trusts.

**Panel UI.** Job list (active + last N finished) with state, progress bar, message;
buttons: *Open log*, *Open artifact folder*, *Continue gate*, *Cancel*, and for
pack/train jobs *Preview* — which (re)starts the rehearsal viewer server
(`python3 -m http.server 8321` in `pipeline/rehearsal/web`, itself a tiny job kind) and
opens `http://localhost:8321/viewer.html?f=<file>` in the browser. Cancellation is
cooperative: `control`=cancel, escalating to SIGTERM on the recorded pid after a timeout.

## 7. Module: GN megastructure asset library

Front-end to PLAN §4.2's procedural kit; mostly conventions plus a little UI.

- **Location:** `assets_src/library/megastructures/*.blend`, one file per family
  (`truss.blend`, `hull-panels.blend`, `radiators.blend`, `solar-wings.blend`,
  `ring-segments.blend`, `regolith.blend`), assets marked for the Asset Browser with a
  shared catalog file (`blender_assets.cats.txt`).
- The add-on registers the library path in Blender preferences if missing (first-run
  setup), and offers *New from generator* — appends/links a generator node group and
  applies a **preset**: presets are JSON files under
  `pipeline/blender/presets/<family>/<name>.json` mapping GN inputs to values, each with
  a `dimension_source` field citing the published spec (NASA SP-413, O'Neill Island
  Three, Artemis docs — per PLAN §4.2). Applying a preset stamps `dimension_source` on
  the object (validated by V050).
- Panel shows the generator's exposed inputs (Blender does this natively via the modifier
  panel; the add-on adds *Save as preset* / *Load preset*).
- Library .blend files are content, not code: they live in `assets_src/` (git-lfs or
  outside git per PLAN §8), but the presets JSON is versioned normally.

## 8. Module: TRELLIS prop intake

Wraps the image → 3D → cleanup loop (PLAN §4.3) with the license guards baked in.

**Flow:**

1. *Intake* operator: pick an input image (file browser defaults to the ComfyUI output
   dir) or paste a path; optional prop name/slug. The operator copies the image to
   `assets_src/props/<slug>/input/` and launches a `trellis-intake` job.
2. WSL side (`pipeline/trellis/intake.py`, importable function + CLI, conda `trellis1`,
   `cwd`/`PYTHONPATH` = `~/apps/TRELLIS`): rembg background removal → TRELLIS 1 with
   **`formats=['mesh', 'radiance_field']` — the string `'gaussian'` must not appear in
   this codebase outside comments** → GLB texture bake via diffoctreerast → writes GLB +
   **provenance JSON** (tool=TRELLIS 1, model version, input image hash, seed, date,
   license snapshot) next to it.
3. On `done`, the panel's *Import result* button appends the GLB into a `Props_Intake`
   collection at world origin, real scale unknown → object gets a `needs_scale` flag
   (validator refuses to let `Props_Intake` content into render collections).
4. **Cleanup loop** buttons, each a thin wrapper over `pipeline/blender/prop_cleanup.py`
   functions (M2 script, per PLAN §4.3): *Remesh/retopo*, *UV unwrap*, *Rebake textures
   from source*, *Generate LODs*. Runs in-Blender (it's bpy work, fast enough), same
   functions usable headless for batch cleanup.
5. *Promote prop* moves it to the props library collection, requires: scale set,
   provenance present, cleanup steps recorded in the provenance JSON.

When TRELLIS.2 activates (DINOv3 grant — setup-log.md Phase 5), only the WSL-side intake
script gains a `--backend trellis2` switch; the add-on UI is unchanged. The add-on never
knows which conda env ran.

## 9. Repo layout additions

```
pipeline/
├── blender/
│   ├── addon/catalogue_tools/    # the add-on (UI glue only)
│   │   ├── blender_manifest.toml
│   │   ├── __init__.py           # registration
│   │   ├── paths.py              # Windows↔WSL path mapping (single owner)
│   │   ├── jobs_client.py        # launch/poll/control jobs
│   │   └── panels/…, operators/…
│   ├── export_dataset.py         # M2: envelope→rig→render→COLMAP (from make_scene.py)
│   ├── hotspots.py               # M2.5: hotspot export/merge
│   ├── validate.py               # M2.5: scene checks
│   ├── prop_cleanup.py           # M2: remesh/UV/bake/LOD functions
│   └── presets/<family>/*.json
├── jobs/run_job.py               # WSL job runner + status-file protocol (§6)
├── trellis/intake.py             # image→GLB+provenance (trellis1 env)
└── …
jobs/                             # runtime job state (gitignored)
assets_src/library/megastructures/*.blend
assets_src/scenes/<concept>/envelope.json
```

## 10. Testing & acceptance

- **Parity rule test:** every operator's core call target is a `pipeline.*` function that
  also has CLI coverage; a grep-level CI check flags operators importing torch/ML
  packages or exceeding a glue-size heuristic (code review enforces the spirit).
- **Headless tests:** `blender-win.sh -b --python pipeline/blender/tests/test_addon.py`
  registers the add-on, builds a toy scene, runs: envelope export → schema-validate;
  hotspot sync round-trip (including the Y-up conversion against a reference GLB);
  validator on a deliberately broken scene (expects specific finding IDs).
- **Envelope round-trip test (the critical one):** export envelope → generate rig →
  verify all rig poses lie inside envelope+margin → convert to viewer limits → verify
  clamped viewer poses lie inside the *un*-margined rig coverage.
- **Job runner tests:** pure-WSL pytest for status-file atomicity, gate/continue/cancel
  protocol, double-fork survival (kill the launcher, job continues).

**Milestone M2.5 done when:** the M3 lunar-base scene can be revised, re-exported,
retrained, packed and previewed end-to-end from the Blender UI without touching a
terminal; its envelope and hotspots round-trip into the live concept page; and the
validator passes on it with zero suppressions.

## 11. Non-goals

- No ML inference, training, or heavy processing in Blender's Python (principle 2).
- No replication of the web viewer inside Blender — preview is the real rehearsal/M1
  viewer in a browser.
- No general render farm / queue system: one workstation, sequential jobs, simple files.
- No automatic license decisions: the add-on surfaces provenance and blocks known-bad
  sources (V031), but new license calls are Kari's, logged in provenance.

## 12. Open questions (decide before implementation)

1. Envelope margin defaults (+5° / ±5%?) — pick after measuring quality falloff at the
   clamp on the M3 scene.
2. `\\wsl.localhost` I/O performance for the Asset Browser library files — if sluggish,
   mirror library .blends to a Windows-side cache.
3. Whether `render-dataset` should stream per-frame progress (frame counter in
   `status.json`) via a render post-frame handler — nice, cheap, probably yes.
4. Blender MCP addon coexistence: the job panel and MCP (port 9876) both drive Blender;
   define which owns scene mutation during a job (proposal: jobs never mutate the open
   scene; they run on saved .blend copies).
