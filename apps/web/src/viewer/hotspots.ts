// Hotspots as DOM overlays (no @babylonjs/gui — cheaper on the engine budget,
// and DOM text stays crisp, selectable, and accessible). Projection runs per
// rendered frame; elements are hidden when behind the camera or off-viewport.
//
// DOM contract per hotspot (pages style these classes with brand tokens):
//   button.viewer-hotspot            — positioned pin, click => onSelect(h)
//     span.viewer-hotspot__pin       — the visual marker
//     span.viewer-hotspot__label     — title, revealed on hover/focus by CSS
//   span.viewer-hotspot__desc        — visually-hidden sibling, aria-describedby

import type { Scene } from "@babylonjs/core/scene";
import type { Camera } from "@babylonjs/core/Cameras/camera";
import { Vector3, Matrix } from "@babylonjs/core/Maths/math.vector";
import type { Observer } from "@babylonjs/core/Misc/observable";
import type { Hotspot } from "../catalogue/concept";

export interface HotspotLayer {
  dispose(): void;
}

let hotspotDescSeq = 0; // unique aria-describedby ids across remounts

export function mountHotspots(
  scene: Scene,
  // explicit camera: with multi-view rendering, scene.getTransformMatrix()
  // reflects whichever view rendered last — pins must track the MAIN camera
  camera: Camera,
  layer: HTMLElement,
  hotspots: Hotspot[],
  onSelect?: (h: Hotspot) => void,
): HotspotLayer {
  const items = hotspots.map((h, i) => {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "viewer-hotspot";
    el.style.position = "absolute";
    el.style.transform = "translate(-50%, -50%)";

    const pin = document.createElement("span");
    pin.className = "viewer-hotspot__pin";
    pin.setAttribute("aria-hidden", "true");
    el.appendChild(pin);

    const label = document.createElement("span");
    label.className = "viewer-hotspot__label";
    label.textContent = h.title;
    el.appendChild(label);

    let desc: HTMLElement | null = null;
    if (h.body) {
      el.title = h.body;
      // screen-reader description as a visually-hidden SIBLING (inside the
      // button it would concatenate into the accessible name)
      desc = document.createElement("span");
      desc.className = "viewer-hotspot__desc";
      desc.id = `viewer-hotspot-desc-${hotspotDescSeq}-${i}`;
      desc.textContent = h.body;
      desc.style.cssText = "position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)";
      el.setAttribute("aria-describedby", desc.id);
      layer.appendChild(desc);
    }
    if (onSelect) el.addEventListener("click", () => onSelect(h));
    // the 24px pin is the one DOM element allowed to capture pointer input
    // over the canvas — a right-press on it must still not open the browser
    // menu (the canvas suppresses it too, loadViewer.ts)
    el.addEventListener("contextmenu", (e) => e.preventDefault());
    layer.appendChild(el);
    return { el, desc, pos: new Vector3(h.position_m[0], h.position_m[1], h.position_m[2]) };
  });
  hotspotDescSeq += 1;

  let observer: Observer<Scene> | null = null;
  if (items.length > 0) {
    observer = scene.onAfterRenderObservable.add(() => {
      // multi-canvas views render this scene once per enabled view, and the
      // views extension swaps scene.activeCamera to the view's camera for its
      // pass (abstractEngine.views: _renderViewStep) while the shared working
      // canvas is resized to THAT view — so during a feature-view pass the
      // main camera's projection matrix recomputes at the wrong aspect ratio.
      // Only the pass rendered with the tracked camera may write pin positions.
      if (scene.activeCamera !== camera) return;
      // project straight into CSS pixel space (layer size) — engine render
      // size varies per view when multi-canvas views are active, and hardware
      // scaling diverges from CSS pixels under DPR caps
      const cw = layer.clientWidth;
      const ch = layer.clientHeight;
      if (cw === 0 || ch === 0) return;
      const viewport = camera.viewport.toGlobal(cw, ch);
      const transform = camera.getViewMatrix().multiply(camera.getProjectionMatrix());
      for (const item of items) {
        const p = Vector3.Project(item.pos, Matrix.IdentityReadOnly, transform, viewport);
        const visible = p.z > 0 && p.z < 1 && p.x >= 0 && p.x <= cw && p.y >= 0 && p.y <= ch;
        item.el.style.display = visible ? "" : "none";
        if (visible) {
          item.el.style.left = `${p.x}px`;
          item.el.style.top = `${p.y}px`;
        }
      }
    });
  }

  return {
    dispose() {
      if (observer) scene.onAfterRenderObservable.remove(observer);
      for (const { el, desc } of items) {
        el.remove();
        desc?.remove();
      }
    },
  };
}
