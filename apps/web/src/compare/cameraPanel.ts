// Live camera panel for the splat-compare tool (dev-only; never built, never
// deployed — see compare/main.ts).
//
// Splats from different captures differ in scale by three orders of magnitude
// (the de Gerlache terrain opens at 45 km, an mk2 pad splat at ~100 m), so a
// window framed by one concept-JSON camera block shows the next splat as a
// speck — or nothing at all, past the near/far clip. This panel exposes
// exactly the fields of the concept-JSON `camera` block (same author-facing
// names, units and clamps as content/concepts/README.md) and drives the four
// live cameras with them, so a framing can be dialled in on screen and then
// copied straight into content/concepts/<id>.json.
//
// The panel never decides framing (art-direction boundary): values start from
// the concept JSON — or, for an unauthored window, from the viewer's own
// neutral auto-fit — and every change is the author's. "Fit" re-runs that same
// neutral utility fit (scale only: target + distance/clip; the current angles
// and lens are left alone).
//
// Liveness note: the feature windows are driven by loadViewer's direct
// controls, which read move_speed / glide_after_release live but bake
// rotate_speed / zoom_speed at attach time — those two therefore ask the host
// for a view re-attach (opts.onReattach).

import type { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera";
import type { CameraControls, CameraEnvelope } from "../catalogue/concept";

export interface CamRange {
  min: number | null;
  max: number | null;
  start: number;
}

/** The concept-JSON `camera` block, in author-facing names and units. */
export interface CamState {
  look_at_m: [number, number, number];
  distance_m: CamRange;
  angle_around_deg: CamRange;
  angle_up_down_deg: CamRange;
  zoom_fov_deg: number;
  move_limit_m: number | null;
  clip_near_m: number | null;
  clip_far_m: number | null;
  controls: CameraControls;
}

const DEG = 180 / Math.PI;
const rad = (d: number) => d / DEG;
const deg = (r: number) => r * DEG;
const norm180 = (d: number) => ((((d + 180) % 360) + 360) % 360) - 180;
const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

// GroundPanCamera is constructed at alpha -90°, beta 1.1 rad in loadViewer;
// used only to fill a start field the JSON omits, so the panel reports what
// the camera actually does rather than inventing an opening pose.
const CTOR_ALPHA_DEG = -90;
const CTOR_BETA_DEG = deg(1.1);
const CTOR_RADIUS = 9;

/** Viewer defaults from cameraEnvelope.ts, mirrored for the "empty = default" hints. */
const DEFAULT_NEAR = 0.05;
const DEFAULT_FAR = 10000;

const clone = (s: CamState): CamState => ({
  look_at_m: [s.look_at_m[0], s.look_at_m[1], s.look_at_m[2]],
  distance_m: { ...s.distance_m },
  angle_around_deg: { ...s.angle_around_deg },
  angle_up_down_deg: { ...s.angle_up_down_deg },
  zoom_fov_deg: s.zoom_fov_deg,
  move_limit_m: s.move_limit_m,
  clip_near_m: s.clip_near_m,
  clip_far_m: s.clip_far_m,
  controls: { ...s.controls },
});

export function stateFromEnvelope(e: CameraEnvelope): CamState {
  return {
    look_at_m: [e.target_m[0], e.target_m[1], e.target_m[2]],
    distance_m: {
      min: e.radius_m.min,
      max: e.radius_m.max,
      // no authored start = the camera keeps its constructed radius, which
      // Babylon's per-frame _checkLimits then pulls into the authored range.
      // Report that, rather than inventing an opening distance from a limit.
      start: e.radius_m.default ?? clamp(CTOR_RADIUS, e.radius_m.min ?? CTOR_RADIUS, e.radius_m.max ?? CTOR_RADIUS),
    },
    angle_around_deg: { min: e.alpha_deg.min, max: e.alpha_deg.max, start: e.alpha_deg.default ?? CTOR_ALPHA_DEG },
    angle_up_down_deg: { min: e.beta_deg.min, max: e.beta_deg.max, start: e.beta_deg.default ?? CTOR_BETA_DEG },
    zoom_fov_deg: e.fov_deg,
    move_limit_m: e.pan_m?.max_from_center ?? null,
    clip_near_m: e.clip_near_m ?? null,
    clip_far_m: e.clip_far_m ?? null,
    controls: { ...e.controls },
  };
}

/**
 * Placeholder state for an unauthored (auto-fit) window, used only until that
 * window's splat lands and setFrom() replaces it with the viewer's measured
 * numbers: the camera's constructed pose and the auto-fit lens, nothing
 * invented.
 */
export function defaultCamState(controls: CameraControls): CamState {
  return {
    look_at_m: [0, 0, 0],
    distance_m: { min: null, max: null, start: CTOR_RADIUS },
    angle_around_deg: { min: null, max: null, start: CTOR_ALPHA_DEG },
    angle_up_down_deg: { min: null, max: null, start: CTOR_BETA_DEG },
    zoom_fov_deg: 45,
    move_limit_m: null,
    clip_near_m: null,
    clip_far_m: null,
    controls: { ...controls },
  };
}

/**
 * Restore panel state from the URL. Hand-edited/truncated `?cam=` is normal in
 * a dev tool, so every field is validated against `base` individually — a bad
 * one falls back instead of poisoning the whole camera.
 */
export function camStateFromJson(text: string, base: CamState): CamState | null {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return null;
  }
  if (typeof raw !== "object" || raw === null) return null;
  const r = raw as Record<string, unknown>;
  const out = clone(base);

  const numOr = (v: unknown, fallback: number): number => (typeof v === "number" && Number.isFinite(v) ? v : fallback);
  const limOr = (v: unknown, fallback: number | null): number | null =>
    v === null ? null : typeof v === "number" && Number.isFinite(v) ? v : fallback;
  const range = (v: unknown, fallback: CamRange): CamRange => {
    if (typeof v !== "object" || v === null) return fallback;
    const o = v as Record<string, unknown>;
    return { min: limOr(o.min, fallback.min), max: limOr(o.max, fallback.max), start: numOr(o.start, fallback.start) };
  };

  const look = r.look_at_m;
  if (Array.isArray(look) && look.length === 3 && look.every((v) => typeof v === "number" && Number.isFinite(v))) {
    out.look_at_m = [look[0] as number, look[1] as number, look[2] as number];
  }
  out.distance_m = range(r.distance_m, out.distance_m);
  out.angle_around_deg = range(r.angle_around_deg, out.angle_around_deg);
  out.angle_up_down_deg = range(r.angle_up_down_deg, out.angle_up_down_deg);
  out.zoom_fov_deg = clamp(numOr(r.zoom_fov_deg, out.zoom_fov_deg), 1, 179);
  out.move_limit_m = limOr(r.move_limit_m, out.move_limit_m);
  out.clip_near_m = limOr(r.clip_near_m, out.clip_near_m);
  out.clip_far_m = limOr(r.clip_far_m, out.clip_far_m);
  if (typeof r.controls === "object" && r.controls !== null) {
    const c = r.controls as Record<string, unknown>;
    out.controls = {
      rotate_speed: clamp(numOr(c.rotate_speed, out.controls.rotate_speed), 0.1, 10),
      move_speed: clamp(numOr(c.move_speed, out.controls.move_speed), 0.1, 10),
      zoom_speed: clamp(numOr(c.zoom_speed, out.controls.zoom_speed), 0.1, 10),
      glide_after_release: clamp(numOr(c.glide_after_release, out.controls.glide_after_release), 0, 0.95),
    };
  }
  return out;
}

/** Read a live camera back into panel state (an auto-fit window's real numbers). */
export function stateFromCamera(cam: ArcRotateCamera, controls: CameraControls): CamState {
  const limDeg = (v: number | null): number | null => (v == null ? null : Math.round(deg(v) * 100) / 100);
  return {
    look_at_m: [cam.target.x, cam.target.y, cam.target.z],
    distance_m: { min: cam.lowerRadiusLimit, max: cam.upperRadiusLimit, start: cam.radius },
    angle_around_deg: { min: limDeg(cam.lowerAlphaLimit), max: limDeg(cam.upperAlphaLimit), start: norm180(deg(cam.alpha)) },
    angle_up_down_deg: { min: limDeg(cam.lowerBetaLimit), max: limDeg(cam.upperBetaLimit), start: deg(cam.beta) },
    zoom_fov_deg: deg(cam.fov),
    move_limit_m: cam.panningDistanceLimit ?? null,
    clip_near_m: cam.minZ,
    clip_far_m: cam.maxZ,
    controls: { ...controls },
  };
}

/* ------------------------------- apply ---------------------------------- */

// Babylon's alpha is a continuous angle and its clamp does not wrap: express
// the authored arc in the 2π branch nearest the camera's current alpha, so
// applying limits never hard-snaps the azimuth (same rule as applyEnvelope).
function pushAlphaLimits(cam: ArcRotateCamera, s: CamState): void {
  const { min, max } = s.angle_around_deg;
  if (min == null || max == null) {
    cam.lowerAlphaLimit = min == null ? null : rad(min);
    cam.upperAlphaLimit = max == null ? null : rad(max);
    return;
  }
  const lo = rad(min);
  const hi = rad(max);
  const turn = 2 * Math.PI;
  const shift = Math.round((cam.alpha - (lo + hi) / 2) / turn) * turn;
  cam.lowerAlphaLimit = lo + shift;
  cam.upperAlphaLimit = hi + shift;
}

function pushBetaLimits(cam: ArcRotateCamera, s: CamState): void {
  const { min, max } = s.angle_up_down_deg;
  cam.lowerBetaLimit = min == null ? 0.01 : rad(min);
  cam.upperBetaLimit = max == null ? Math.PI - 0.01 : rad(max);
}

function pushLookAt(cam: ArcRotateCamera, s: CamState): void {
  const [x, y, z] = s.look_at_m;
  cam.target.set(x, y, z);
  // the pan clamp measures from here (groundPanCamera.slideClamp)
  cam.panningOriginTarget.set(x, y, z);
}

function pushMoveLimit(cam: ArcRotateCamera, s: CamState): void {
  const v = s.move_limit_m;
  cam.panningAxis.set(1, 0, 1); // ground-plane pan, as applyEnvelope does
  cam.panningOriginTarget.set(s.look_at_m[0], s.look_at_m[1], s.look_at_m[2]);
  cam.panningDistanceLimit = v != null && v > 0 ? v : null;
}

/* ------------------------------- fields --------------------------------- */

interface Field {
  key: string;
  label: string;
  group: string;
  hint?: string;
  nullable: boolean;
  /** rotate/zoom speed are baked into the direct controls at attach time. */
  reattach?: boolean;
  slider?: { min: number; max: number; step: number };
  get(s: CamState): number | null;
  set(s: CamState, v: number | null): void;
  push(cam: ArcRotateCamera, s: CamState): void;
}

const G_LOOK = "Look at (m)";
const G_DIST = "Distance (m)";
const G_AROUND = "Around (°)";
const G_UPDOWN = "Up / down (°)";
const G_LENS = "Lens, clipping, move";
const G_FEEL = "Feel";

function axisField(i: 0 | 1 | 2, label: string): Field {
  return {
    key: `look_at_m.${i}`,
    label,
    group: G_LOOK,
    nullable: false,
    get: (s) => s.look_at_m[i],
    set: (s, v) => {
      if (v != null) s.look_at_m[i] = v;
    },
    push: pushLookAt,
  };
}

const FIELDS: Field[] = [
  axisField(0, "x"),
  axisField(1, "y"),
  axisField(2, "z"),

  {
    key: "distance_m.start",
    label: "start",
    group: G_DIST,
    hint: "opening distance — moves the camera now",
    nullable: false,
    get: (s) => s.distance_m.start,
    set: (s, v) => {
      if (v != null) s.distance_m.start = v;
    },
    push: (cam, s) => {
      cam.radius = s.distance_m.start;
    },
  },
  {
    key: "distance_m.min",
    label: "min",
    group: G_DIST,
    hint: "closest zoom — empty = unlimited",
    nullable: true,
    get: (s) => s.distance_m.min,
    set: (s, v) => {
      s.distance_m.min = v;
    },
    push: (cam, s) => {
      cam.lowerRadiusLimit = s.distance_m.min;
    },
  },
  {
    key: "distance_m.max",
    label: "max",
    group: G_DIST,
    hint: "furthest zoom — empty = unlimited",
    nullable: true,
    get: (s) => s.distance_m.max,
    set: (s, v) => {
      s.distance_m.max = v;
    },
    push: (cam, s) => {
      cam.upperRadiusLimit = s.distance_m.max;
    },
  },

  {
    key: "angle_around_deg.start",
    label: "start",
    group: G_AROUND,
    hint: "opening azimuth — moves the camera now",
    nullable: false,
    slider: { min: -180, max: 180, step: 1 },
    get: (s) => s.angle_around_deg.start,
    set: (s, v) => {
      if (v != null) s.angle_around_deg.start = v;
    },
    push: (cam, s) => {
      cam.alpha = rad(s.angle_around_deg.start);
      pushAlphaLimits(cam, s); // re-branch the limits around the new azimuth
    },
  },
  {
    key: "angle_around_deg.min",
    label: "min",
    group: G_AROUND,
    hint: "empty = free orbit",
    nullable: true,
    get: (s) => s.angle_around_deg.min,
    set: (s, v) => {
      s.angle_around_deg.min = v;
    },
    push: pushAlphaLimits,
  },
  {
    key: "angle_around_deg.max",
    label: "max",
    group: G_AROUND,
    hint: "empty = free orbit",
    nullable: true,
    get: (s) => s.angle_around_deg.max,
    set: (s, v) => {
      s.angle_around_deg.max = v;
    },
    push: pushAlphaLimits,
  },

  {
    key: "angle_up_down_deg.start",
    label: "start",
    group: G_UPDOWN,
    hint: "0 = top-down, 90 = horizon — moves the camera now",
    nullable: false,
    slider: { min: 1, max: 179, step: 1 },
    get: (s) => s.angle_up_down_deg.start,
    set: (s, v) => {
      if (v != null) s.angle_up_down_deg.start = v;
    },
    push: (cam, s) => {
      cam.beta = rad(s.angle_up_down_deg.start);
    },
  },
  {
    key: "angle_up_down_deg.min",
    label: "min",
    group: G_UPDOWN,
    hint: "empty = viewer default 0.6°",
    nullable: true,
    get: (s) => s.angle_up_down_deg.min,
    set: (s, v) => {
      s.angle_up_down_deg.min = v;
    },
    push: pushBetaLimits,
  },
  {
    key: "angle_up_down_deg.max",
    label: "max",
    group: G_UPDOWN,
    hint: "empty = viewer default 179.4°",
    nullable: true,
    get: (s) => s.angle_up_down_deg.max,
    set: (s, v) => {
      s.angle_up_down_deg.max = v;
    },
    push: pushBetaLimits,
  },

  {
    key: "zoom_fov_deg",
    label: "fov",
    group: G_LENS,
    hint: "1–179",
    nullable: false,
    slider: { min: 10, max: 120, step: 1 },
    get: (s) => s.zoom_fov_deg,
    set: (s, v) => {
      if (v != null) s.zoom_fov_deg = clamp(v, 1, 179);
    },
    push: (cam, s) => {
      cam.fov = rad(s.zoom_fov_deg);
    },
  },
  {
    key: "clip_near_m",
    label: "clip near",
    group: G_LENS,
    hint: `empty = ${DEFAULT_NEAR} m`,
    nullable: true,
    get: (s) => s.clip_near_m,
    set: (s, v) => {
      s.clip_near_m = v;
    },
    push: (cam, s) => {
      cam.minZ = s.clip_near_m ?? DEFAULT_NEAR;
    },
  },
  {
    key: "clip_far_m",
    label: "clip far",
    group: G_LENS,
    hint: `empty = ${DEFAULT_FAR} m — km scenes must raise this`,
    nullable: true,
    get: (s) => s.clip_far_m,
    set: (s, v) => {
      s.clip_far_m = v;
    },
    push: (cam, s) => {
      cam.maxZ = s.clip_far_m ?? DEFAULT_FAR;
    },
  },
  {
    key: "move_limit_m",
    label: "move limit",
    group: G_LENS,
    // NB the same JSON value means something else on the main view: live_view's
    // camera runs Babylon's stock input path, where no move_limit_m = pan OFF.
    hint: "how far a right-drag may pan from look-at — empty = no limit in an Overview window (in live_view it turns panning off)",
    nullable: true,
    get: (s) => s.move_limit_m,
    set: (s, v) => {
      s.move_limit_m = v;
    },
    push: pushMoveLimit,
  },

  {
    key: "controls.rotate_speed",
    label: "rotate",
    group: G_FEEL,
    hint: "0.1–10 · re-attaches the windows",
    nullable: false,
    reattach: true,
    slider: { min: 0.1, max: 5, step: 0.1 },
    get: (s) => s.controls.rotate_speed,
    set: (s, v) => {
      if (v != null) s.controls.rotate_speed = clamp(v, 0.1, 10);
    },
    push: () => {
      /* baked at attach time — applied by the re-attach */
    },
  },
  {
    key: "controls.move_speed",
    label: "move",
    group: G_FEEL,
    hint: "0.1–10 · live",
    nullable: false,
    slider: { min: 0.1, max: 5, step: 0.1 },
    get: (s) => s.controls.move_speed,
    set: (s, v) => {
      if (v != null) s.controls.move_speed = clamp(v, 0.1, 10);
    },
    push: () => {
      /* read live from the shared controls object */
    },
  },
  {
    key: "controls.zoom_speed",
    label: "zoom",
    group: G_FEEL,
    hint: "0.1–10 · re-attaches the windows",
    nullable: false,
    reattach: true,
    slider: { min: 0.1, max: 5, step: 0.1 },
    get: (s) => s.controls.zoom_speed,
    set: (s, v) => {
      if (v != null) s.controls.zoom_speed = clamp(v, 0.1, 10);
    },
    push: () => {
      /* baked at attach time — applied by the re-attach */
    },
  },
  {
    key: "controls.glide_after_release",
    label: "glide",
    group: G_FEEL,
    hint: "0–0.95 · live",
    nullable: false,
    slider: { min: 0, max: 0.95, step: 0.05 },
    get: (s) => s.controls.glide_after_release,
    set: (s, v) => {
      if (v != null) s.controls.glide_after_release = clamp(v, 0, 0.95);
    },
    push: (cam, s) => {
      cam.inertia = s.controls.glide_after_release;
      cam.panningInertia = s.controls.glide_after_release;
    },
  },
];

/** Every field onto one camera — new windows, "go to start", restored URL state. */
export function applyState(cam: ArcRotateCamera, s: CamState): void {
  for (const f of FIELDS) f.push(cam, s);
}

/* --------------------------------- fit ----------------------------------- */

/**
 * Neutral scale fit for whatever splat this camera's scene holds — the same
 * measurement loadViewer uses for an unauthored window (robust 90th-percentile
 * radius around the median of the splat's own centers, so the routine outlier
 * gaussians and the lunar tile's ~100 km skirt don't zoom the subject to a
 * speck), applied to distance + clipping only. Angles and fov are left as the
 * author has them: this rescues scale, it does not choose a shot.
 * Returns false when the scene has no splat yet.
 */
export function fitCameraToSplat(cam: ArcRotateCamera, s: CamState): boolean {
  const splat = cam.getScene().meshes.find((m) => m.getClassName() === "GaussianSplattingMesh");
  if (!splat) return false;
  splat.computeWorldMatrix(true);
  const m = splat.getWorldMatrix().m;
  const toWorld = (x: number, y: number, z: number): [number, number, number] => [
    m[0] * x + m[4] * y + m[8] * z + m[12],
    m[1] * x + m[5] * y + m[9] * z + m[13],
    m[2] * x + m[6] * y + m[10] * z + m[14],
  ];

  let cx = 0;
  let cy = 0;
  let cz = 0;
  let radius = 1;
  const pos = (splat as unknown as { _splatPositions?: Float32Array })._splatPositions;
  if (pos && pos.length >= 3) {
    const n = pos.length / 3;
    const step = Math.max(1, Math.floor(n / 8000));
    const xs: number[] = [];
    const ys: number[] = [];
    const zs: number[] = [];
    for (let i = 0; i < n; i += step) {
      const [wx, wy, wz] = toWorld(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]);
      xs.push(wx);
      ys.push(wy);
      zs.push(wz);
    }
    const median = (a: number[]): number => {
      const sorted = a.slice().sort((p, q) => p - q);
      return sorted[sorted.length >> 1];
    };
    cx = median(xs);
    cy = median(ys);
    cz = median(zs);
    const d = xs.map((x, k) => Math.hypot(x - cx, ys[k] - cy, zs[k] - cz)).sort((p, q) => p - q);
    radius = d[Math.floor(d.length * 0.9)] || 1;
  } else {
    const bs = splat.getBoundingInfo().boundingSphere;
    cx = bs.centerWorld.x;
    cy = bs.centerWorld.y;
    cz = bs.centerWorld.z;
    radius = bs.radiusWorld;
  }
  radius = Math.max(0.1, radius);

  // same ratios as the viewer's auto-fit
  s.look_at_m = [cx, cy, cz];
  s.distance_m = { min: radius * 0.3, max: radius * 10, start: radius * 2.6 };
  s.clip_near_m = Math.max(0.01, radius * 0.01);
  s.clip_far_m = radius * 200;
  return true;
}

/* -------------------------------- JSON ----------------------------------- */

const rnd = (v: number, dp: number): number => Number(v.toFixed(dp));
const rndOrNull = (v: number | null, dp: number): number | null => (v == null ? null : rnd(v, dp));

/**
 * The state as paste-ready concept JSON.
 *
 * `controls` is emitted as a SIBLING of `camera`, because that is where an
 * Overview window's feel actually comes from: page.ts passes
 * `features[i].controls` to attachFeatureView, and the direct window controls
 * never read `features[i].camera.controls`. (For live_view it is the other way
 * round — that camera runs Babylon's stock input path, so its controls belong
 * inside `live_view.camera`.) The block is also emitted inside `camera` so a
 * live_view paste keeps working; the duplicate is harmless in a feature.
 */
export function stateToJson(s: CamState): string {
  const block = {
    look_at_m: s.look_at_m.map((v) => rnd(v, 2)),
    distance_m: {
      min: rndOrNull(s.distance_m.min, 2),
      max: rndOrNull(s.distance_m.max, 2),
      start: rnd(s.distance_m.start, 2),
    },
    angle_around_deg: {
      min: rndOrNull(s.angle_around_deg.min, 1),
      max: rndOrNull(s.angle_around_deg.max, 1),
      start: rnd(s.angle_around_deg.start, 1),
    },
    angle_up_down_deg: {
      min: rndOrNull(s.angle_up_down_deg.min, 1),
      max: rndOrNull(s.angle_up_down_deg.max, 1),
      start: rnd(s.angle_up_down_deg.start, 1),
    },
    zoom_fov_deg: rnd(s.zoom_fov_deg, 1),
    move_limit_m: rndOrNull(s.move_limit_m, 2),
    clip_near_m: rndOrNull(s.clip_near_m, 3),
    clip_far_m: rndOrNull(s.clip_far_m, 1),
    controls: {
      rotate_speed: rnd(s.controls.rotate_speed, 2),
      move_speed: rnd(s.controls.move_speed, 2),
      zoom_speed: rnd(s.controls.zoom_speed, 2),
      glide_after_release: rnd(s.controls.glide_after_release, 2),
    },
  };
  return (
    `"controls": ${JSON.stringify(block.controls)},\n` + `"camera": ${JSON.stringify(block, null, 2)}`
  );
}

/* -------------------------------- panel ---------------------------------- */

export interface CameraPanelOptions {
  initial: CamState;
  /** Every live window camera (may be empty while splats load). */
  cameras: () => ArcRotateCamera[];
  /** The focused window's camera — source for the live readout and "capture view". */
  leader: () => ArcRotateCamera | null;
  /** Which window that is ("window 2"), for the readout. */
  leaderLabel?: () => string;
  /** The controls object handed to attachFeatureView; mutated in place (live feel). */
  controls: CameraControls;
  /** State changed (host persists it in the URL). */
  onStateChange: (s: CamState) => void;
  /** rotate/zoom speed changed — the host must re-attach the views. */
  onReattach: () => void;
  /** "Reset" — host drops the URL state and reloads. */
  onReset: () => void;
  /** True when the state came from the URL rather than the concept JSON. */
  startDirty?: boolean;
}

export interface CameraPanelHandle {
  el: HTMLElement;
  state(): CamState;
  /** Push the whole state onto a camera (called when a window's splat lands). */
  applyTo(cam: ArcRotateCamera): void;
  /** Adopt a camera's values (an auto-fit window's real numbers) — only while clean. */
  setFrom(cam: ArcRotateCamera): void;
  dirty(): boolean;
  dispose(): void;
}

export function mountCameraPanel(opts: CameraPanelOptions): CameraPanelHandle {
  const s = clone(opts.initial);
  // Per-field ownership, not one global dirty flag: only a field the author
  // actually set is pushed onto a window, and only an untouched field may be
  // refilled from a window's own auto-fit. Without this, tweaking one control
  // before the splats land would stamp the whole placeholder camera (target
  // 0,0,0 at 9 m) onto every window.
  const touched = new Set<string>(opts.startDirty === true ? FIELDS.map((f) => f.key) : []);
  const touch = (keys: readonly string[]): void => {
    for (const f of FIELDS) {
      if (keys.some((k) => f.key === k || f.key.startsWith(`${k}.`))) touched.add(f.key);
    }
  };

  const el = <K extends keyof HTMLElementTagNameMap>(
    tag: K,
    className?: string,
    text?: string,
  ): HTMLElementTagNameMap[K] => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  };

  const fmt = (v: number | null): string => {
    if (v == null) return "";
    const a = Math.abs(v);
    const dp = a >= 1000 ? 0 : a >= 100 ? 1 : a >= 1 ? 2 : 4;
    return String(Number(v.toFixed(dp)));
  };

  const root = el("details", "compare-camera");
  root.open = true;
  const summary = el("summary", undefined, "Camera — live, applies to all four windows");
  root.appendChild(summary);

  const body = el("div", "compare-camera-body");
  root.appendChild(body);

  // declared up here so the field handlers below can refresh it
  const jsonEl = el("pre", undefined, stateToJson(s));

  const status = el("span", "compare-camera-status", "");
  const setStatus = (msg: string): void => {
    status.textContent = msg;
  };

  const inputs = new Map<string, { number: HTMLInputElement; slider: HTMLInputElement | null }>();

  const syncInputs = (): void => {
    for (const f of FIELDS) {
      const pair = inputs.get(f.key);
      if (!pair) continue;
      const v = f.get(s);
      if (document.activeElement !== pair.number) pair.number.value = fmt(v);
      if (pair.slider && document.activeElement !== pair.slider && v != null) pair.slider.value = String(v);
    }
    jsonEl.textContent = stateToJson(s);
  };

  const pushAll = (): void => {
    for (const cam of opts.cameras()) applyState(cam, s);
  };

  /** Push one field (an edit) or a named subset (a fit) — never more than the
   *  action touched, so a scale fix can't also snap the author's angles. */
  const changed = (f?: Field, keys?: readonly string[]): void => {
    const cams = opts.cameras();
    for (const field of FIELDS) {
      if (f ? field !== f : keys && !keys.some((k) => field.key === k || field.key.startsWith(`${k}.`))) continue;
      touched.add(field.key);
      for (const cam of cams) field.push(cam, s);
    }
    jsonEl.textContent = stateToJson(s);
    warnClamped();
    opts.onStateChange(s);
  };

  // Babylon re-clamps the camera against its own limits every frame, so a start
  // value outside min/max silently snaps — say so instead of looking broken.
  const warnClamped = (): void => {
    const out: string[] = [];
    const d = s.distance_m;
    if ((d.min != null && d.start < d.min) || (d.max != null && d.start > d.max)) out.push("distance start");
    const b = s.angle_up_down_deg;
    if ((b.min != null && b.start < b.min) || (b.max != null && b.start > b.max)) out.push("up/down start");
    // azimuth wraps: compare in the 2π branch the limits live in (applyEnvelope
    // does the same shift), so -170 inside [170, 200] does not read as outside
    const a = s.angle_around_deg;
    if (a.min != null && a.max != null) {
      const mid = (a.min + a.max) / 2;
      const start = a.start - Math.round((a.start - mid) / 360) * 360;
      if (start < a.min || start > a.max) out.push("around start");
    }
    if (out.length === 0 && s.clip_near_m != null && s.clip_far_m != null && s.clip_near_m >= s.clip_far_m) {
      setStatus("clip near is not below clip far — the window will render nothing");
      return;
    }
    setStatus(out.length ? `${out.join(", ")} outside min/max — the camera clamps` : "");
  };

  // controls live in the object loadViewer's direct controls read from
  const syncControls = (): void => {
    opts.controls.rotate_speed = s.controls.rotate_speed;
    opts.controls.move_speed = s.controls.move_speed;
    opts.controls.zoom_speed = s.controls.zoom_speed;
    opts.controls.glide_after_release = s.controls.glide_after_release;
  };

  // ---- field rows, grouped -------------------------------------------------
  const groups = new Map<string, HTMLElement>();
  for (const f of FIELDS) {
    let group = groups.get(f.group);
    if (!group) {
      group = el("div", "compare-camera-group");
      group.appendChild(el("h4", undefined, f.group));
      groups.set(f.group, group);
      body.appendChild(group);
    }

    const row = el("label", "compare-camera-row");
    row.appendChild(el("span", "compare-camera-label", f.label));

    const number = el("input", "compare-camera-num");
    number.type = "text"; // text, not number: "" means null and spinners round
    number.inputMode = "decimal";
    number.value = fmt(f.get(s));
    if (f.hint) number.title = f.hint;
    row.appendChild(number);

    let slider: HTMLInputElement | null = null;
    if (f.slider) {
      slider = el("input", "compare-camera-slider");
      slider.type = "range";
      slider.min = String(f.slider.min);
      slider.max = String(f.slider.max);
      slider.step = String(f.slider.step);
      const v = f.get(s);
      slider.value = String(v ?? f.slider.min);
      row.appendChild(slider);
    }
    if (f.hint) row.title = f.hint;
    group.appendChild(row);
    inputs.set(f.key, { number, slider });

    const commit = (raw: string, fromSlider: boolean): void => {
      const t = raw.trim();
      const parsed = t === "" ? null : Number(t);
      if (parsed != null && !Number.isFinite(parsed)) return; // mid-typing garbage
      if (parsed == null && !f.nullable) return;
      f.set(s, parsed);
      const applied = f.get(s); // set() may clamp
      if (fromSlider) {
        number.value = fmt(applied);
      } else if (slider && applied != null) {
        slider.value = String(applied);
      }
      syncControls();
      changed(f);
    };

    number.addEventListener("input", () => commit(number.value, false));
    slider?.addEventListener("input", () => commit(slider.value, true));
    // on blur/enter: show what the field actually holds — an entry that was
    // rejected ("abc", "" in a non-nullable field) or clamped must not be left
    // on screen looking applied
    const resync = (): void => {
      const v = f.get(s);
      number.value = fmt(v);
      if (slider && v != null) slider.value = String(v);
    };
    number.addEventListener("change", resync);
    slider?.addEventListener("change", resync);
    // rotate/zoom speed are baked at attach — re-attach once the drag/typing ends
    if (f.reattach) {
      const reattach = (): void => {
        setStatus("re-attaching windows…");
        opts.onReattach();
      };
      number.addEventListener("change", reattach);
      slider?.addEventListener("change", reattach);
    }
  }

  // ---- live readout + buttons ---------------------------------------------
  const actions = el("div", "compare-camera-actions");

  const readout = el("span", "compare-camera-live", "current view: —");

  const fitBtn = el("button", "compare-btn", "Fit to splat");
  fitBtn.type = "button";
  fitBtn.title = "Neutral scale fit (distance + clipping) per the focused window's splat — angles and fov untouched";
  fitBtn.addEventListener("click", () => {
    const lead = opts.leader() ?? opts.cameras()[0] ?? null;
    if (!lead || !fitCameraToSplat(lead, s)) {
      setStatus("no splat loaded yet");
      return;
    }
    // only what the fit measured — the current orbit angles and the authored
    // start angles both stay exactly as they are
    changed(undefined, ["look_at_m", "distance_m", "clip_near_m", "clip_far_m"]);
    syncInputs();
    setStatus(`fitted — ${fmt(s.distance_m.start)} m`);
  });

  const captureBtn = el("button", "compare-btn", "Capture view → start");
  captureBtn.type = "button";
  captureBtn.title = "Copy the focused window's current position into the start / look-at fields";
  captureBtn.addEventListener("click", () => {
    const lead = opts.leader() ?? opts.cameras()[0] ?? null;
    if (!lead) {
      setStatus("no window loaded yet");
      return;
    }
    s.look_at_m = [lead.target.x, lead.target.y, lead.target.z];
    s.distance_m.start = lead.radius;
    s.angle_around_deg.start = norm180(deg(lead.alpha));
    s.angle_up_down_deg.start = deg(lead.beta);
    touch(["look_at_m", "distance_m.start", "angle_around_deg.start", "angle_up_down_deg.start"]);
    // this window is already there; only ITS pan origin follows the new look-at
    // (the other windows keep theirs until "Go to start" moves them too)
    pushMoveLimit(lead, s);
    syncInputs();
    opts.onStateChange(s);
    setStatus("captured");
  });

  const startBtn = el("button", "compare-btn", "Go to start");
  startBtn.type = "button";
  startBtn.title = "Put every window back on the start values above";
  startBtn.addEventListener("click", () => {
    pushAll();
    setStatus("back to start");
  });

  const copyBtn = el("button", "compare-btn", "Copy JSON");
  copyBtn.type = "button";
  copyBtn.title = "Copy this camera block for content/concepts/<id>.json";
  copyBtn.addEventListener("click", () => {
    const text = stateToJson(s);
    void navigator.clipboard
      .writeText(text)
      .then(() => setStatus("camera JSON copied"))
      .catch(() => setStatus("clipboard blocked — copy it from the JSON box below"));
  });

  const resetBtn = el("button", "compare-btn", "Reset");
  resetBtn.type = "button";
  resetBtn.title = "Drop these edits and reload from the concept JSON (or the auto-fit)";
  resetBtn.addEventListener("click", () => opts.onReset());

  actions.append(fitBtn, captureBtn, startBtn, copyBtn, resetBtn, status, readout);
  body.appendChild(actions);

  const jsonBox = el("details", "compare-camera-json");
  jsonBox.appendChild(el("summary", undefined, "JSON for content/concepts/<id>.json"));
  jsonBox.appendChild(
    el(
      "p",
      "compare-camera-hint",
      "Overview window: paste both keys into that feature — the window's feel comes from the outer " +
        "“controls”, camera.controls is ignored there. live_view: keep the controls inside “camera”. " +
        "Pasting replaces the block, so carry over any “_note” / “object_envelopes” you already have — " +
        "and on the main view, look_at_m and the min/max limits are generated by the capture export " +
        "(pipeline/pack/envelope_to_concept.py), not hand-edited.",
    ),
  );
  jsonEl.textContent = stateToJson(s);
  jsonBox.appendChild(jsonEl);
  body.appendChild(jsonBox);

  syncControls();

  // live readout of the focused window (the fields stay authoritative)
  const tick = setInterval(() => {
    const lead = opts.leader() ?? opts.cameras()[0] ?? null;
    const who = opts.leaderLabel ? opts.leaderLabel() : "current view";
    readout.textContent = lead
      ? `${who}: ${fmt(lead.radius)} m · around ${fmt(norm180(deg(lead.alpha)))}° · ` +
        `up/down ${fmt(deg(lead.beta))}° · look at ${fmt(lead.target.x)}, ${fmt(lead.target.y)}, ${fmt(lead.target.z)}`
      : `${who}: —`;
  }, 200);

  return {
    el: root,
    state: () => clone(s),
    // only fields the author set — an untouched window keeps exactly what
    // applyEnvelope (or the viewer's auto-fit) gave it
    applyTo: (cam) => {
      for (const f of FIELDS) {
        if (touched.has(f.key)) f.push(cam, s);
      }
    },
    // refill the untouched fields from a window's own framing, so the panel
    // reports real numbers instead of the placeholder
    setFrom: (cam) => {
      const read = stateFromCamera(cam, s.controls);
      for (const f of FIELDS) {
        if (!touched.has(f.key)) f.set(s, f.get(read));
      }
      syncInputs();
    },
    dirty: () => touched.size > 0,
    dispose: () => clearInterval(tick),
  };
}
