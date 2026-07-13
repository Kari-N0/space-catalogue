// Mockup C2 page script (iteration 2, Kari 2026-07-13): the viewer AUTO-LOADS
// after the page load event (concept-page behavior — the landing/grid route
// still never touches Babylon). Adds fullscreen toggle, hotspot popup with
// image, and four live feature views sharing the hero engine + scene.

import { loadConcept, assetUrl, type Hotspot } from "../catalogue/concept";
import { pickTier } from "../viewer/tiering";
import type { FeatureViewHandle, ViewerHandle } from "../viewer/types";

const stage = document.getElementById("stage") as HTMLElement;
const canvas = document.getElementById("view") as HTMLCanvasElement;
const overlay = document.getElementById("overlay") as HTMLElement;
const poster = document.getElementById("stage-poster") as HTMLElement;
const status = document.getElementById("stage-status") as HTMLElement;
const fsBtn = document.getElementById("stage-fs") as HTMLButtonElement;
const popup = document.getElementById("hotspot-popup") as HTMLElement;
const popupImage = document.getElementById("popup-image") as HTMLImageElement;
const popupTitle = document.getElementById("popup-title") as HTMLElement;
const popupBody = document.getElementById("popup-body") as HTMLElement;
const popupClose = document.getElementById("popup-close") as HTMLButtonElement;

let handle: ViewerHandle | null = null;
let lastPin: HTMLElement | null = null;

/* -- hotspot popup (image + title + body) -------------------------------- */

function openPopup(h: Hotspot): void {
  lastPin = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  if (h.image) {
    popupImage.src = assetUrl(h.image);
    popupImage.alt = h.title;
    popupImage.hidden = false;
  } else {
    popupImage.hidden = true;
    popupImage.removeAttribute("src");
  }
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

/* -- fullscreen toggle ----------------------------------------------------- */

if (stage.requestFullscreen) {
  fsBtn.hidden = false;
  fsBtn.addEventListener("click", () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void stage.requestFullscreen();
  });
  document.addEventListener("fullscreenchange", () => {
    fsBtn.textContent = document.fullscreenElement ? "Exit Fullscreen" : "Fullscreen";
  });
}

/* -- viewer bootstrap (auto-load after page load) --------------------------- */

async function init3d(): Promise<void> {
  try {
    const search = new URLSearchParams(location.search);
    const concept = await loadConcept(`${import.meta.env.BASE_URL}content/concepts/lunar-base.json`);
    const profile = pickTier(search);

    // the lazy boundary — the first Babylon bytes cross the network here
    const { loadViewer } = await import("../viewer/loadViewer");
    handle = await loadViewer({
      canvas,
      hotspotLayer: overlay,
      concept,
      profile,
      onProgress: (p) => {
        status.textContent =
          p.phase === "download" && p.ratio != null
            ? `loading scene… ${(p.ratio * 100).toFixed(0)}%`
            : p.phase === "ready"
              ? ""
              : `${p.phase}…`;
      },
      onHotspotSelect: openPopup,
    });
    poster.remove();
    attachFeatureViews(handle);
  } catch (err) {
    status.textContent = "could not load the 3D scene";
    console.error(err);
  }
}

/* -- live feature views (shared engine/scene, no pins, panning enabled) ----- */

function attachFeatureViews(h: ViewerHandle): void {
  const canvases = [...document.querySelectorAll<HTMLCanvasElement>(".feature-canvas")];
  const angles = [35, -50, 150, -120]; // sample framing variety per row
  const views = new Map<HTMLCanvasElement, FeatureViewHandle>();
  for (const [i, c] of canvases.entries()) {
    try {
      views.set(c, h.attachFeatureView(c, { alphaOffsetDeg: angles[i] ?? 0 }));
    } catch (err) {
      console.error("feature view failed", err);
    }
  }
  // render only the views near the viewport
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) views.get(e.target as HTMLCanvasElement)?.setEnabled(e.isIntersecting);
    },
    { rootMargin: "120px" },
  );
  for (const c of views.keys()) io.observe(c);
}

const start = () => setTimeout(() => void init3d(), 0);
if (document.readyState === "complete") start();
else addEventListener("load", start, { once: true });

addEventListener("pagehide", () => handle?.dispose());

// exposed for scripted verification
declare global {
  interface Window {
    __viewerHandle: () => ViewerHandle | null;
  }
}
window.__viewerHandle = () => handle;
