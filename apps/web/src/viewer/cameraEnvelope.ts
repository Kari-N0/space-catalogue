// Envelope JSON → ArcRotateCamera limits. Degrees in JSON (Blender/authoring
// friendly), radians here. This mapping must stay the single place envelope
// semantics live — M2's export_dataset.py consumes the same JSON block.

import type { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import type { CameraControls, CameraEnvelope } from "../catalogue/concept";

const rad = (deg: number) => (deg * Math.PI) / 180;

/**
 * Input-side pan divisor at move_speed 1. groundPanCamera.ts multiplies the
 * same constant back out, so pan gain is defined THERE (ground-tracking,
 * radius-proportional) and this value only sets the units — keep the two in
 * sync via this export.
 */
export const PAN_BASE_SENSIBILITY = 350;

export function applyEnvelope(camera: ArcRotateCamera, e: CameraEnvelope): void {
  camera.setTarget(new Vector3(e.target_m[0], e.target_m[1], e.target_m[2]));
  camera.fov = rad(e.fov_deg);

  // Opening pose — each is optional; when absent the camera keeps its
  // constructed default. Set BEFORE the alpha limits so the wrap-normalization
  // below branches around the authored opening angle, not the constructed one.
  if (e.radius_m.default != null) camera.radius = e.radius_m.default;
  if (e.alpha_deg.default != null) camera.alpha = rad(e.alpha_deg.default);
  if (e.beta_deg.default != null) camera.beta = rad(e.beta_deg.default);

  camera.lowerRadiusLimit = e.radius_m.min;
  camera.upperRadiusLimit = e.radius_m.max;

  if (e.alpha_deg.min == null || e.alpha_deg.max == null) {
    camera.lowerAlphaLimit = e.alpha_deg.min == null ? null : rad(e.alpha_deg.min);
    camera.upperAlphaLimit = e.alpha_deg.max == null ? null : rad(e.alpha_deg.max);
  } else {
    // Babylon's alpha is a continuous angle (free orbiting accumulates turns) and
    // its limit clamp doesn't wrap: re-express the arc in the 2π-branch nearest
    // the camera's current alpha so applying limits never hard-snaps the azimuth.
    let lo = rad(e.alpha_deg.min);
    let hi = rad(e.alpha_deg.max);
    const turn = 2 * Math.PI;
    const shift = Math.round((camera.alpha - (lo + hi) / 2) / turn) * turn;
    lo += shift;
    hi += shift;
    camera.lowerAlphaLimit = lo;
    camera.upperAlphaLimit = hi;
  }
  camera.lowerBetaLimit = e.beta_deg.min == null ? 0.01 : rad(e.beta_deg.min);
  camera.upperBetaLimit = e.beta_deg.max == null ? Math.PI - 0.01 : rad(e.beta_deg.max);

  // Panning moves the target and can walk the camera out of the trained
  // envelope. When the envelope allows it (pan_m), constrain it to the ground
  // plane and clamp the target's distance from the scene center; otherwise off.
  const panEnabled = !!(e.pan_m && e.pan_m.max_from_center > 0);
  if (panEnabled && e.pan_m) {
    camera.panningAxis = new Vector3(1, 0, 1); // ground plane only
    camera.panningOriginTarget = new Vector3(e.target_m[0], e.target_m[1], e.target_m[2]);
    camera.panningDistanceLimit = e.pan_m.max_from_center;
    // an authored limit that spans a handful of pixels at the opening
    // framing reads as "panning is broken" (the live site shipped 5 m at a
    // 4.6 km distance = 0.7 px once) — say so instead of staying silent
    const heightPx = camera.getEngine().getRenderHeight() * camera.getEngine().getHardwareScalingLevel();
    if (heightPx > 0) {
      const pxSpan = (2 * e.pan_m.max_from_center * heightPx) / (2 * camera.radius * Math.tan(camera.fov / 2));
      if (pxSpan < 24) {
        console.info(
          `camera.move_limit_m ${e.pan_m.max_from_center} spans only ~${Math.max(1, Math.round(pxSpan))}px ` +
            `at the opening distance (${Math.round(camera.radius)} m) — pans will look like nothing happens; ` +
            `raise move_limit_m or lower distance_m.start`,
        );
      }
    }
  }
  applyControls(camera, e.controls, panEnabled);
  camera.useNaturalPinchZoom = true;
  // Clip planes. Near defaults to 0.05 m; far is left at Babylon's 10 km default
  // unless set — km-scale scenes MUST author clip_far_m or distant splats cull.
  camera.minZ = e.clip_near_m ?? 0.05;
  if (e.clip_far_m != null) camera.maxZ = e.clip_far_m;
}

/**
 * Author-tunable camera feel (JSON camera.controls; 1/1/1/0.9 = baseline).
 * Babylon sensibilities are inverse ("higher = slower"), hence the divisions.
 * Feature views call this again with their own per-window controls.
 *
 * move_speed multiplies the ground-tracked pan gain (groundPanCamera.ts): at
 * 1.0 a drag moves the terrain ~1:1 with the pointer at any orbit radius.
 * panningSensibility 0 = pan OFF — deliberate whenever the envelope carries
 * no pan_m (object-focus envelopes never do: the camera must not pan off the
 * trained close-up).
 */
export function applyControls(camera: ArcRotateCamera, c: CameraControls, panEnabled: boolean): void {
  camera.angularSensibilityX = 1000 / c.rotate_speed;
  camera.angularSensibilityY = 1000 / c.rotate_speed;
  camera.inertia = c.glide_after_release;
  camera.panningInertia = c.glide_after_release;
  camera.panningSensibility = panEnabled ? PAN_BASE_SENSIBILITY / c.move_speed : 0;
  camera.wheelDeltaPercentage = 0.01 * c.zoom_speed;
  camera.pinchDeltaPercentage = 0.01 * c.zoom_speed;
}

/** True when the camera sits inside its own limits — dev-harness self-test. */
export function withinEnvelope(camera: ArcRotateCamera): boolean {
  const inRange = (v: number, lo: number | null, hi: number | null) =>
    (lo == null || v >= lo - 1e-6) && (hi == null || v <= hi + 1e-6);
  return (
    inRange(camera.radius, camera.lowerRadiusLimit, camera.upperRadiusLimit) &&
    inRange(camera.alpha, camera.lowerAlphaLimit, camera.upperAlphaLimit) &&
    inRange(camera.beta, camera.lowerBetaLimit, camera.upperBetaLimit)
  );
}
