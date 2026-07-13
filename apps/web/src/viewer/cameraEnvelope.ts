// Envelope JSON → ArcRotateCamera limits. Degrees in JSON (Blender/authoring
// friendly), radians here. This mapping must stay the single place envelope
// semantics live — M2's export_dataset.py consumes the same JSON block.

import type { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import type { CameraEnvelope } from "../catalogue/concept";

const rad = (deg: number) => (deg * Math.PI) / 180;

export function applyEnvelope(camera: ArcRotateCamera, e: CameraEnvelope): void {
  camera.setTarget(new Vector3(e.target_m[0], e.target_m[1], e.target_m[2]));
  camera.fov = rad(e.fov_deg);

  camera.lowerRadiusLimit = e.radius_m.min;
  camera.upperRadiusLimit = e.radius_m.max;
  if (e.radius_m.default != null) camera.radius = e.radius_m.default;

  camera.lowerAlphaLimit = e.alpha_deg.min == null ? null : rad(e.alpha_deg.min);
  camera.upperAlphaLimit = e.alpha_deg.max == null ? null : rad(e.alpha_deg.max);
  camera.lowerBetaLimit = e.beta_deg.min == null ? 0.01 : rad(e.beta_deg.min);
  camera.upperBetaLimit = e.beta_deg.max == null ? Math.PI - 0.01 : rad(e.beta_deg.max);

  // Panning moves the target and can walk the camera out of the trained
  // envelope. When the envelope allows it (pan_m), constrain it to the ground
  // plane and clamp the target's distance from the scene center; otherwise off.
  if (e.pan_m && e.pan_m.max_from_center > 0) {
    camera.panningSensibility = 350; // right-drag / two-finger pan
    camera.panningAxis = new Vector3(1, 0, 1); // ground plane only
    camera.panningOriginTarget = new Vector3(e.target_m[0], e.target_m[1], e.target_m[2]);
    camera.panningDistanceLimit = e.pan_m.max_from_center;
  } else {
    camera.panningSensibility = 0;
  }
  camera.useNaturalPinchZoom = true;
  camera.wheelDeltaPercentage = 0.01;
  camera.pinchDeltaPercentage = 0.01;
  camera.minZ = 0.05;
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
