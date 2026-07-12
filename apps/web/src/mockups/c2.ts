// Mockup C2 page script: wires the REAL M1 viewer into the "Live View"
// section. Babylon stays behind the dynamic import() until the user taps
// Enter 3D (lazy-boundary rule); hotspot pins open the popup card.

import { loadConcept, type Hotspot } from "../catalogue/concept";
import { pickTier } from "../viewer/tiering";
import type { ViewerHandle } from "../viewer/types";

const canvas = document.getElementById("view") as HTMLCanvasElement;
const overlay = document.getElementById("overlay") as HTMLElement;
const gate = document.getElementById("stage-gate") as HTMLElement;
const poster = document.getElementById("stage-poster") as HTMLElement;
const enter = document.getElementById("enter") as HTMLButtonElement;
const status = document.getElementById("stage-status") as HTMLElement;
const popup = document.getElementById("hotspot-popup") as HTMLElement;
const popupTitle = document.getElementById("popup-title") as HTMLElement;
const popupBody = document.getElementById("popup-body") as HTMLElement;
const popupClose = document.getElementById("popup-close") as HTMLButtonElement;

let handle: ViewerHandle | null = null;
let lastPin: HTMLElement | null = null;

function openPopup(h: Hotspot): void {
  lastPin = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  popupTitle.textContent = h.title;
  popupBody.textContent = h.body;
  popup.setAttribute("data-open", "");
  popupClose.focus();
}

function closePopup(): void {
  popup.removeAttribute("data-open");
  lastPin?.focus();
  lastPin = null;
}

popupClose.addEventListener("click", closePopup);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && popup.hasAttribute("data-open")) closePopup();
});

async function enter3d(): Promise<void> {
  enter.disabled = true;
  status.textContent = "loading…";
  try {
    const search = new URLSearchParams(location.search);
    const concept = await loadConcept(`${import.meta.env.BASE_URL}content/concepts/lunar-base.json`);
    const profile = pickTier(search);

    // THE lazy boundary — the first Babylon bytes cross the network here
    const { loadViewer } = await import("../viewer/loadViewer");
    handle = await loadViewer({
      canvas,
      hotspotLayer: overlay,
      concept,
      profile,
      onProgress: (p) => {
        status.textContent =
          p.phase === "download" && p.ratio != null
            ? `downloading scene… ${(p.ratio * 100).toFixed(0)}%`
            : p.phase === "ready"
              ? ""
              : `${p.phase}…`;
      },
      onHotspotSelect: openPopup,
    });
    gate.remove();
    poster.remove();
  } catch (err) {
    status.textContent = "could not load the 3D scene";
    enter.disabled = false;
    console.error(err);
  }
}

enter.addEventListener("click", () => void enter3d());
addEventListener("pagehide", () => handle?.dispose());
