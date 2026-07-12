// Engine bootstrap: WebGPU when supported, WebGL2 otherwise. One engine per
// page visit, reused across scene switches; recreated only after WebGPU device
// loss (heroScene/loadViewer drop back to the poster in that case).

import { Engine } from "@babylonjs/core/Engines/engine";
import { WebGPUEngine } from "@babylonjs/core/Engines/webgpuEngine";
import type { AbstractEngine } from "@babylonjs/core/Engines/abstractEngine";
// WebGPU's dynamic-texture support arrives via side-effect module; the SOG
// texture path needs it (see plan Part B / Babylon forum #63761).
import "@babylonjs/core/Engines/AbstractEngine/abstractEngine.texture";
import type { EngineKind, TierProfile } from "./types";

export interface EngineBundle {
  engine: AbstractEngine;
  kind: EngineKind;
  /** Re-applies the DPR cap (call after monitor moves). */
  applyScaling(): void;
  dispose(): void;
}

export async function createEngine(canvas: HTMLCanvasElement, profile: TierProfile): Promise<EngineBundle> {
  const wantWebGPU =
    profile.engineForce !== "webgl2" && (profile.engineForce === "webgpu" || (await WebGPUEngine.IsSupportedAsync));

  let engine: AbstractEngine;
  let kind: EngineKind;
  if (wantWebGPU) {
    const gpu = new WebGPUEngine(canvas, { antialias: true, adaptToDeviceRatio: false });
    await gpu.initAsync();
    engine = gpu;
    kind = "webgpu";
  } else {
    engine = new Engine(canvas, true, { adaptToDeviceRatio: false });
    kind = "webgl2";
  }

  const applyScaling = () => engine.setHardwareScalingLevel(1 / Math.min(devicePixelRatio, profile.dprCap));
  applyScaling();

  // DPR changes (window dragged between monitors, browser zoom) don't fire a
  // content-box ResizeObserver — watch the DPR itself with a re-arming
  // matchMedia listener (the query string is specific to the current DPR).
  let dprWatchStopped = false;
  let mql: MediaQueryList | null = null;
  const onDprChange = () => {
    if (dprWatchStopped) return;
    applyScaling(); // also triggers engine.resize()
    watchDpr();
  };
  const watchDpr = () => {
    mql = matchMedia(`(resolution: ${devicePixelRatio}dppx)`);
    mql.addEventListener("change", onDprChange, { once: true });
  };
  watchDpr();

  const container = canvas.parentElement ?? canvas;
  let resizeQueued = false;
  const ro = new ResizeObserver(() => {
    // coalesce to one resize per frame; mobile URL-bar changes fire in bursts
    if (resizeQueued) return;
    resizeQueued = true;
    requestAnimationFrame(() => {
      resizeQueued = false;
      engine.resize();
    });
  });
  ro.observe(container);

  return {
    engine,
    kind,
    applyScaling,
    dispose() {
      dprWatchStopped = true;
      mql?.removeEventListener("change", onDprChange);
      ro.disconnect();
      engine.dispose();
    },
  };
}
