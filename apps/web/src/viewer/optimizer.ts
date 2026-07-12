// SceneOptimizer wiring: degrade rendering resolution *from the tier baseline*
// toward the fps target, never from 1.0 — the tier's DPR cap is the starting
// point (loadViewer resets scaling at every scene swap).

import type { Scene } from "@babylonjs/core/scene";
import {
  SceneOptimizer,
  SceneOptimizerOptions,
  HardwareScalingOptimization,
  TextureOptimization,
} from "@babylonjs/core/Misc/sceneOptimizer";
import type { TierProfile } from "./types";

export interface OptimizerHandle {
  stop(): void;
}

export function startOptimizer(scene: Scene, profile: TierProfile, inspect: boolean): OptimizerHandle {
  // check against ~90% of the target: an exact 60-check on a 60 Hz vsynced
  // display reads ordinary dips as sustained misses, and degrade-only mode
  // never recovers once it has scaled down
  const checkFps = Math.round(profile.targetFps * 0.9);
  const options = new SceneOptimizerOptions(checkFps, 2000);
  const baseline = 1 / Math.min(devicePixelRatio, profile.dprCap);
  // priority 0: degrade resolution up to 2× the tier baseline, in 0.25 steps
  options.optimizations.push(new HardwareScalingOptimization(0, baseline * 2, 0.25));
  if (inspect) options.optimizations.push(new TextureOptimization(1, 512));
  const optimizer = new SceneOptimizer(scene, options);

  // let shader warm-up / first-frame jank settle before measuring
  const warmup = setTimeout(() => {
    if (!scene.isDisposed) optimizer.start();
  }, 3000);

  return {
    stop() {
      clearTimeout(warmup);
      optimizer.stop();
    },
  };
}
