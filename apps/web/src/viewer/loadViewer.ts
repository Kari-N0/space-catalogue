// Sole public entry of the viewer (the lazy boundary — landing code reaches
// this module ONLY via dynamic import()). Owns the hero⇄inspect state machine,
// engine lifetime, optimizer, HUD, feature views, and disposal.

import type { Scene } from "@babylonjs/core/scene";
import type { Observer } from "@babylonjs/core/Misc/observable";
import { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
// multi-canvas views: registerView/unRegisterView on AbstractEngine
import "@babylonjs/core/Engines/Extensions/engine.views";
import { createEngine, type EngineBundle } from "./engine";
import { buildHeroScene } from "./heroScene";
import { mountHotspots, type HotspotLayer } from "./hotspots";
import { startOptimizer, type OptimizerHandle } from "./optimizer";
import { mountHud, type Hud } from "./hud";
import { pickSogUrl } from "./tiering";
import { applyControls, applyEnvelope } from "./cameraEnvelope";
import { assetUrl } from "../catalogue/concept";
import type { FeatureViewHandle, ViewerHandle, ViewerMode, ViewerOptions } from "./types";

const rad = (deg: number) => (deg * Math.PI) / 180;
const preventDefault = (e: Event) => e.preventDefault();

export async function loadViewer(opts: ViewerOptions): Promise<ViewerHandle> {
  const { canvas, concept, profile, hotspotLayer } = opts;
  const progress = opts.onProgress ?? (() => {});

  progress({ phase: "engine" });
  const bundle: EngineBundle = await createEngine(canvas, profile);
  const { engine, kind } = bundle;
  // right-drag pans (when the envelope allows it) — the browser menu must not
  canvas.addEventListener("contextmenu", preventDefault);
  // hovering the main canvas reclaims input from any feature view
  const onMainEnter = () => {
    if (currentInput && currentInput.canvas !== canvas && activeScene && mode === "hero") {
      const heroCam = activeScene.activeCamera;
      if (heroCam) activateInput({ canvas, camera: heroCam });
    }
  };
  canvas.addEventListener("pointerenter", onMainEnter);

  let mode: ViewerMode = "hero";
  let activeScene: Scene | null = null;
  let pendingOld: Scene | null = null;
  let optimizer: OptimizerHandle | null = null;
  let hotspots: HotspotLayer | null = null;
  let hud: Hud | null = null;
  let disposed = false;
  let generation = 0; // stale async scene builds (rapid mode switches) get discarded
  const featureViews: (FeatureViewHandle & { _teardown(): void })[] = [];

  // Multi-view input model: exactly ONE camera has controls attached at a
  // time, switched on pointerenter — otherwise every camera consumes the same
  // pointer stream (all views move together, and an off-screen view's input
  // can steal focus and smooth-scroll the page to it).
  interface InputEntry {
    canvas: HTMLCanvasElement;
    camera: { attachControl(noPreventDefault?: boolean): void; detachControl(): void };
  }
  let currentInput: InputEntry | null = null;
  const activateInput = (entry: InputEntry) => {
    if (disposed || currentInput === entry || !activeScene) return;
    currentInput?.camera.detachControl();
    // the scene's inputManager owns the DOM listeners — it must rebind to the
    // new canvas too, or events from that canvas never reach camera inputs
    activeScene.detachControl();
    engine.inputElement = entry.canvas;
    activeScene.attachControl();
    entry.camera.attachControl();
    currentInput = entry;
  };

  const flushPendingOld = () => {
    pendingOld?.dispose();
    pendingOld = null;
  };

  const disposeFeatureViews = () => {
    for (const fv of featureViews.splice(0)) fv._teardown();
  };

  const stopSceneExtras = () => {
    optimizer?.stop();
    optimizer = null;
    hotspots?.dispose();
    hotspots = null;
    disposeFeatureViews();
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
    // buildHeroScene attached hero controls; it is the current input owner
    currentInput = { canvas, camera: hero.camera };

    // clicking a pin glides the camera target onto it (clamped to the pan
    // envelope so the click can never escape the trained region), then lets
    // the page open its popup
    let retargetObs: Observer<Scene> | null = null;
    const retargetHero = (to: Vector3) => {
      let dest = to.clone();
      const env = concept.camera_envelope;
      if (env?.pan_m) {
        const center = new Vector3(env.target_m[0], env.target_m[1], env.target_m[2]);
        const d = dest.subtract(center);
        if (d.length() > env.pan_m.max_from_center) {
          dest = center.add(d.scale(env.pan_m.max_from_center / d.length()));
        }
      }
      if (retargetObs) hero.scene.onBeforeRenderObservable.remove(retargetObs);
      const from = hero.camera.target.clone();
      let t = 0;
      retargetObs = hero.scene.onBeforeRenderObservable.add(() => {
        t += hero.scene.getEngine().getDeltaTime() / 600;
        const k = t >= 1 ? 1 : 1 - Math.pow(1 - t, 3); // ease-out cubic
        hero.camera.setTarget(Vector3.Lerp(from, dest, k));
        if (t >= 1 && retargetObs) {
          hero.scene.onBeforeRenderObservable.remove(retargetObs);
          retargetObs = null;
        }
      });
    };

    if (hotspotLayer && concept.hotspots.length > 0) {
      hotspots = mountHotspots(hero.scene, hero.camera, hotspotLayer, concept.hotspots, (h) => {
        retargetHero(new Vector3(h.position_m[0], h.position_m[1], h.position_m[2]));
        opts.onHotspotSelect?.(h);
      });
    }
  };

  const enterInspect = async () => {
    if (!concept.assets.inspect_glb) throw new Error("inspect mode unavailable: concept has no inspect_glb");
    const gen = ++generation;
    // second lazy boundary: glTF/KTX2/meshopt code loads only on demand
    const { buildInspectScene } = await import("./inspect");
    const inspect = await buildInspectScene(engine, concept, hotspotLayer, progressFor(gen), opts.onHotspotSelect);
    if (disposed || gen !== generation) {
      inspect.hotspots?.dispose();
      inspect.scene.dispose();
      return;
    }
    swapScene(inspect.scene, "inspect", true);
    hotspots = inspect.hotspots;
  };

  const attachFeatureView: ViewerHandle["attachFeatureView"] = (viewCanvas, viewOpts) => {
    if (disposed) throw new Error("viewer disposed");
    if (mode !== "hero" || !activeScene) throw new Error("feature views attach to the live hero scene");
    const scene = activeScene;

    const camera = new ArcRotateCamera(
      `feature-${featureViews.length}`,
      -Math.PI / 2,
      1.1,
      9,
      Vector3.Zero(),
      scene,
    );
    if (concept.camera_envelope) {
      applyEnvelope(camera, concept.camera_envelope);
      if (viewOpts?.controls) {
        // per-window feel override (defaults to the main view's controls)
        applyControls(camera, viewOpts.controls, !!concept.camera_envelope.pan_m?.max_from_center);
      }
    }
    camera.alpha += rad(viewOpts?.alphaOffsetDeg ?? 0);

    // controls attach on pointerenter (single-owner input model above)
    const entry = { canvas: viewCanvas, camera };
    const onEnter = () => activateInput(entry);
    viewCanvas.addEventListener("pointerenter", onEnter);
    viewCanvas.addEventListener("contextmenu", preventDefault);

    const view = engine.registerView(viewCanvas, camera);

    const fv = {
      setEnabled(enabled: boolean) {
        view.enabled = enabled;
      },
      dispose() {
        const i = featureViews.indexOf(fv);
        if (i >= 0) featureViews.splice(i, 1);
        fv._teardown();
      },
      _teardown() {
        viewCanvas.removeEventListener("pointerenter", onEnter);
        viewCanvas.removeEventListener("contextmenu", preventDefault);
        engine.unRegisterView(viewCanvas);
        if (currentInput?.canvas === viewCanvas) currentInput = null;
        camera.detachControl();
        camera.dispose();
      },
    };
    featureViews.push(fv);
    return fv;
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
    attachFeatureView,
    fps: () => engine.getFps(),
    dispose() {
      if (disposed) return;
      disposed = true;
      generation++;
      removeEventListener("pagehide", onPageHide);
      document.removeEventListener("visibilitychange", onVisibility);
      canvas.removeEventListener("contextmenu", preventDefault);
      canvas.removeEventListener("pointerenter", onMainEnter);
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
