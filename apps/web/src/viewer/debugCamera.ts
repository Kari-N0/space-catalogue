// Camera debug overlay, mounted only behind the ?debug=camera URL flag
// (permanent QA tool, companion to ?debug=hotspots). Shows, live:
//   - camera pose (alpha/beta/radius/fov) and target,
//   - pan distance from the envelope origin vs. the authored move_limit_m,
//   - the applied Babylon control values (panningSensibility etc.),
//   - the values LOADED from the concept JSON camera block,
// so a stale, clamped, or ignored config edit is visible in two seconds
// (unrecognized-key warnings from the parser land in the console alongside).
// DOM-only: Babylon types are imported type-only, keeping this chunk
// engine-free.

import type { Scene } from "@babylonjs/core/scene";
import type { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera";
import type { CameraEnvelope } from "../catalogue/concept";

export function mountCameraDebug(
  scene: Scene,
  camera: ArcRotateCamera,
  env: CameraEnvelope | null,
  parent: HTMLElement,
): void {
  const el = document.createElement("pre");
  el.className = "viewer-camera-debug";
  el.style.cssText =
    "position:absolute;top:8px;left:8px;z-index:30;margin:0;padding:8px 10px;" +
    "font:11px/1.6 ui-monospace,monospace;color:#fff;background:rgba(0,0,0,.65);" +
    "border-radius:4px;pointer-events:none;white-space:pre";
  parent.appendChild(el);

  const deg = (r: number | null | undefined) => (r == null ? "—" : ((r * 180) / Math.PI).toFixed(1));
  const num = (n: number | null | undefined, d = 1) => (n == null ? "—" : n.toFixed(d));
  const render = () => {
    const o = camera.panningOriginTarget;
    const panDist = Math.hypot(camera.target.x - o.x, camera.target.z - o.z);
    const limit = camera.panningDistanceLimit;
    const t = camera.target;
    el.textContent = [
      `cam     α ${deg(camera.alpha)}°  β ${deg(camera.beta)}°  r ${num(camera.radius)} m  fov ${deg(camera.fov)}°`,
      `target  (${num(t.x)}, ${num(t.y)}, ${num(t.z)})  pan ${num(panDist)}${limit ? ` / ${limit} m` : " m (no limit)"}`,
      `limits  r ${num(camera.lowerRadiusLimit)}–${num(camera.upperRadiusLimit)} m` +
        `  β ${deg(camera.lowerBetaLimit)}–${deg(camera.upperBetaLimit)}°` +
        `  α ${camera.lowerAlphaLimit == null && camera.upperAlphaLimit == null ? "free" : `${deg(camera.lowerAlphaLimit)}–${deg(camera.upperAlphaLimit)}°`}`,
      `applied panSens ${num(camera.panningSensibility, 0)}${camera.panningSensibility === 0 ? " (pan OFF)" : ""}` +
        `  rotSens ${num(camera.angularSensibilityX, 0)}  wheelΔ ${num((camera.wheelDeltaPercentage ?? 0) * 100)}%  glide ${num(camera.inertia, 2)}`,
      env
        ? `json    move_limit_m ${env.pan_m ? env.pan_m.max_from_center : "0/absent → pan disabled"}` +
          `  move ${env.controls.move_speed}  rotate ${env.controls.rotate_speed}` +
          `  zoom ${env.controls.zoom_speed}  glide ${env.controls.glide_after_release}`
        : "json    no camera block — built-in defaults",
    ].join("\n");
  };
  render();
  const iv = setInterval(render, 250);
  scene.onDisposeObservable.add(() => {
    clearInterval(iv);
    el.remove();
  });
}
