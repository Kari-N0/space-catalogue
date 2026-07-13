// Inspect mode — second dynamic-import boundary (chunk "babylon-inspect").
// Loaded only when the concept JSON provides inspect_glb; everything KTX2/
// meshopt stays dormant until then (plan risk R7: verified with Kari's first
// real .glb drop).

import type { AbstractEngine } from "@babylonjs/core/Engines/abstractEngine";
import { Scene } from "@babylonjs/core/scene";
import { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import { Color4 } from "@babylonjs/core/Maths/math.color";
import { ImportMeshAsync } from "@babylonjs/core/Loading/sceneLoader";
import { KhronosTextureContainer2 } from "@babylonjs/core/Misc/khronosTextureContainer2";
import { MeshoptCompression } from "@babylonjs/core/Meshes/Compression/meshoptCompression";
// glTF 2.0 loader registration (side-effect import; glTF1 deliberately excluded)
import "@babylonjs/loaders/glTF/2.0";
import type { ConceptDoc, Hotspot } from "../catalogue/concept";
import { assetUrl } from "../catalogue/concept";
import { applyIbl } from "./lighting";
import { mountHotspots, type HotspotLayer } from "./hotspots";
import type { ViewerProgress } from "./types";

let decodersConfigured = false;

/** Point Babylon's KTX2/meshopt workers at our vendored copies (never a CDN). */
function configureDecoders(): void {
  if (decodersConfigured) return;
  decodersConfigured = true;
  const v = (f: string) => new URL(`${import.meta.env.BASE_URL}vendor/babylon/${f}`, document.baseURI).href;
  MeshoptCompression.Configuration.decoder = { url: v("meshopt_decoder.js") };
  KhronosTextureContainer2.URLConfig = {
    jsDecoderModule: v("babylon.ktx2Decoder.js"),
    wasmUASTCToASTC: v("uastc_astc.wasm"),
    wasmUASTCToBC7: v("uastc_bc7.wasm"),
    wasmUASTCToRGBA_UNORM: v("uastc_rgba8_unorm_v2.wasm"),
    wasmUASTCToRGBA_SRGB: v("uastc_rgba8_srgb_v2.wasm"),
    wasmUASTCToR8_UNORM: v("uastc_r8_unorm.wasm"),
    wasmUASTCToRG8_UNORM: v("uastc_rg8_unorm.wasm"),
    jsMSCTranscoder: v("msc_basis_transcoder.js"),
    wasmMSCTranscoder: v("msc_basis_transcoder.wasm"),
    wasmZSTDDecoder: v("zstddec.wasm"),
  };
}

export interface InspectScene {
  scene: Scene;
  camera: ArcRotateCamera;
  hotspots: HotspotLayer | null;
}

export async function buildInspectScene(
  engine: AbstractEngine,
  concept: ConceptDoc,
  hotspotLayer: HTMLElement | null,
  onProgress: (p: ViewerProgress) => void,
  onHotspotSelect?: (h: Hotspot) => void,
): Promise<InspectScene> {
  const glbPath = concept.assets.inspect_glb;
  if (!glbPath) throw new Error("concept has no inspect_glb");
  configureDecoders();

  const scene = new Scene(engine);
  try {
    return await fillInspectScene(scene, concept, glbPath, hotspotLayer, onProgress, onHotspotSelect);
  } catch (err) {
    // a failed import must not leave a half-built scene registered on the engine
    scene.dispose();
    throw err;
  }
}

async function fillInspectScene(
  scene: Scene,
  concept: ConceptDoc,
  glbPath: string,
  hotspotLayer: HTMLElement | null,
  onProgress: (p: ViewerProgress) => void,
  onHotspotSelect?: (h: Hotspot) => void,
): Promise<InspectScene> {
  scene.clearColor = new Color4(0.012, 0.012, 0.016, 1);

  // free orbit — inspect mode is real geometry, not a trained envelope
  const camera = new ArcRotateCamera("inspect", -Math.PI / 2, Math.PI / 3, 6, Vector3.Zero(), scene);
  // no-arg attachControl => preventDefault (see heroScene.ts)
  camera.attachControl();
  camera.lowerRadiusLimit = 0.5;
  camera.upperRadiusLimit = 50;
  camera.minZ = 0.05;
  camera.wheelDeltaPercentage = 0.01;
  camera.pinchDeltaPercentage = 0.01;

  applyIbl(scene, concept.assets.env ? assetUrl(concept.assets.env) : null);

  onProgress({ phase: "download", ratio: 0 });
  await ImportMeshAsync(assetUrl(glbPath), scene, {
    onProgress: (e) => {
      if (e.lengthComputable && e.total > 0) onProgress({ phase: "download", ratio: e.loaded / e.total });
    },
  });
  onProgress({ phase: "ready" });

  const hotspots =
    hotspotLayer && concept.hotspots.length > 0
      ? mountHotspots(scene, camera, hotspotLayer, concept.hotspots as Hotspot[], onHotspotSelect)
      : null;

  return { scene, camera, hotspots };
}
