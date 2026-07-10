# Space Engineering Catalogue — Production & Development Plan

A plan for building a modern, visual-first web catalogue of space and future engineering concepts (lunar bases, O'Neill cylinders, Dyson swarms, space elevators…) using Babylon.js, Gaussian splats (SOG) and optimized meshes — with a local, open-source, commercially-safe content pipeline running on an RTX 4090 workstation, and Claude Code doing the heavy lifting on implementation.

Status of key facts in this plan: verified against current documentation and releases as of July 2026. Re-verify licenses before launch — several tools in this space change terms between versions.

---

## 1. What we're building

A catalogue website where each concept is presented through three layers working together:

1. **A photoreal hero scene** — a 3D Gaussian splat (SOG) of the concept in its environment, with fully baked path-traced lighting. The user flies a constrained camera through it. This is where the "wow" and the realism live.
2. **An interactive inspect model** — a compressed PBR mesh (GLB) the user can orbit freely, with hotspot annotations, exploded/cutaway views, and scale comparisons.
3. **A fact layer** — real dimensions, physics, engineering status (theoretical / studied / in development), history, and cited sources, rendered as fast static content.

The catalogue front page is a grid/scroll of concepts with poster renders; tapping a card opens the concept page which lazy-loads its 3D content. Everything must run at 60 fps on a typical laptop and 30+ fps on a modern phone, on an ordinary connection.

## 2. Core architectural decision: three asset classes

This is the most important call in the whole project, and it's what makes "photoreal on a phone" possible.

**Class A — Splat hero scenes (.sog).** You assemble and light each environment in Blender, render a few hundred views with Cycles, and train a Gaussian splat from those renders. The splat "bakes in" full path-traced global illumination, soft shadows, and material response — things no mobile GPU can compute in real time — and then renders as a cheap rasterization workload. SOG compression brings scenes down roughly 95% versus raw PLY, so a rich scene ships in the 10–30 MB range instead of hundreds of MB. The trade-off: splats are frozen light. No relighting, limited dynamic objects, and quality degrades outside the trained camera envelope — so the web camera must be constrained to the same envelope you trained.

**Class B — Interactive PBR meshes (.glb).** For the inspect mode you need real geometry: free orbit, exploded views, animated mechanisms, hotspots. These are conventional real-time assets — meshopt-compressed glTF with KTX2 textures and IBL lighting — built to a strict polygon/texture budget.

**Class C — Flat media.** Cycles renders for posters and stills, diagrams, scale-comparison graphics, and AI-generated backdrop/matte elements. Cheapest to serve, highest information density.

A concept page typically opens on Class C (instant), streams Class A when the user enters the scene, and loads Class B when they switch to inspect mode.

## 3. Web stack

**Engine: Babylon.js (Apache-2.0), version 8.30+ / v9 line.** Babylon now natively loads SOG/SOGS alongside PLY, .splat and Niantic SPZ, and — critically for your larger scenes — supports *streamed* SOG bundles: a spatial octree of chunks at multiple LODs described by a `lod-meta.json`, where only the chunks/LODs needed for the current viewpoint are downloaded and decoded. Recent releases also added splat shadow casting, a compound mode that merges multiple splat assets into one globally-sorted draw call, orthographic camera support, and Triangle Splatting import. Run the WebGPU engine where available with automatic WebGL2 fallback (Babylon handles both from the same code).

**App framework: Vite + TypeScript.** Keep the site content-driven: one JSON/MD file per concept drives the catalogue, pages, and asset manifests. If SEO for the text layer matters, wrap it in Astro (MIT) with the Babylon viewer as an island; otherwise a plain Vite multi-page app is simpler for Claude Code to maintain. Don't load the engine on the landing page — initialize it on first 3D interaction.

**Asset tooling on the web side:**

| Tool | Role | License |
|---|---|---|
| `gltfpack` / meshoptimizer | Mesh + scene compression for GLB | MIT |
| KTX-Software (`toktx`) | GPU texture compression (UASTC/ETC1S in KTX2) | Apache-2.0 |
| `splat-transform` (PlayCanvas CLI) | Splat format conversion, editing, streamed-SOG generation | MIT |
| SuperSplat (PlayCanvas) | Browser-based splat cleanup/editing, exports PLY/SPLAT/SOG | MIT |
| Babylon `.env` IBL tools | Prefiltered environment maps for PBR lighting | Apache-2.0 |

**Hosting:** any static host/CDN (Cloudflare Pages, Netlify, GitHub Pages + CDN). Brotli compression, immutable cache headers on hashed asset filenames, HTTP/2+. Splat chunks and KTX2 are already compressed — serve as-is.

## 4. Content production pipeline (all local, RTX 4090)

Your machine is well matched to this: 24 GB VRAM covers splat training and current image/3D generators (sometimes quantized), the 5950X handles batch processing, and 128 GB RAM is generous for CPU-offloaded model weights and large datasets.

One honest note up front: in 2026, AI 3D generation is excellent for *props and secondary assets* and still weak at *engineering-accurate megastructures* — topology is messy and dimensions are invented. The winning division of labor for a realism-focused catalogue is: AI generates images, textures, props and clutter; **Blender Geometry Nodes generates the megastructures procedurally** (trusses, panel grids, ring segments, greebles — exactly the repetitive geometry procedural systems are best at); and the splat pipeline converts your path-traced scenes into web-deliverable photorealism. As a professional Blender user you sit in the highest-leverage seat: art direction and assembly, while scripts and AI do volume work.

### 4.1 References & concept art (AI images, license-clean)

Run image models locally through ComfyUI (the app is GPL-3.0, which doesn't affect your outputs). Stick to models whose weights are commercially clear:

| Model | License | Why use it |
|---|---|---|
| Qwen-Image / Qwen-Image-2.0 / 2512 | Apache-2.0 | Photoreal, native 2K in 2.0 (7B fits your GPU), strong prompt adherence; also an Edit variant |
| FLUX.1 [schnell], FLUX.2 [klein] 4B | Apache-2.0 | Fast, high quality; klein 4B runs in ~13 GB VRAM |
| Z-Image Turbo | Apache-2.0 | Very fast photoreal batches |
| Stable Diffusion 3.5 | Stability Community License | Free commercial use under $1M revenue; deepest ControlNet/LoRA ecosystem |

**Avoid:** FLUX.1 [dev] and FLUX.2 [dev] (non-commercial weight licenses). Use these images for: moodboards and art direction, input images for image-to-3D generation, matte/backdrop elements, and page graphics. For engineering-consistent views, drive SD3.5 or Qwen with ControlNet depth/edge maps rendered from your blockout geometry — that keeps AI imagery locked to correct proportions.

### 4.2 Primary structures: procedural Blender modeling

Model hero structures to *real published dimensions* so the realism is structural, not just visual. Primary sources to build from: the 1975 NASA Ames/Stanford summer study (NASA SP-413) for the Stanford torus, O'Neill's Island Three specifications for the cylinder pair (~8 km diameter, ~32 km long), current NASA Artemis surface-architecture documents for the lunar base, Dyson's 1960 paper for the swarm. Build a small library of Geometry Nodes generators — truss beam, pressure-hull panel array, radiator field, solar wing, ring segment, regolith-berm — and every concept becomes assembly rather than modeling. Claude Code can write and iterate these node setups via Blender's Python API.

### 4.3 Secondary assets: local AI 3D generation

**Primary tool: Microsoft TRELLIS.2 (TRELLIS.2-4B), MIT license.** Released December 2025; generates a textured PBR 3D asset (GLB export with color/roughness/metallic) from a single image or text, at selectable voxel resolutions — roughly seconds for 512³ previews up to ~a minute for 1536³ production quality. Run it via the official repo or the ComfyUI-TRELLIS2 node; community-quantized workflows fit 24 GB VRAM comfortably at 1024³. Use it for: rovers, landers, hab modules, antennas, cargo, tanks, interior clutter, spacesuited figures as background props.

Fallbacks, all commercially clear: TRELLIS 1 (MIT), TripoSR (MIT — fast low-fi drafts), Stable Fast 3D (Stability Community License).

**Do not use Hunyuan3D (any 2.x open release) or HunyuanWorld-Voyager: their community licenses explicitly exclude the European Union**, and you're operating from Finland. This is the single biggest licensing trap in the current 3D-gen landscape.

Every AI mesh goes through a Blender cleanup loop before it ships: import GLB → remesh/retopologize (Blender's tools or Instant Meshes, BSD) → UV unwrap → re-bake the AI textures onto clean maps → generate LODs by decimation. Budget ~20–45 minutes per prop once the loop is scripted; Claude Code should automate the repetitive steps as a bpy batch script.

### 4.4 Materials, environments, sky

CC0 PBR material and HDRI libraries: Poly Haven and ambientCG (both CC0 — no attribution needed, commercial fine). Custom procedural materials: Material Maker (MIT) or Blender's own shader/texture tools. Star fields and space backdrops: NASA SVS Deep Star Maps (NASA media is generally free to use under their media-usage guidelines) and ESO imagery (CC BY 4.0 — attribute it). Convert HDRIs to Babylon `.env` prefiltered files for cheap, correct IBL on Class B meshes.

### 4.5 Hero scenes → Gaussian splats (the core trick)

This is the pipeline that turns your Cycles quality into phone-playable content:

1. **Assemble & light in Blender.** Physically plausible setups: correct sun intensity (~1361 W/m² at 1 AU), a single harsh key with black sky and bounce-off-regolith for lunar surface scenes, correct atmospheric scattering for Earth-orbit shots. Cycles path tracing gives you physically correct GI that the splat will preserve.
2. **Generate the camera rig + dataset.** Two good Blender add-ons: **Splats** (Blender extensions platform, Dec 2025 — Fibonacci-sphere camera distribution, frustum culling, OpenCV-format camera parameters, per-frame PLY point-cloud export, built specifically for 3DGS training) or **BlenderNeRF** (exports NeRF-format `transforms.json` plus a `points3d.ply` initialization cloud from scene vertices). Known poses mean **no COLMAP step and zero pose error**. Design the camera coverage to exactly match the web camera envelope — train only the views users can reach.
3. **Render.** 150–400 views at ~1600 px, Cycles + OptiX denoise. On a 4090 this is typically an over-lunch batch per scene, not an overnight one.
4. **Train.** Use **gsplat** (nerfstudio project, Apache-2.0) — its `simple_trainer` with the MCMC strategy is the current workhorse, up to 4× more memory-efficient than the original implementation. GUI alternatives if you prefer: Brush (open source, cross-platform, WebGPU-based, consumes COLMAP/nerfstudio-format datasets) or LichtFeld Studio (open-source trainer/editor, CUDA 12.8+). **Never use the original Inria/MPII reference implementation — its license is non-commercial.** gsplat exists partly to solve exactly this problem.
5. **Clean & edit.** SuperSplat (MIT, in-browser): delete floaters, crop to the envelope, set orientation and pivot, preview compression.
6. **Export SOG.** For normal scenes, a single `.sog` file. For very large scenes, generate a *streamed* SOG bundle with `splat-transform` (chunked octree + `lod-meta.json`) and let Babylon stream LODs at runtime.
7. **Tier it.** Export two densities per scene — e.g. desktop ~1.5–3M splats, mobile ≤ ~0.7M — and pick at load time by device class.

### 4.6 Mesh packing (Class B)

Blender → GLB export (real-world scale, meters) → `gltfpack -cc` (meshopt compression, quantization) → textures to KTX2 with `toktx` (UASTC for normal maps, ETC1S for albedo/AO/roughness). Babylon loads meshopt+KTX2 natively. Target budgets are in §6.

## 5. License matrix (the "can I ship this commercially from the EU" table)

| Tool / asset source | Purpose | License | Commercial use, EU |
|---|---|---|---|
| Babylon.js, gsplat, nerfstudio, KTX-Software, Draco, TypeScript | Engine & tooling | Apache-2.0 | ✅ |
| Vite, meshoptimizer/gltfpack, SuperSplat, splat-transform, Material Maker, Astro | Tooling | MIT | ✅ |
| Blender | DCC | GPL (tool only — your outputs are yours) | ✅ |
| ComfyUI | Local AI runner | GPL-3.0 (tool only) | ✅ |
| TRELLIS 1 (**active**: DINOv2 encoder + rembg, Inria rasterizer excluded) | AI 3D gen | MIT | ✅ (see notes below) |
| TRELLIS.2 (installed, **dormant** — encoder gated) / TripoSR | AI 3D gen | MIT (encoder: DINOv3 License) | ⏸ pending DINOv3 access |
| **briaai RMBG-2.0** (TRELLIS.2's upstream default bg remover) | Background removal | **CC BY-NC 4.0** | ❌ never — patched to rembg (MIT) |
| **mip-splatting `diff-gaussian-rasterization`** (TRELLIS 1 optional dep, `--mipgaussian`) | 3DGS rendering | **Inria non-commercial** | ❌ never — excluded from install |
| Qwen-Image (all versions), FLUX.1 schnell, FLUX.2 klein, Z-Image Turbo | AI images | Apache-2.0 | ✅ |
| Stable Diffusion 3.5, Stable Fast 3D | AI images / 3D | Stability Community License | ✅ under $1M annual revenue |
| Instant Meshes | Retopo | BSD | ✅ |
| Poly Haven, ambientCG | HDRIs, PBR materials | CC0 | ✅ |
| NASA imagery/media | Reference, star maps | Generally public domain / free per NASA media guidelines | ✅ (follow guidelines, no NASA endorsement implied) |
| ESO / ESA imagery | Space imagery | CC BY 4.0 / CC BY-SA 3.0 IGO | ✅ with attribution (mind SA terms) |
| **Inria/MPII 3D Gaussian Splatting reference code** | Splat training | **Non-commercial** | ❌ never |
| **Hunyuan3D 2.x, HunyuanWorld-Voyager** | AI 3D gen | Community license **excluding EU/UK/KR** | ❌ not in Finland |
| **FLUX.1 [dev], FLUX.2 [dev]** | AI images | Non-commercial weights | ❌ (use schnell/klein) |

**3D-gen stack notes (2026-07-10 setup):** TRELLIS 1 is the working image→3D generator. Its install *excludes* `--mipgaussian` (Inria-derived non-commercial rasterizer); consequently pipelines must request `formats=['mesh', 'radiance_field']` — never `'gaussian'` — and GLB texture baking runs via diffoctreerast (MIT). Background removal in both TRELLIS versions is rembg/u2net (MIT); TRELLIS.2's code carries a license guard that overrides its upstream RMBG-2.0 (CC BY-NC) default. TRELLIS.2 is pending DINOv3 access; on grant, review Meta's DINOv3 license terms and record them in the provenance log before commercial use.

Two hygiene rules: keep a **provenance log** per asset (tool, model + version, prompt/seed, date, license at time of generation) — it's cheap insurance and Claude Code can maintain it as JSON; and remember that purely AI-generated outputs may have limited copyright protection in many jurisdictions — your curation, modification and assembly are what create protectable work, which your Blender-centric pipeline naturally provides. (Not legal advice; worth a one-hour review with a lawyer before commercial launch.)

## 6. Performance plan

Set budgets first and make Claude Code enforce them in CI (a script that fails the build if an asset exceeds its budget is worth more than any amount of optimization advice).

| Item | Budget (mobile) | Budget (desktop) |
|---|---|---|
| Initial route (HTML+CSS+JS, no engine) | < 200 KB gz | < 200 KB gz |
| Babylon engine chunk (lazy, on first 3D interaction) | ~1 MB gz, cached | same |
| Hero splat (SOG) per concept | 6–15 MB (≤ ~0.7M splats) | 15–40 MB or streamed (1.5–3M splats) |
| Inspect model (GLB, meshopt + KTX2) | ≤ 4 MB | ≤ 10 MB |
| Frame rate | ≥ 30 fps | ≥ 60 fps |
| Time to interactive 3D on 4G | < 8 s | — |

Techniques, in priority order: lazy-init the engine and load exactly one concept's assets at a time (dispose scene on navigation); device tiering at load (pick splat density tier, cap devicePixelRatio at ~1.5–2 on mobile, use Babylon hardware scaling); use Babylon's SceneOptimizer to degrade gracefully under load; light Class B meshes with a prefiltered `.env` IBL instead of multiple dynamic lights; skip post-processing on mobile; use splat compound mode when a scene mixes several splat assets; use streamed SOG for anything over ~25 MB; `preload`/`prefetch` the next likely concept's poster and manifest. Test matrix from day one: a mid-range Android (Pixel 7a-class), a recent iPhone (Safari has its own WebGL/WebGPU quirks and memory limits — the usual source of surprises), an integrated-GPU laptop, and your desktop.

## 7. Content model

One JSON file per concept drives everything — catalogue card, page, asset loading, and the provenance log links back to it:

```json
{
  "id": "oneill-cylinder",
  "title": "O'Neill Cylinder (Island Three)",
  "status": "theoretical-studied",
  "era": "Proposed 1976",
  "stats": { "diameter_m": 8000, "length_m": 32000, "rotation_rpm": 0.53, "population": "several million" },
  "summary": "...",
  "physics_notes": ["artificial gravity via rotation", "day/night via mirror strips", "..."],
  "sources": [{ "label": "O'Neill, The High Frontier (1976)", "url": "..." }],
  "assets": {
    "poster": "posters/oneill.avif",
    "hero_sog": { "mobile": "splats/oneill-m.sog", "desktop": "splats/oneill-d.sog" },
    "inspect_glb": "models/oneill.glb",
    "env": "env/space-neutral.env"
  },
  "hotspots": [{ "position": [0, 120, 40], "title": "Mirror strip", "body": "..." }]
}
```

Starter catalogue (roughly ordered by production difficulty, easiest first):

| Concept | Class A scene idea | Status label |
|---|---|---|
| Lunar surface base | Habitat + ISRU field at low sun angle, harsh shadows | In development (Artemis-era) |
| LEO commercial station | Station over Earth limb, sunrise | In development |
| Mars surface habitat | Dust-hazed settlement, Jezero-like terrain | Studied |
| Stanford torus | Interior rim landscape looking up through spokes | Studied (NASA SP-413) |
| O'Neill cylinder | Interior valley with window strips | Theoretical, well-specified |
| Bernal sphere | Interior equator view | Theoretical |
| Asteroid mining rig | Rig anchored to rubble-pile asteroid | Studied |
| Solar power satellite | Kilometer-scale array, transmitter toward Earth | Studied |
| Space elevator | Anchor station + ribbon vanishing up | Theoretical |
| Orbital ring | Ring segment low over Earth | Theoretical |
| Dyson swarm | Sparse collector field against the Sun (log-scale trickery) | Theoretical |
| Generation ship | Departure vista | Speculative |

Scale honesty: never try to render true megastructure scale in one continuous scene (floating-point precision and content cost both explode). Each scene is a *bounded vista*; convey scale with the fact layer, an interactive scale-comparison widget (concept vs. Earth vs. ISS vs. a city), and camera language — this is also what NASA's own concept art does.

## 8. Repository layout & Claude Code setup

```
space-catalogue/
├── CLAUDE.md                  # conventions, commands, budgets — Claude Code reads this every session
├── PLAN.md                    # this document
├── apps/web/                  # Vite + TS + Babylon site
│   ├── src/viewer/            # engine bootstrap, splat scene, inspect scene, tiering
│   ├── src/catalogue/         # cards, concept pages, content loader
│   └── public/assets/         # FINAL packed assets only (sog/glb/ktx2/env/avif)
├── content/concepts/*.json    # content model (§7)
├── pipeline/
│   ├── blender/               # bpy scripts: dataset export, batch render, GLB export, LODs
│   ├── splats/                # gsplat train wrapper, SuperSplat/splat-transform steps, tier export
│   ├── pack/                  # gltfpack + toktx + env generation, budget checker
│   └── provenance/            # per-asset provenance JSON
└── assets_src/                # .blend files, AI outputs, renders (git-lfs or outside git)
```

Seed `CLAUDE.md` with (adapt as the project firms up):

```markdown
# Project: Space Engineering Catalogue
Stack: Vite + TypeScript + Babylon.js (v9 line, WebGPU w/ WebGL2 fallback). Static site, content-driven from content/concepts/*.json.

## Commands
- dev: `npm run dev` (apps/web)   - build: `npm run build`   - check budgets: `npm run budgets`
- pack a model: `node pipeline/pack/pack-glb.mjs <in.glb>`
- build splat tiers: `bash pipeline/splats/tiers.sh <scene.ply>`

## Hard rules
- Asset budgets in PLAN.md §6 are CI-enforced; never raise a budget to make a task pass.
- Only license-cleared tools/sources (PLAN.md §5). Never Inria 3DGS code, never Hunyuan3D, never FLUX [dev].
- Every generated asset gets a provenance JSON in pipeline/provenance/.
- All 3D in real-world meters. glTF: meshopt + KTX2 only. Splats ship as SOG.
- One concept's assets in memory at a time; dispose scenes on navigation.
- Mobile first: test tiering logic on every viewer change.
```

Scripts worth having Claude Code write early, because they multiply your throughput: a headless bpy batch renderer (scene file in, dataset out, resumable), a gsplat training wrapper with your default hyperparameters, the pack pipeline (GLB→meshopt→KTX2 with a budget check), a splat tier exporter, a content-manifest generator, and the provenance logger.

## 9. Milestones (each one is a good Claude Code work session or two)

**M0 — Scaffold.** Repo, Vite+TS app, CI with lint/typecheck/budget-check, deploy pipeline to a static host. *Done when a hello-world page deploys automatically.*

**M1 — Viewer core.** Babylon bootstrap (WebGPU→WebGL2 fallback), SOG loading with camera envelope constraints, GLB inspect mode with `.env` IBL and hotspots, device tiering, scene disposal. Use any placeholder splat + model. *Done when both modes hit budget frame rates on your phone.*

**M2 — Pipeline scripts.** Everything in §8's script list, tested on one dummy scene end-to-end. Write every script as an importable function with a thin CLI main — the M2.5 add-on calls the functions, headless runs use the CLIs (see ADDON.md). *Done when `scene.blend → web-ready .sog + .glb` is one command each.*

**M3 — Vertical slice: Lunar Base.** Full production of one concept: procedural base kit in Blender, 2–3 TRELLIS.2 props through the cleanup loop, lit scene, splat tiers, inspect model, content JSON, finished page. *Done when the lunar base page is something you'd show publicly.* Expect this milestone to surface every pipeline problem — that's its job.

**M2.5 — Catalogue Tools Blender add-on.** Runs *after* the vertical slice (numbered 2.5 because it packages the M2 scripts into an artist cockpit — M3 must prove the pipeline by hand first). Full spec: **ADDON.md**. A Blender 5.1 add-on where every operator is a thin wrapper over `pipeline/` scripts that also run headless; Blender never imports the ML stack; long jobs launch in WSL and report via status files. Modules: camera-envelope designer (one JSON drives trainer rig and web camera limits), hotspot authoring via empties → concept JSON, scene validator, dataset export, job panel (render/train/pack/preview with stage gates), GN megastructure asset library, TRELLIS prop intake. *Done when the M3 lunar-base scene can be revised, re-exported, retrained, packed and previewed end-to-end from the Blender UI, and its envelope + hotspots round-trip into the live concept page.*

**M4 — Catalogue shell.** Landing grid, routing, concept-page template generalized from the slice, prefetching, SEO/meta, basic analytics. *Done when adding a concept means adding one JSON + assets, no code.*

**M5 — Content sprint.** Batch-produce remaining concepts through the now-proven pipeline. Realistic pace once M2/M3 are solid: roughly 1–2 concepts per focused day.

**M6 — Hardening.** Lighthouse + real-device audits, accessibility (keyboard camera controls, reduced-motion fallback to posters, alt text), error/loading states, a "sources & methods" page (which also documents your AI usage transparently).

Working style with Claude Code that pays off on a project like this: give it `PLAN.md` and `CLAUDE.md` as standing context; use plan mode for anything architectural; keep tasks PR-sized ("implement SOG tier selection", not "build the viewer"); for visual work, iterate by feeding it screenshots of what rendered; and let it own the boring multiplier work (scripts, budget checker, provenance) early — that's where an agent earns its keep.

## 10. Risks & mitigations

**ML tooling on Windows.** gsplat, TRELLIS.2 and friends are Linux-first. Run the training/generation stack in WSL2 (full CUDA support on your 4090) or a dual-boot Ubuntu; keep Blender wherever you're comfortable. Budget an afternoon for environment setup and pin versions.

**TRELLIS.2 VRAM at max resolution.** 1536³ generations are demanding; use 1024³ (fine for props that get retextured anyway) or community-quantized workflows sized for 24 GB.

**Splat artifacts outside the trained envelope.** Solved by discipline: the camera-rig script and the runtime camera limits must be generated from the same envelope definition.

**iOS Safari.** Memory limits and WebGPU/WebGL differences make it the most likely place things break. Test the M1 viewer on an iPhone before building anything on top.

**License drift.** AI-model licenses change between versions (this year's examples: territory exclusions, dev/schnell splits). The provenance log records the license *at generation time*; re-check the matrix in §5 before launch.

**Scope creep in realism.** Path-traced splats make everything look finished early — keep the fact layer's honesty (status labels, sources, "artist's impression based on…") so visual polish never outruns scientific grounding. It's also a genuine differentiator versus the usual sci-fi eye candy.

## 11. First week, concretely

Day 1–2: WSL2/Ubuntu environment (CUDA, gsplat, ComfyUI + TRELLIS.2 + Qwen-Image), verify each with a smoke test. Day 2–3: run one *tiny* end-to-end rehearsal by hand — a Blender primitive scene → Splats/BlenderNeRF dataset → gsplat → SuperSplat → SOG → the Babylon playground SOG example — so you understand every joint in the pipeline before automating it. Day 3–5: start Claude Code on M0 and M1 with this document in the repo. Then M2, and you're in production.

---

## Sources

- Babylon.js Gaussian Splatting docs (SOG, streamed SOG/LOD, formats, shadows, compound): https://doc.babylonjs.com/features/featuresDeepDive/mesh/gaussianSplatting/
- Babylon.js GS update threads & v9 feature coverage: https://forum.babylonjs.com/t/gaussian-splatting-october-update/61157 · https://radiancefields.com/babylon.js-v9.0-3dgs-gets-shadows-sogs-and-triangle-splatting-support-announced
- TRELLIS.2 (MIT, weights + code): https://github.com/microsoft/TRELLIS.2 · https://huggingface.co/microsoft/TRELLIS.2-4B
- Hunyuan3D community license (EU/UK/KR exclusion): https://github.com/Tencent-Hunyuan/Hunyuan3D-2/blob/main/LICENSE
- gsplat (Apache-2.0): https://github.com/nerfstudio-project/gsplat · Splatfacto/nerfstudio: https://docs.nerf.studio/nerfology/methods/splat.html
- Splat tool landscape incl. Brush, LichtFeld, SuperSplat: https://developer.playcanvas.com/user-manual/gaussian-splatting/creating/recommended-tools/
- splat-transform CLI: https://github.com/playcanvas/splat-transform
- Blender dataset add-ons: https://extensions.blender.org/add-ons/splats/ · https://github.com/maximeraafat/BlenderNeRF
- Qwen-Image (Apache-2.0): https://github.com/QwenLM/Qwen-Image
- Open image-model licensing overview (FLUX schnell/klein Apache-2.0, dev non-commercial, SD3.5 community license): https://www.thundercompute.com/blog/best-open-source-image-generation-models
