# Engine-explorer pages — how to edit them

This folder holds the content for the **engine-explorer page type** — a second
kind of concept page, next to the JSON-driven template in `../concepts/`.
It exists for Concept 002 (rocket engines):

- **Page:** `/concept/rocket-engines/` → https://farsidelab.com/concept/rocket-engines/
- **Content:** `rocket-engines.json` (this folder) — every text on the page,
  the engine list, photo credits and sources.
- **Assets:** `apps/web/public/assets/rocket-engines/` (`engines/`, `vehicles/`,
  `hero/`, `env/`), referenced from the JSON by that path, e.g.
  `"assets/rocket-engines/vehicles/photo.webp"`.
- **Code:** `apps/web/src/explorer/` + `apps/web/src/styles/explorer.css`;
  page shell `apps/web/concept/rocket-engines/index.html`.

Do **not** put this file in `../concepts/`: the concept template would try to
render it at `/concept/?id=rocket-engines` and produce a half-empty page.
The two page types do not share a schema.

Edit → commit → push to `main` → live in ~1 min, same as the concept pages.
The page always fetches the latest JSON.

## `rocket-engines.json` — field guide

Keys starting with `_` are ignored (use them for notes).

| block | what it drives |
|---|---|
| `page_title`, `footer_label` | browser-tab title, mono text bottom-right |
| `hero` | same fields as the concept template's hero (`label`, `status`, two-tone title, `era_line`, `button_text`, `poster_image`, `video`, and optionally `video_mobile`, a 720p encode that phones get instead of `video`). `status` is optional here: it is the text of the blue chip beside the label (Concept 002: `"Engineering"`), and leaving it out removes the chip. The "← Catalogue" button in the header bar is fixed; it is not set from this file |
| `explorer.heading`, `explorer.note` | section kicker and the mono line under the explorer |
| `explorer.groups` | the headings in the left rail (`id`, `title`) |
| `explorer.engines` | one entry per engine — see below |
| `sources` | `heading`, `intro`, and `items`: `{ "label": "SRC_01", "text": "…", "url": "…" }` (`url` optional — the text becomes a link) |

The `ladder` block is left over from a removed section and is not rendered.

### One engine entry

```json
{
  "id": "pressure-fed",
  "ref": "E_01",
  "group": "today",
  "title": "Pressure-fed",
  "summary": "…",
  "description": "…",
  "reference_engine": "Aerojet AJ10-190",
  "status": "live",
  "model": "assets/rocket-engines/engines/pressure-fed_d.glb",
  "manifest": "assets/rocket-engines/engines/pressure-fed.json",
  "flown_on": {
    "heading": "Flown on",
    "text": "…",
    "photos": [
      { "src": "…", "alt": "…", "caption": "…", "credit": "…", "license": "…", "source_url": "…", "position": "center 70%" }
    ]
  }
}
```

| field | what it does |
|---|---|
| `id` | also the `?engine=` value in view links |
| `ref` | reference code shown in the rail and the side panel (`E_01` …) |
| `group` | one of `explorer.groups[].id` |
| `summary` | first paragraph in the side panel: how the engine works |
| `description` | second paragraph in the side panel: what that gives and what it costs. It replaces the `description` in the engine's manifest, which the Blender export writes and which is shown only when this field is missing |
| `status` | `"live"` = selectable; anything else = listed but greyed out ("In build") |
| `model` / `manifest` | the `.glb` and its manifest `.json` (see "Adding or updating an engine") |
| `flown_on.heading` | optional; default "Flown on" |

- **The two paragraphs must not repeat each other** (Kari, 2026-10-06). Each
  fact is said once, in whichever paragraph it belongs. Keeping both in this
  file means a fresh export from Blender cannot bring an old text back.
- **`license` says what is true, not what is convenient.** A photo that a
  company supplied to NASA is not public domain because NASA published it
  (the four Electron photos: NASA's record names Rocket Lab as photographer;
  they are used with credit under Rocket Lab's media terms).
- **Every photo needs `credit`, `license` and `source_url`** — they are shown
  in the enlarged view and are the licence record for the image. Record them
  when the file is downloaded, not later.
- `position` (optional) is a CSS `object-position` value that picks which part
  of the photo shows in its thumbnail.
- The first photo is the wide one; the rest fill a three-column row.

### View links

`?engine=<id>&mode=<explore|explode|cutaway|flow>&part=<node name>&variant=<id>&cam=<alpha,beta,radius>`
— "Copy view link" on the page writes all of these.

## Adding or updating an engine

1. In Blender, run `rk.export_engine("<Root object>", r"<folder>")`. It writes
   `<id>.glb` and `<id>.json` (the manifest).
   Then run `python3 pipeline/pack/strip-glb-scene-extras.py <id>.glb`. The
   export copies the scene's custom properties into the file, and add-ons keep
   their settings there: every model once carried 58 KB of an add-on's settings
   and an identifier. The tool removes the scene-level `extras` and nothing
   else (the geometry is copied byte for byte); `--check` only reports.
2. Copy them to `apps/web/public/assets/rocket-engines/engines/`, **renaming
   the model to `<id>_d.glb`**. The `_d` suffix puts it in the desktop size
   tier of the CI budget check (`pipeline/pack/check-budgets.mjs`: 10 MB;
   un-suffixed `.glb` files must fit the 4 MB mobile tier). Never raise a
   budget to make a model pass — compress or simplify the model instead.
3. In `rocket-engines.json`, point `model` / `manifest` at the files and set
   `"status": "live"`.
4. Optional: add a cycle schematic for it to `DIAGRAMS` in
   `apps/web/src/explorer/diagrams.ts`. Give each shape a `data-part` with the
   part's node name so it highlights together with the 3D part.
5. Add a provenance record under `pipeline/provenance/rocket-engines/`
   (CLAUDE.md hard rule).

### Conventions the viewer relies on (Blender export)

- Every part is one node under the engine root. The manifest lists it with
  `explode_offset` (metres, Blender axes) and `explode_order`.
- The thrust axis is Blender +Z. The viewer lays the engine on its side.
- Parts whose origin is on the thrust axis are the ones that get cut in
  Cutaway. A part can override this with `cut: true` or `cut: false` (custom
  property `cutaway` in Blender).
- A part with `spin` (axis and revolutions per second) rotates in Flow mode,
  such as a pump rotor.
- Flow meshes are bundles of thin streamline tubes. UV.x is the travel time
  along the line in seconds, so a streak moves at the local flow speed. UV.y
  is the end fade and the second UV set's y is temperature (both stored as
  `1 - value`, because the glTF export flips V).
- `role: "context"` marks schematic parts such as the tanks.
- An engine can have more than one operating mode in Flow. Tag a flow object
  with the custom property `flow_variant` and list the modes under
  `flow_model.variants` on the root (`id`, `label`, `caption`). Untagged
  streams show in every mode.

### Known limits (carried over from the approved demo)

- Cut faces are not capped, so thick walls look hollow in Cutaway.
- Flow speeds are on a compressed scale (display speed = 0.22 · v^0.32),
  because the real ones span five orders of magnitude. Exhaust speed and
  temperature come from a 1-D isentropic model with assumed gas properties;
  liquid speeds are nominal. See `flow_model` in each manifest.
- The models are uncompressed GLB. The page was designed for desktop.
