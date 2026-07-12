// M1 dev harness (unlinked route /dev/viewer.html). Proves the lazy boundary:
// this module imports catalogue/ and viewer types only — the Babylon chunks
// load exclusively through the dynamic import() in enter3d().

import { loadConcept } from "../catalogue/concept";
import { pickTier } from "../viewer/tiering";
import type { ViewerHandle } from "../viewer/types";

const canvas = document.getElementById("view") as HTMLCanvasElement;
const overlay = document.getElementById("overlay") as HTMLElement;
const enter = document.getElementById("enter") as HTMLButtonElement;
const status = document.getElementById("status") as HTMLParagraphElement;

let handle: ViewerHandle | null = null;

async function enter3d(): Promise<void> {
  enter.disabled = true;
  status.textContent = "loading concept…";
  try {
    const search = new URLSearchParams(location.search);
    const conceptId = search.get("concept") ?? "lunar-base";
    const concept = await loadConcept(`${import.meta.env.BASE_URL}content/concepts/${conceptId}.json`);
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
            ? `downloading splat… ${(p.ratio * 100).toFixed(0)}%`
            : p.phase === "ready"
              ? ""
              : `${p.phase}…`;
      },
      onModeChange: (m) => console.info(`[harness] mode: ${m}`),
    });
    enter.remove();
    console.info(`[harness] engine=${handle.engineKind} tier=${profile.tier}`);
  } catch (err) {
    status.textContent = String(err);
    enter.disabled = false;
    throw err;
  }
}

enter.addEventListener("click", () => void enter3d());

// exposed for devtools-driven checks (leak test, envelope assertions)
declare global {
  interface Window {
    __viewerHandle: () => ViewerHandle | null;
  }
}
window.__viewerHandle = () => handle;
