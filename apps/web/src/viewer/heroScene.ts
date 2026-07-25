// Hero splat scene: SOG import + envelope-constrained ArcRotateCamera.
// Splat material settings (compensation=true, kernelSize 0.3) are
// project-validated — see CLAUDE.md "Splat pipeline learnings".

import type { AbstractEngine } from "@babylonjs/core/Engines/abstractEngine";
import { Scene } from "@babylonjs/core/scene";
import type { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import { GroundPanCamera } from "./groundPanCamera";
import { Color4 } from "@babylonjs/core/Maths/math.color";
import { ImportMeshAsync } from "@babylonjs/core/Loading/sceneLoader";
import type { GaussianSplattingMesh } from "@babylonjs/core/Meshes/GaussianSplatting/gaussianSplattingMesh";
import type { GaussianSplattingMaterial } from "@babylonjs/core/Materials/GaussianSplatting/gaussianSplattingMaterial";
// Registers .sog/.splat/.ply/.spz with the scene loader (side-effect import).
import "@babylonjs/loaders/SPLAT/splatFileLoader";
import * as fflate from "fflate";
import type { CameraEnvelope } from "../catalogue/concept";
import { applyEnvelope } from "./cameraEnvelope";
import type { ViewerProgress } from "./types";

export interface HeroScene {
  scene: Scene;
  camera: ArcRotateCamera;
  splat: GaussianSplattingMesh | null;
}

export async function buildHeroScene(
  engine: AbstractEngine,
  sogUrl: string,
  envelope: CameraEnvelope | null,
  useSogTextures: boolean,
  onProgress: (p: ViewerProgress) => void,
): Promise<HeroScene> {
  const scene = new Scene(engine);
  try {
    return await fillHeroScene(scene, sogUrl, envelope, useSogTextures, onProgress);
  } catch (err) {
    // a failed import must not leave a half-built scene registered on the engine
    scene.dispose();
    throw err;
  }
}

async function fillHeroScene(
  scene: Scene,
  sogUrl: string,
  envelope: CameraEnvelope | null,
  useSogTextures: boolean,
  onProgress: (p: ViewerProgress) => void,
): Promise<HeroScene> {
  scene.clearColor = new Color4(0, 0, 0, 1); // splat scenes carry their own baked sky

  // GroundPanCamera = ArcRotateCamera with screen-anchored ground panning
  // (see groundPanCamera.ts for why stock panning fails at km scale)
  const camera = new GroundPanCamera("hero", -Math.PI / 2, 1.1, 9, Vector3.Zero(), scene);
  // Input mapping (deliberate — Babylon 9.16.1 defaults made explicit):
  //   left drag = rotate · right/middle drag or ctrl+left drag = pan (only
  //   when the envelope grants pan_m; applyControls sets panningSensibility 0
  //   otherwise) · wheel/pinch = zoom. noPreventDefault=false: wheel over the
  //   canvas must zoom, not scroll the (scrollable) concept page behind it.
  //   The browser context menu on right-drag is suppressed in loadViewer
  //   (canvas) and hotspots.ts (pin buttons).
  camera.attachControl(false, /* useCtrlForPanning */ true, /* panningMouseButton */ 2);
  // Middle-button (scroll-wheel press) drag also pans, matching the feature
  // overview windows — one consistent control scheme across every splat window.
  // Babylon's default input map leaves button 1 unmapped (it would trigger the
  // browser's middle-click autoscroll instead; that is suppressed on the canvas
  // in loadViewer.ts). Documented cast: `input` is declared on the concrete
  // ArcRotateCameraMovement, not the base CameraMovement type camera.movement
  // is typed as. Deps exact-pinned (@babylonjs/core 9.16.1) — revisit on a bump.
  (camera.movement as unknown as {
    input: { addEntry(e: { source: "pointer"; button: number; interaction: string }): void };
  }).input.addEntry({ source: "pointer", button: 1, interaction: "pan" });
  if (envelope) applyEnvelope(camera, envelope);

  const splat = await importSplatIntoScene(scene, sogUrl, useSogTextures, onProgress);
  onProgress({ phase: "ready" });
  return { scene, camera, splat };
}

/**
 * Import a .sog into an existing scene with the project-pinned loader options
 * (bundled fflate; no-CDN SPZ; file-embedded camera limits ignored) and apply
 * the validated splat material tweaks (compensation, kernelSize). Shared by the
 * hero scene and per-window feature splats so those options never drift.
 */
export async function importSplatIntoScene(
  scene: Scene,
  sogUrl: string,
  useSogTextures: boolean,
  onProgress?: (p: ViewerProgress) => void,
): Promise<GaussianSplattingMesh | null> {
  onProgress?.({ phase: "download", ratio: 0 });
  const result = await ImportMeshAsync(sogUrl, scene, {
    onProgress: (e) => {
      if (!onProgress) return;
      if (e.lengthComputable && e.total > 0) {
        const ratio = e.loaded / e.total;
        onProgress(ratio >= 1 ? { phase: "decode" } : { phase: "download", ratio });
      } else {
        onProgress({ phase: "download" });
      }
    },
    pluginOptions: {
      splat: {
        // bundled fflate — without this the loader fetches it from unpkg.com
        // at runtime (splatFileLoader.pure.ts), breaking self-containment
        fflate,
        // explicit undefined forces the built-in SPZ parser: the loader's
        // DEFAULT is an unpkg.com URL, which would violate the no-CDN rule the
        // moment a concept ships a .spz (V4+/NGSP files then error instead of
        // silently fetching — vendor @adobe/spz locally if we ever need them)
        spzLibraryUrl: undefined,
        useSogTextures,
        // file-embedded camera limits must never override the concept JSON
        disableAutoCameraLimits: true,
      },
    },
  });

  const splat =
    (result.meshes.find((m) => m.getClassName() === "GaussianSplattingMesh") as GaussianSplattingMesh | undefined) ??
    null;
  if (splat?.material) {
    const mat = splat.material as GaussianSplattingMaterial;
    mat.compensation = true;
    mat.kernelSize = 0.3;
  }
  return splat;
}

export interface FeatureSplatScene {
  scene: Scene;
  splat: GaussianSplattingMesh | null;
}

/**
 * A standalone scene holding ONE splat, for an Overview window that shows a
 * different splat than the hero (concept feature `scene_file`). No camera or
 * envelope — the caller adds a feature camera and frames it to the splat's
 * bounds (feature splats can be any scale, unrelated to the hero envelope).
 */
export async function buildFeatureSplatScene(
  engine: AbstractEngine,
  sogUrl: string,
  useSogTextures: boolean,
): Promise<FeatureSplatScene> {
  const scene = new Scene(engine);
  scene.clearColor = new Color4(0, 0, 0, 1);
  try {
    const splat = await importSplatIntoScene(scene, sogUrl, useSogTextures);
    return { scene, splat };
  } catch (err) {
    // a failed import must not leave a half-built scene registered on the engine
    scene.dispose();
    throw err;
  }
}
