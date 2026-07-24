# Concept pages — how to edit and create them (no coding needed)

One JSON file in this folder = one concept page. The page template reads the
file and builds everything: hero, 3D view, pins, overview, article, sources,
signup, footer. **You never touch HTML/CSS/TS** — if something can't be done
from the JSON, that's a template gap: ask for it.

- **View a page:** `/concept/?id=<filename>` — e.g. `/concept/?id=lunar-base`
  → https://kari-n0.github.io/space-catalogue/concept/?id=lunar-base
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
- `intro` — the lead paragraph.
- `features` — one entry per row (any count works; they alternate sides).
  Each has `label` (mono index line), `title`, `text`, and
  `view_angle_deg` — how many degrees that window's camera is rotated
  around the scene compared to the main view.

### `article` — the free-form "Specifications" section
A list of blocks, rendered in order. Three kinds:
```json
{ "type": "chapter",   "text": "A heading" }
{ "type": "paragraph", "text": "Running text…" }
{ "type": "image",     "file": "assets/…/fig.webp", "caption": "FIG_01 — caption" }
```
Write as many chapters/paragraphs/images as you like, in any order.

### `sources`
`items`: list of `{ "label": "SRC_01", "text": "citation…" }` rows.

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
