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
import { assetUrl, type CameraEnvelope } from "../catalogue/concept";
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
  // per-object zoom state (capture child-rig envelopes) — hero mode only
  let objectFocus: string | null = null;
  let focusEnvelope: ((env: CameraEnvelope) => void) | null = null;

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
    objectFocus = null;
    focusEnvelope = null;
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

    // one camera animation at a time: glides the target (and optionally the
    // radius) with ease-out cubic over ~600 ms, then runs onDone. A replaced
    // in-flight animation runs its pending onDone IMMEDIATELY — envelope swaps
    // park their destination limits there, and dropping it would strand the
    // camera on the widened transition limits forever.
    let animObs: Observer<Scene> | null = null;
    let animPending: (() => void) | null = null;
    const animateCamera = (dest: Vector3, radiusTo?: number, onDone?: () => void) => {
      if (animObs) {
        hero.scene.onBeforeRenderObservable.remove(animObs);
        animObs = null;
        animPending?.();
      }
      animPending = onDone ?? null;
      const from = hero.camera.target.clone();
      const radiusFrom = hero.camera.radius;
      let t = 0;
      animObs = hero.scene.onBeforeRenderObservable.add(() => {
        t += hero.scene.getEngine().getDeltaTime() / 600;
        const k = t >= 1 ? 1 : 1 - Math.pow(1 - t, 3); // ease-out cubic
        hero.camera.setTarget(Vector3.Lerp(from, dest, k));
        if (radiusTo != null) hero.camera.radius = radiusFrom + (radiusTo - radiusFrom) * k;
        if (t >= 1 && animObs) {
          hero.scene.onBeforeRenderObservable.remove(animObs);
          animObs = null;
          animPending = null;
          onDone?.();
        }
      });
    };

    // clicking a pin glides the camera target onto it (clamped to the pan
    // envelope so the click can never escape the trained region), then lets
    // the page open its popup. While an object envelope is focused, ITS pan
    // rules apply — object envelopes carry no pan, so the pin click only
    // opens the popup without moving the camera off the trained close-up.
    const retargetHero = (to: Vector3) => {
      const env = objectFocus ? concept.object_envelopes[objectFocus] : concept.camera_envelope;
      if (objectFocus && !env?.pan_m) return;
      let dest = to.clone();
      if (env?.pan_m) {
        const center = new Vector3(env.target_m[0], env.target_m[1], env.target_m[2]);
        const d = dest.subtract(center);
        if (d.length() > env.pan_m.max_from_center) {
          dest = center.add(d.scale(env.pan_m.max_from_center / d.length()));
        }
      }
      animateCamera(dest);
    };

    // envelope swap (per-object zoom): widen the limits to the union for the
    // flight — applying the tight destination limits mid-air would hard-snap
    // radius/beta — then land exactly on the destination envelope.
    // null limits mean UNBOUNDED: any null side of the union stays null.
    const union = (a: number | null, b: number | null, pick: (x: number, y: number) => number) =>
      a == null || b == null ? null : pick(a, b);
    focusEnvelope = (env: CameraEnvelope) => {
      const cam = hero.camera;
      cam.lowerRadiusLimit = union(cam.lowerRadiusLimit, env.radius_m.min, Math.min);
      cam.upperRadiusLimit = union(cam.upperRadiusLimit, env.radius_m.max, Math.max);
      cam.lowerBetaLimit = Math.min(cam.lowerBetaLimit ?? 0.01, rad(env.beta_deg.min ?? 1));
      cam.upperBetaLimit = Math.max(cam.upperBetaLimit ?? Math.PI - 0.01, rad(env.beta_deg.max ?? 179));
      cam.lowerAlphaLimit = null;
      cam.upperAlphaLimit = null;
      const dest = new Vector3(env.target_m[0], env.target_m[1], env.target_m[2]);
      const rMin = env.radius_m.min ?? 0.05;
      const rMax = env.radius_m.max ?? cam.radius;
      const radiusTo = env.radius_m.default ?? Math.min(Math.max(cam.radius, rMin), rMax);
      animateCamera(dest, radiusTo, () => applyEnvelope(cam, env));
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
    objectFocus: () => objectFocus,
    focusObject(name) {
      const env = concept.object_envelopes[name];
      if (!env) throw new Error(`concept "${concept.id}" has no object envelope "${name}"`);
      if (mode !== "hero" || !focusEnvelope) throw new Error("object zoom is hero-mode only");
      focusEnvelope(env);
      objectFocus = name;
    },
    clearObjectFocus() {
      if (!objectFocus) return;
      if (mode !== "hero" || !focusEnvelope || !concept.camera_envelope) return;
      focusEnvelope(concept.camera_envelope);
      objectFocus = null;
    },
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
