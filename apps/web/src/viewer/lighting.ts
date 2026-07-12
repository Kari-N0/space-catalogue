// Inspect-scene lighting: prefiltered .env IBL when the concept provides one;
// otherwise a zero-asset neutral rig (placeholder rule: never fetch media the
// concept JSON does not name).

import type { Scene } from "@babylonjs/core/scene";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import { Color3 } from "@babylonjs/core/Maths/math.color";
import { HemisphericLight } from "@babylonjs/core/Lights/hemisphericLight";
import { DirectionalLight } from "@babylonjs/core/Lights/directionalLight";
import { CubeTexture } from "@babylonjs/core/Materials/Textures/cubeTexture";
// .env loader registration (side-effect import)
import "@babylonjs/core/Materials/Textures/Loaders/envTextureLoader";

export function applyIbl(scene: Scene, envUrl: string | null): void {
  if (envUrl) {
    scene.environmentTexture = CubeTexture.CreateFromPrefilteredData(envUrl, scene);
    scene.imageProcessingConfiguration.toneMappingEnabled = true;
    return;
  }
  const hemi = new HemisphericLight("neutral-sky", new Vector3(0, 1, 0), scene);
  hemi.intensity = 0.9;
  hemi.groundColor = new Color3(0.12, 0.11, 0.1);
  const key = new DirectionalLight("neutral-key", new Vector3(-0.6, -0.8, 0.4), scene);
  key.intensity = 1.5;
  scene.imageProcessingConfiguration.toneMappingEnabled = true;
}
