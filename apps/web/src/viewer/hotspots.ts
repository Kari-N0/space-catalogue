// Hotspots as DOM overlays (no @babylonjs/gui — cheaper on the engine budget,
// and DOM text stays crisp, selectable, and accessible). Projection runs per
// rendered frame; elements are hidden when behind the camera or off-viewport.

import type { Scene } from "@babylonjs/core/scene";
import { Vector3, Matrix } from "@babylonjs/core/Maths/math.vector";
import type { Observer } from "@babylonjs/core/Misc/observable";
import type { Hotspot } from "../catalogue/concept";

export interface HotspotLayer {
  dispose(): void;
}

let hotspotDescSeq = 0; // unique aria-describedby ids across remounts

export function mountHotspots(scene: Scene, layer: HTMLElement, hotspots: Hotspot[]): HotspotLayer {
  const items = hotspots.map((h, i) => {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "viewer-hotspot";
    el.textContent = h.title;
    el.style.position = "absolute";
    el.style.transform = "translate(-50%, -50%)";
    let desc: HTMLElement | null = null;
    if (h.body) {
      el.title = h.body;
      // screen-reader description as a visually-hidden SIBLING (inside the
      // button it would concatenate into the accessible name)
      desc = document.createElement("span");
      desc.id = `viewer-hotspot-desc-${hotspotDescSeq}-${i}`;
      desc.textContent = h.body;
      desc.style.cssText = "position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)";
      el.setAttribute("aria-describedby", desc.id);
      layer.appendChild(desc);
    }
    layer.appendChild(el);
    return { el, desc, pos: new Vector3(h.position_m[0], h.position_m[1], h.position_m[2]) };
  });
  hotspotDescSeq += 1;

  let observer: Observer<Scene> | null = null;
  if (items.length > 0) {
    observer = scene.onAfterRenderObservable.add(() => {
      const engine = scene.getEngine();
      const camera = scene.activeCamera;
      if (!camera) return;
      const w = engine.getRenderWidth();
      const h = engine.getRenderHeight();
      const viewport = camera.viewport.toGlobal(w, h);
      // engine pixels → CSS pixels (hardware scaling level ≠ 1 under DPR caps)
      const cssScaleX = layer.clientWidth / w;
      const cssScaleY = layer.clientHeight / h;
      for (const item of items) {
        const p = Vector3.Project(item.pos, Matrix.IdentityReadOnly, scene.getTransformMatrix(), viewport);
        const visible = p.z > 0 && p.z < 1 && p.x >= 0 && p.x <= w && p.y >= 0 && p.y <= h;
        item.el.style.display = visible ? "" : "none";
        if (visible) {
          item.el.style.left = `${p.x * cssScaleX}px`;
          item.el.style.top = `${p.y * cssScaleY}px`;
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
