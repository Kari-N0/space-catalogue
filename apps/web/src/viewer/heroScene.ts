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
  //   left/middle drag = rotate · right drag or ctrl+left drag = pan (only
  //   when the envelope grants pan_m; applyControls sets panningSensibility 0
  //   otherwise) · wheel/pinch = zoom. noPreventDefault=false: wheel over the
  //   canvas must zoom, not scroll the (scrollable) concept page behind it.
  //   The browser context menu on right-drag is suppressed in loadViewer
  //   (canvas) and hotspots.ts (pin buttons).
  camera.attachControl(false, /* useCtrlForPanning */ true, /* panningMouseButton */ 2);
  if (envelope) applyEnvelope(camera, envelope);

  onProgress({ phase: "download", ratio: 0 });
  const result = await ImportMeshAsync(sogUrl, scene, {
    onProgress: (e) => {
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

  onProgress({ phase: "ready" });
  return { scene, camera, splat };
}
