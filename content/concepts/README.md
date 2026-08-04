# Concept pages — how to edit and create them (no coding needed)

One JSON file in this folder = one concept page. The page template reads the
file and builds everything: hero, 3D view, pins, overview, article, sources,
signup, footer. **You never touch HTML/CSS/TS** — if something can't be done
from the JSON, that's a template gap: ask for it.

- **View a page:** `/concept/?id=<filename>` — e.g. `/concept/?id=lunar-base`
  → https://farsidelab.com/concept/?id=lunar-base
- **Edit a page:** change the JSON, commit, push → live in ~1 min.
- **New page:** copy `lunar-base.json` → `my-concept.json`, change `"id"`
  to `"my-concept"` (must match the filename), edit content, push.
  It's immediately available at `/concept/?id=my-concept`.
- **Images/videos/3D files:** put files in `apps/web/public/assets/…` and
  reference them by that path, e.g. `"assets/lunar-base/photo.webp"`.
  (During the placeholder phase everything lives in `assets/placeholders/`.)

## Field guide (top to bottom = page order)

### `hero` — the full-screen opening
| field | what it does |
|---|---|
| `label` | small mono label, e.g. `"Concept 001"` |
| `status` | text in the blue chip, e.g. `"In Development"` |
| `title_line_1` / `title_line_2` | the big two-tone headline (line 1 white, line 2 gray) |
| `era_line` | the mono line under the title |
| `button_text` | the white pill (scrolls to the 3D view) |
| `video` | looping background video (muted, autoplays) |
| `poster_image` | still image shown while the video loads / for reduced-motion visitors |

### `live_view` — the 3D gaussian-splat section
| field | what it does |
|---|---|
| `heading` | section kicker |
| `note` | mono line under the 3D stage |
| `scene_file` | the `.sog` splat file |
| `scene_file_mobile` | optional lighter `.sog` for phones (`null` = use the main one) |
| `camera.look_at_m` | point the camera orbits around, in meters `[x, y, z]` |
| `camera.distance_m` | zoom limits: `min`/`max`, and `start` = distance on load |
| `camera.angle_up_down_deg` | up/down tilt: `min`/`max` limits (degrees; 90 = horizon), and `start` = opening tilt |
| `camera.angle_around_deg` | horizontal orbit: `min`/`max` limits (`null` = free spin), and `start` = opening direction |
| `camera.zoom_fov_deg` | lens field of view |
| `camera.clip_near_m` | nearest visible distance (m); omit = `0.05`. Raise for large scenes to avoid flicker |
| `camera.clip_far_m` | farthest visible distance (m); omit = `10000` (10 km). **Large scenes MUST set this** or splats past ~10 km from the camera vanish ("fall off") |
| `camera.move_limit_m` | how far right-drag panning may move from `look_at_m`, in real meters. Reaching the limit slides along the boundary (no dead-stop). **Scale it to the scene**: at a 3.5 km viewing distance a 50 m limit spans ~8 screen pixels — for visible panning use a value comparable to the area you want reachable. `0`/omit = panning off |

The **opening shot** is `distance_m.start` + `angle_up_down_deg.start` + `angle_around_deg.start` (all three; each falls back to a sensible default if omitted). Change these to set where the camera sits and which way it faces when the page loads.
| `camera.controls.rotate_speed` | orbit drag speed — `1` = normal, `2` = twice as fast, `0.5` = half |
| `camera.controls.move_speed` | right-drag pan speed, same scale. At `1` the terrain tracks the pointer roughly 1:1 at any zoom distance and any tilt (including top-down) |
| `camera.controls.zoom_speed` | scroll/pinch zoom speed, same scale |
| `camera.controls.glide_after_release` | how long the camera keeps gliding after you let go: `0` = stops instantly, `0.9` = normal, `0.95` = long glide (max) |

The main `camera.controls` are the default feel for the main 3D view **and**
every Overview window. Each Overview feature ALSO carries its own `controls`
block — edit it to give one window a different feel (any field you leave out
falls back to the main view's value).

**Generated camera fields (capture pipeline — see CAPTURE.md):** once a scene
is trained from a capture vantage, `look_at_m`, `distance_m.min/max`,
`angle_up_down_deg` and `angle_around_deg` are exported from the SAME envelope
the training rig used (the `_camera_generated` note records where they came
from). Don't hand-edit those — move/scale the `ENV_`/`FOCUS_` objects in
Blender and re-export. Everything else in the camera block (`start`, `controls`,
`move_limit_m`, `zoom_fov_deg`) stays yours. `camera.object_envelopes` is a
generated map of per-object zoom envelopes (from child capture rigs): the
viewer can glide into one for a close-up of that object while enforcing its
own trained limits. Nothing on the page triggers them yet — how they're
triggered (pin click, button, …) is a separate design decision.

**Panning notes:** right-drag (or ctrl+left-drag) pans; left/middle drag
rotates; wheel/pinch zooms. Panning is deliberately OFF while zoomed into an
object close-up (`object_envelopes` carry no `move_limit_m` — the camera must
not pan off the trained region) and comes back when you zoom out to the main
view.

**Checking what the viewer actually loaded:** open the page with
`?debug=camera` — a live overlay shows the camera pose, the pan distance vs.
your `move_limit_m`, and every loaded `controls` value, so a stale or ignored
edit is visible immediately. Misspelled keys anywhere in the `camera` block
are named in the browser console (`unrecognized key … is IGNORED`), and
out-of-range values report what they were clamped to. Combine flags with a
comma: `?debug=camera,hotspots`.

**Seeing your edits:** the live site updates only after you commit + push
(deploy takes ~1 min — check the Actions tab turns green). Editing the file
on disk and refreshing the browser does nothing until then. After the deploy,
a normal refresh is enough — the page always fetches the latest JSON.

`pins` — clickable points in the 3D scene. Each pin:
```json
{
  "position_m": [0.9, 1.0, 1.2],
  "title": "Crew EVA",
  "text": "Shown in the popup when clicked.",
  "image": "assets/…/photo.webp"
}
```
`position_m` is a real 3D point in scene meters, in the **viewer frame** —
the same frame as `look_at_m`. This is NOT the raw Blender coordinate. To
convert a Blender point (an empty, a cursor position) into `position_m`:

1. Take the Blender world position of the point, `(Bx, By, Bz)`.
2. Subtract the vantage FOCUS empty's world position `(Fx, Fy, Fz)`
   (the splat's origin — for the current lunar-base captures it is
   `(5697.7695, -5286.2061, 1660.4834)`).
3. Swap the last two axes — **no sign flips**:

   `position_m = [Bx - Fx, Bz - Fz, By - Fy]`

   (viewer X = Blender X, viewer Y = Blender Z = height, viewer Z = Blender Y.)

Sanity check: the middle number is the point's height above the FOCUS — for
anything on the terrain it should be near the surrounding `look_at_m` heights
(tens of meters here), never hundreds. A wrong height reads as the pin
"sliding" over the terrain while orbiting (parallax).

**Verify after every pin or splat change:** open the page with
`?debug=hotspots` — magenta spheres render in-scene at each anchor. Orbit,
including top-down, and confirm each sphere stays glued to its feature and
each pin ring stays glued to its sphere.

Clicking a pin also glides the camera to it. `image` is optional (`null` for
text-only popups).

### `overview` — intro text + the live 3D windows
- `intro` — the lead paragraph (plain string). Used only when `intro_blocks`
  is absent.
- `intro_blocks` *(optional)* — a structured lead: an array of `paragraph` and
  `list` blocks (same shape as the `article` blocks above), rendered in order.
  When present it **replaces** `intro`. Use it when the lead needs more than one
  paragraph or an enumerated list, e.g.:
  ```json
  "intro_blocks": [
    { "type": "paragraph", "text": "Four resources make a camp permanent:" },
    { "type": "list", "items": ["Oxygen", "Water", "Energy", "Access to Earth"] },
    { "type": "paragraph", "text": "…" }
  ]
  ```
- `features` — one entry per row. **Any number works** (1, 2, 5, …) — add or
  remove entries freely; they alternate sides automatically.
  Each has `label` (mono index line), `title`, `text`, and
  `view_angle_deg` — how many degrees that window's camera is rotated
  around the scene compared to the main view.
- `features[].chip` *(optional)* — the small badge overlaid on that 3D window
  (shown uppercase). Each window is independent. Omit it for the default
  `"Live — Sample Scene"`; set `""` (empty) to hide the badge on that window.
- `features[].text_blocks` *(optional)* — multi-paragraph card body: an array
  of `paragraph` / `list` blocks (same schema as `intro_blocks`), rendered in
  place of the single `text` string. Omit it and `text` renders exactly as
  before. Cards with `text_blocks` top-align on desktop and the 3D window
  stays sticky beside the text while you scroll. Example:
  ```json
  "text_blocks": [
    { "type": "paragraph", "text": "First paragraph…" },
    { "type": "list", "items": ["Point one", "Point two"] },
    { "type": "paragraph", "text": "Closing paragraph…" }
  ]
  ```
- `features[].scene_file` *(optional)* — show a **different Gaussian splat** in
  that window instead of the hero splat. Give a path like the live-view
  `scene_file` (e.g. `"assets/splats/splat_mk2_d.sog"`); the window loads
  that splat in its own view and auto-fits the camera to it, rotated by
  `view_angle_deg`. Add `scene_file_mobile` for a lighter tier (falls back to
  `scene_file`). Omit or set `null` to keep the default: a view of the hero
  splat. Each distinct splat is a full download + GPU cost, so only add what you
  need.
- `features[].camera` *(optional)* — full per-window framing, **the same fields
  as `live_view.camera`** (`look_at_m`, `distance_m`, `angle_around_deg`,
  `angle_up_down_deg`, `zoom_fov_deg`, `move_limit_m`, `clip_near_m/far_m`,
  `controls`). When present it **replaces the auto-fit**; when absent the window
  auto-fits. `look_at_m` must be that splat's own focus point in meters (read it
  from Blender) — the hero's `look_at_m` won't match a different splat. The
  opening shot is `distance_m.start` + `angle_*_deg.start`, exactly like the
  hero. Every window controls all four windows' feel independently.
- `features[].pins` *(optional)* — POIs for that window. **Simpler than the hero
  pins: hover shows the `title`, click/tap smoothly re-centers the window's
  camera on `position_m` — no pop-up box.** Each entry needs `position_m`
  `[x,y,z]` (meters, hand-authored) and `title`; `text` is optional extra
  hover text. `image` is ignored here (no pop-up). Default is `[]` (no POIs).

`lunar-base.json`'s first Overview feature carries `_camera_example` and
`_pins_example` blocks (keys starting with `_` are ignored) — copy either and
rename to `camera` / `pins` to start authoring. The auto-fit is a neutral
utility framing; the `camera` block is yours to set.

### `article` — the free-form "Specifications" section
A list of blocks, rendered in order. Five kinds:
```json
{ "type": "chapter",   "text": "A heading" }
{ "type": "paragraph", "text": "Running text…" }
{ "type": "list",      "items": ["First point", "Second point", "Third point"] }
{ "type": "image",     "file": "assets/…/fig.webp", "caption": "FIG_01 — caption" }
{ "type": "video",     "file": "assets/…/anim-d.mp4", "file_webm": "assets/…/anim-d.webm",
  "file_mobile": "assets/…/anim-m.mp4", "file_mobile_webm": "assets/…/anim-m.webm",
  "poster": "assets/…/anim-poster.webp", "caption": "FIG_02 — caption" }
```
Write as many blocks as you like, in any order. A `list` renders with round
bullet markers in the brand's muted label color; empty/non-string items are
dropped. A `video` renders as a silent looping figure (autoplay muted loop,
plays inline, no controls, `preload="metadata"` + `poster` so nothing heavy
loads before it's near the viewport). Only `file` (MP4) is required; `file_webm`
is served preferentially where supported, and phones get the `*_mobile`
variants when present (same tiering as the splats). Keep loops ~5 s and well
under 5 MB.

### `sources`
`items`: list of `{ "label": "SRC_01", "text": "citation…" }` rows.
`intro` (optional): a paragraph shown above the rows in small dim text —
disclaimer/context; omit or `""` for none.

### `signup` — the email band
`kicker`, `heading_line_1`/`heading_line_2` (two-tone headline), `label`,
`placeholder`, `button`, `note`. The form is inert until the email service
account is activated.

### Top-level
`page_title` = browser-tab title. `footer_label` = mono text bottom-right.

## Tips
- Keys starting with `_` (like `_readme`) are ignored — use them for notes.
- JSON gotchas: every `"string"` in double quotes, no comma after the last
  item in a list, `null` (not empty) to switch something off.
- If the page shows "could not load", the JSON has a syntax error — paste the
  file into https://jsonlint.com to find the line.
- Mark unfinished copy with `[sample …]` brackets so nothing drafty ships
  unnoticed.
