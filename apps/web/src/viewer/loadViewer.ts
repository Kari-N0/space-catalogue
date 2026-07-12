// Sole public entry of the viewer (the lazy boundary — landing code reaches
// this module ONLY via dynamic import()). Owns the hero⇄inspect state machine,
// engine lifetime, optimizer, HUD, and disposal.

import type { Scene } from "@babylonjs/core/scene";
import { createEngine, type EngineBundle } from "./engine";
import { buildHeroScene } from "./heroScene";
import { mountHotspots, type HotspotLayer } from "./hotspots";
import { startOptimizer, type OptimizerHandle } from "./optimizer";
import { mountHud, type Hud } from "./hud";
import { pickSogUrl } from "./tiering";
import { assetUrl } from "../catalogue/concept";
import type { ViewerHandle, ViewerMode, ViewerOptions } from "./types";

export async function loadViewer(opts: ViewerOptions): Promise<ViewerHandle> {
  const { canvas, concept, profile, hotspotLayer } = opts;
  const progress = opts.onProgress ?? (() => {});

  progress({ phase: "engine" });
  const bundle: EngineBundle = await createEngine(canvas, profile);
  const { engine, kind } = bundle;

  let mode: ViewerMode = "hero";
  let activeScene: Scene | null = null;
  let pendingOld: Scene | null = null;
  let optimizer: OptimizerHandle | null = null;
  let hotspots: HotspotLayer | null = null;
  let hud: Hud | null = null;
  let disposed = false;
  let generation = 0; // stale async scene builds (rapid mode switches) get discarded

  const flushPendingOld = () => {
    pendingOld?.dispose();
    pendingOld = null;
  };

  const stopSceneExtras = () => {
    optimizer?.stop();
    optimizer = null;
    hotspots?.dispose();
    hotspots = null;
  };

  const swapScene = (next: Scene, nextMode: ViewerMode, inspect: boolean) => {
    // a re-swap before the previous scene's first frame must not orphan it
    flushPendingOld();
    stopSceneExtras();
    pendingOld = activeScene;
    activeScene = next;
    mode = nextMode;
    engine.stopRenderLoop();
    engine.runRenderLoop(() => next.render());
    // dispose the old scene only after the new one produced a frame, so the
    // switch never shows a black flash (flushPendingOld is idempotent)
    next.onAfterRenderObservable.addOnce(flushPendingOld);
    // degradation from a heavier previous scene must not stick: reset to the
    // tier baseline, then let the optimizer degrade this scene on its own
    bundle.applyScaling();
    optimizer = startOptimizer(next, profile, inspect);
    opts.onModeChange?.(nextMode);
  };

  // a superseded build must not keep driving the shared progress callback
  const progressFor = (gen: number) => (p: Parameters<typeof progress>[0]) => {
    if (!disposed && gen === generation) progress(p);
  };

  const enterHero = async () => {
    const gen = ++generation;
    const sogPath = pickSogUrl(profile.tier, concept.assets.hero_sog);
    if (!sogPath) throw new Error(`concept "${concept.id}" has no hero_sog for tier ${profile.tier}`);
    const hero = await buildHeroScene(
      engine,
      assetUrl(sogPath),
      concept.camera_envelope,
      profile.useSogTextures,
      progressFor(gen),
    );
    if (disposed || gen !== generation) {
      hero.scene.dispose();
      return;
    }
    swapScene(hero.scene, "hero", false);
    if (hotspotLayer && concept.hotspots.length > 0) hotspots = mountHotspots(hero.scene, hotspotLayer, concept.hotspots);
  };

  const enterInspect = async () => {
    if (!concept.assets.inspect_glb) throw new Error("inspect mode unavailable: concept has no inspect_glb");
    const gen = ++generation;
    // second lazy boundary: glTF/KTX2/meshopt code loads only on demand
    const { buildInspectScene } = await import("./inspect");
    const inspect = await buildInspectScene(engine, concept, hotspotLayer, progressFor(gen));
    if (disposed || gen !== generation) {
      inspect.hotspots?.dispose();
      inspect.scene.dispose();
      return;
    }
    swapScene(inspect.scene, "inspect", true);
    hotspots = inspect.hotspots;
  };

  const onPageHide = (e: PageTransitionEvent) => {
    // bfcache-persisted navigations keep the viewer alive; visibilitychange
    // already paused the render loop and resumes it on restore
    if (!e.persisted) handle.dispose();
  };
  const onVisibility = () => {
    if (document.hidden) {
      engine.stopRenderLoop();
    } else if (activeScene) {
      const scene = activeScene;
      // a swap that completed while hidden already registered its loop —
      // never stack a second one
      engine.stopRenderLoop();
      engine.runRenderLoop(() => scene.render());
    }
  };
  addEventListener("pagehide", onPageHide);
  document.addEventListener("visibilitychange", onVisibility);

  const handle: ViewerHandle = {
    engineKind: kind,
    mode: () => mode,
    enterInspect,
    enterHero,
    fps: () => engine.getFps(),
    dispose() {
      if (disposed) return;
      disposed = true;
      generation++;
      removeEventListener("pagehide", onPageHide);
      document.removeEventListener("visibilitychange", onVisibility);
      stopSceneExtras();
      hud?.dispose();
      engine.stopRenderLoop();
      flushPendingOld();
      activeScene?.dispose();
      activeScene = null;
      bundle.dispose();
    },
  };

  if (profile.hud && canvas.parentElement) hud = mountHud(engine, kind, profile, canvas.parentElement);

  try {
    await enterHero();
  } catch (err) {
    // never leak an engine + listeners behind a rejected loadViewer — the
    // caller has no handle to dispose
    handle.dispose();
    throw err;
  }
  return handle;
}
