// Screen-anchored ground panning for km-scale splat scenes.
//
// Babylon 9.16.1's stock pan application (_applyPanDelta) has three flaws for
// this catalogue's use, all verified live + in source (2026-07-24):
//   1. gain is a fixed pixel ratio (panningSensibility) that ignores orbit
//      radius — a 150 px drag moved the target 4 m under a 3.5 km hero
//      framing (invisible), and the same setting is twitchy up close;
//   2. with panningAxis (1,0,1) the vertical drag input rides the VIEW axis
//      ((panX, panY, panY) into the axis mask), whose ground projection
//      collapses as sin(beta) — pans go dead near top-down (measured 0.21×
//      at beta 12°);
//   3. a pan step whose endpoint would leave panningDistanceLimit is
//      discarded wholesale — the pan dead-stops at the envelope boundary
//      instead of sliding along it.
//
// This subclass replaces the pan application only; input collection, button
// mapping, inertia and the rest of ArcRotateCamera stay stock:
//   - normalized ground axes: full pan authority at any beta, directions
//     matching stock (panX along camera-right, panY along view-over-ground);
//   - gain proportional to the visible ground per screen pixel at the target
//     depth, so a drag tracks the terrain ~1:1 at any radius, times the
//     authored controls.move_speed;
//   - XZ slide-clamp against panningOriginTarget/panningDistanceLimit: the
//     radial component stops at the boundary, the tangential component keeps
//     moving. target.y is never touched (ground-plane pan).
//
// _applyPanDelta is declared private upstream, so the override is installed
// on the prototype behind one documented cast. Deps are exact-pinned
// (@babylonjs/core 9.16.1, web workstream rules) — revisit this file on any
// Babylon bump. Assumes no camera parent/targetHost (true for hero and
// feature cameras).

import { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import { PAN_BASE_SENSIBILITY } from "./cameraEnvelope";

export class GroundPanCamera extends ArcRotateCamera {}

const tmpRight = new Vector3();
const tmpFwd = new Vector3();

(GroundPanCamera.prototype as unknown as { _applyPanDelta(panX: number, panY: number): void })._applyPanDelta =
  function (this: GroundPanCamera, panX: number, panY: number): void {
    this.getDirectionToRef(Vector3.RightReadOnly, tmpRight);
    this.getDirectionToRef(Vector3.LeftHandedForwardReadOnly, tmpFwd);
    tmpRight.y = 0;
    tmpFwd.y = 0;
    if (tmpFwd.lengthSquared() < 1e-10) {
      // camera looking straight down: the view axis has no ground projection,
      // but "screen-up over the ground" is exactly minus the up axis' one
      this.getDirectionToRef(Vector3.UpReadOnly, tmpFwd);
      tmpFwd.set(-tmpFwd.x, 0, -tmpFwd.z);
    }
    tmpRight.normalize();
    tmpFwd.normalize();

    // panX/panY arrive as dragged-pixels / panningSensibility, where
    // applyControls sets panningSensibility = PAN_BASE_SENSIBILITY/move_speed
    // — multiplying by PAN_BASE_SENSIBILITY recovers px·move_speed. The
    // (1 - panningInertia) factor cancels the inertial decay series
    // (Σ i^n = 1/(1-i)), so the TOTAL ground distance of a drag is
    // px · worldPerPixel · move_speed regardless of glide_after_release.
    const engine = this.getEngine();
    const viewHeightCss = engine.getRenderHeight() * engine.getHardwareScalingLevel() || 1;
    const worldPerPixel = (2 * this.radius * Math.tan(this.fov / 2)) / viewHeightCss;
    const gain = PAN_BASE_SENSIBILITY * (1 - this.panningInertia) * worldPerPixel;

    let nx = this.target.x + (tmpRight.x * panX + tmpFwd.x * panY) * gain;
    let nz = this.target.z + (tmpRight.z * panX + tmpFwd.z * panY) * gain;

    // envelope boundary: clamp radially, keep the tangential component (slide)
    const limit = this.panningDistanceLimit;
    if (limit) {
      const o = this.panningOriginTarget;
      const ex = nx - o.x;
      const ez = nz - o.z;
      const d = Math.hypot(ex, ez);
      if (d > limit) {
        const s = limit / d;
        nx = o.x + ex * s;
        nz = o.z + ez * s;
      }
    }
    this.target.x = nx;
    this.target.z = nz;
  };
