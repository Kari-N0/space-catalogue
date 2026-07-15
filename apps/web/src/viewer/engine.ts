// Engine bootstrap: WebGPU when supported, WebGL2 otherwise. One engine per
// page visit, reused across scene switches; recreated only after WebGPU device
// loss (heroScene/loadViewer drop back to the poster in that case).
//
// Multi-canvas model (Babylon views): the engine renders into a HIDDEN working
// canvas and every on-page canvas — the main display canvas and any feature
// views — is a registered view the frame is blitted into. This is Babylon's
// documented multi-canvas architecture; with views active the engine skips the
// main-frame render entirely, so the display canvas MUST be a view too.

import { Engine } from "@babylonjs/core/Engines/engine";
import { WebGPUEngine } from "@babylonjs/core/Engines/webgpuEngine";
import type { AbstractEngine } from "@babylonjs/core/Engines/abstractEngine";
// WebGPU's dynamic-texture support arrives via side-effect module; the SOG
// texture path needs it (see plan Part B / Babylon forum #63761).
import "@babylonjs/core/Engines/AbstractEngine/abstractEngine.texture";
// installs registerView/unRegisterView/_renderViews on AbstractEngine — the
// pure module exports the installer WITHOUT calling it (tree-shaken builds
// never run the engine-registration side effects that would)
import { RegisterAbstractEngineViews } from "@babylonjs/core/Engines/AbstractEngine/abstractEngine.views.pure";
import type { EngineKind, TierProfile } from "./types";

export interface EngineBundle {
  engine: AbstractEngine;
  kind: EngineKind;
  /** Re-applies the DPR cap (call after monitor moves). */
  applyScaling(): void;
  dispose(): void;
}

export async function createEngine(canvas: HTMLCanvasElement, profile: TierProfile): Promise<EngineBundle> {
  RegisterAbstractEngineViews();

  // WebGPU is opt-in (?engine=webgpu) — WebGL2 is the default. On the WebGPU
  // path the GaussianSplatting material's WGSL shaders are fetched at runtime
  // and 404 to the SPA fallback HTML, so Tint parses "<!doctype html>" as a
  // shader, the pipeline is invalid, and the splat renders black (Chrome/Edge
  // default to WebGPU, so this hit every such visitor). WebGL2's GLSL shaders
  // bundle correctly and render the splat perfectly. Revisit if the WGSL
  // shader-bundling is fixed and verified end-to-end on a real WebGPU adapter.
  const wantWebGPU = profile.engineForce === "webgpu";

  // hidden working canvas — never in the DOM; views size it per frame
  const workingCanvas = document.createElement("canvas");

  let engine: AbstractEngine;
  let kind: EngineKind;
  if (wantWebGPU) {
    const gpu = new WebGPUEngine(workingCanvas, { antialias: true, adaptToDeviceRatio: false });
    await gpu.initAsync();
    engine = gpu;
    kind = "webgpu";
  } else {
    engine = new Engine(workingCanvas, true, { adaptToDeviceRatio: false });
    kind = "webgl2";
  }

  // camera inputs bind to inputElement; leaving it on the display canvas makes
  // every default attachControl() target the right element
  engine.inputElement = canvas;
  // the display canvas is view #0 (no explicit camera: renders the scene's
  // active camera, which survives hero⇄inspect swaps)
  engine.registerView(canvas);

  const applyScaling = () => engine.setHardwareScalingLevel(1 / Math.min(devicePixelRatio, profile.dprCap));
  applyScaling();

  // DPR changes (window dragged between monitors, browser zoom) don't fire a
  // content-box ResizeObserver — watch the DPR itself with a re-arming
  // matchMedia listener (the query string is specific to the current DPR).
  let dprWatchStopped = false;
  let mql: MediaQueryList | null = null;
  const onDprChange = () => {
    if (dprWatchStopped) return;
    applyScaling(); // view sizing picks the new level up next frame
    watchDpr();
  };
  const watchDpr = () => {
    mql = matchMedia(`(resolution: ${devicePixelRatio}dppx)`);
    mql.addEventListener("change", onDprChange, { once: true });
  };
  watchDpr();

  // view sizing is per-frame (clientWidth-driven), so no explicit resize()
  // call is needed for views — but a resize kick keeps anything cached fresh
  const container = canvas.parentElement ?? canvas;
  let resizeQueued = false;
  const ro = new ResizeObserver(() => {
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
      engine.unRegisterView(canvas);
      engine.dispose();
    },
  };
}
