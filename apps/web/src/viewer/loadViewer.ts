// Sole public entry of the viewer (the lazy boundary — landing code reaches
// this module ONLY via dynamic import()). Owns the hero⇄inspect state machine,
// engine lifetime, optimizer, HUD, feature views, and disposal.

import type { Scene } from "@babylonjs/core/scene";
import type { Observer } from "@babylonjs/core/Misc/observable";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import type { GaussianSplattingMesh } from "@babylonjs/core/Meshes/GaussianSplatting/gaussianSplattingMesh";
import { GroundPanCamera } from "./groundPanCamera";
// multi-canvas views: registerView/unRegisterView on AbstractEngine
import "@babylonjs/core/Engines/Extensions/engine.views";
import { createEngine, type EngineBundle } from "./engine";
import { buildHeroScene, buildFeatureSplatScene } from "./heroScene";
import { mountHotspots, type HotspotLayer } from "./hotspots";
import { startOptimizer, type OptimizerHandle } from "./optimizer";
import { mountHud, type Hud } from "./hud";
import { pickSogUrl } from "./tiering";
import { applyEnvelope } from "./cameraEnvelope";
import { assetUrl, type CameraControls, type CameraEnvelope, type Hotspot } from "../catalogue/concept";
import type { FeatureViewHandle, ViewerHandle, ViewerMode, ViewerOptions } from "./types";

const rad = (deg: number) => (deg * Math.PI) / 180;
const preventDefault = (e: Event) => e.preventDefault();

// Feature windows always carry a parsed controls block from the JSON; this only
// covers a caller that omits it (the type allows it optional).
const FEATURE_CONTROLS_FALLBACK: CameraControls = {
  rotate_speed: 1,
  move_speed: 1,
  zoom_speed: 1,
  glide_after_release: 0.9,
};

// One-sided-safe alpha clamp (either limit may be null = unbounded).
const clampAlpha = (a: number, lo: number | null, hi: number | null): number => {
  if (lo != null) a = Math.max(lo, a);
  if (hi != null) a = Math.min(hi, a);
  return a;
};

// Neutral "fit to object" framing for a per-window feature splat — allowed
// utility framing (a validation-view default; precise framing stays Kari's).
// Gaussian splats routinely carry sparse outlier gaussians (and the lunar tile
// a ~100 km skirt), so the raw bounding sphere zooms the subject to a speck; a
// robust 90th-percentile radius around the median of the splat's own centers
// frames the actual mass instead. Falls back to the bounding sphere if the
// internal position buffer is unavailable (deps are exact-pinned @ 9.16.1).
function frameCameraToSplat(cam: GroundPanCamera, splat: GaussianSplattingMesh, alphaOffsetDeg: number): void {
  splat.computeWorldMatrix(true);
  const wm = splat.getWorldMatrix();
  let cx = 0, cy = 0, cz = 0, radius = 1;
  const pos = (splat as unknown as { _splatPositions?: Float32Array })._splatPositions;
  if (pos && pos.length >= 3) {
    const n = pos.length / 3;
    const step = Math.max(1, Math.floor(n / 8000));
    const xs: number[] = [], ys: number[] = [], zs: number[] = [];
    const v = new Vector3();
    for (let i = 0; i < n; i += step) {
      v.set(pos[i * 3], pos[i * 3 + 1], pos[i * 3 + 2]);
      Vector3.TransformCoordinatesToRef(v, wm, v);
      xs.push(v.x); ys.push(v.y); zs.push(v.z);
    }
    const median = (a: number[]) => { const s = a.slice().sort((p, q) => p - q); return s[s.length >> 1]; };
    cx = median(xs); cy = median(ys); cz = median(zs);
    const d = xs.map((x, k) => Math.hypot(x - cx, ys[k] - cy, zs[k] - cz)).sort((p, q) => p - q);
    radius = d[Math.floor(d.length * 0.9)] || 1;
  } else {
    const bs = splat.getBoundingInfo().boundingSphere;
    cx = bs.centerWorld.x; cy = bs.centerWorld.y; cz = bs.centerWorld.z; radius = bs.radiusWorld;
  }
  radius = Math.max(0.1, radius);
  cam.setTarget(new Vector3(cx, cy, cz));
  cam.radius = radius * 2.6;
  cam.lowerRadiusLimit = radius * 0.3;
  cam.upperRadiusLimit = radius * 10;
  cam.minZ = Math.max(0.01, radius * 0.01);
  cam.maxZ = radius * 200;
  cam.fov = rad(45);
  cam.alpha = -Math.PI / 2 + rad(alphaOffsetDeg);
  cam.beta = rad(68);
}

// Overview POIs re-center the window camera on the clicked point: a smooth
// ease-out target glide, zoom (radius) unchanged — no popup. Returns a focus()
// (a new click retargets an in-flight glide) and cancel() for teardown.
function makeFocuser(scene: Scene, camera: GroundPanCamera): {
  focus(pos: [number, number, number]): void;
  cancel(): void;
} {
  let obs: Observer<Scene> | null = null;
  const cancel = () => {
    if (obs) {
      scene.onBeforeRenderObservable.remove(obs);
      obs = null;
    }
  };
  return {
    cancel,
    focus(pos) {
      cancel();
      const from = camera.target.clone();
      const dest = new Vector3(pos[0], pos[1], pos[2]);
      let t = 0;
      obs = scene.onBeforeRenderObservable.add(() => {
        t += scene.getEngine().getDeltaTime() / 500;
        const k = t >= 1 ? 1 : 1 - Math.pow(1 - t, 3); // ease-out cubic
        Vector3.LerpToRef(from, dest, k, camera.target);
        if (t >= 1) cancel();
      });
    },
  };
}

export async function loadViewer(opts: ViewerOptions): Promise<ViewerHandle> {
  const { canvas, concept, profile, hotspotLayer } = opts;
  const progress = opts.onProgress ?? (() => {});

  progress({ phase: "engine" });
  const bundle: EngineBundle = await createEngine(canvas, profile);
  const { engine, kind } = bundle;
  // right-drag pans (when the envelope allows it) — the browser menu must not
  canvas.addEventListener("contextmenu", preventDefault);
  // middle-button (scroll-wheel press) drag pans the hero (mapped in
  // heroScene.ts) — kill Chrome's middle-click autoscroll, which starts on the
  // native mousedown and is NOT covered by Babylon's pointer-event preventDefault.
  const onMainMouseDown = (e: MouseEvent) => { if (e.button === 1) e.preventDefault(); };
  canvas.addEventListener("mousedown", onMainMouseDown);
  // hovering the main canvas reclaims input from any feature view
  const onMainEnter = () => {
    if (currentInput && currentInput.canvas !== canvas && activeScene && mode === "hero") {
      const heroCam = activeScene.activeCamera;
      if (heroCam) activateInput({ canvas, camera: heroCam, scene: activeScene });
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
  // Multi-view render loop: the views extension sets engine.activeView before
  // each view's render pass, so render THAT view's camera scene. Feature windows
  // with their own splat live in a separate scene and thus draw their own splat;
  // the display canvas (view #0, no camera) and any hero-scene feature views
  // fall back to the active hero/inspect scene. Shared by swapScene AND the
  // visibility handler so a tab hide/show never reverts to a hero-only loop
  // (which would redraw the hero splat into every window).
  const renderActiveView = () => {
    const av = (engine as unknown as { activeView?: { camera?: { getScene(): Scene } | null } | null }).activeView;
    (av?.camera?.getScene() ?? activeScene)?.render();
  };
  // per-object zoom state (capture child-rig envelopes) — hero mode only
  let objectFocus: string | null = null;
  let focusEnvelope: ((env: CameraEnvelope) => void) | null = null;

  // Multi-view input model: exactly ONE (scene, camera) has controls attached
  // at a time, switched on pointerenter — otherwise every camera consumes the
  // same pointer stream. Scene-aware: a feature window may render its OWN scene
  // (per-window splat), so we attach/detach THAT entry's scene, not just the
  // hero's — without this those windows never receive pointer events.
  // attachControl(false) keeps preventDefault ON (a bare drag must rotate, not
  // start a page-scrolling selection — the same guard the hero camera uses).
  interface InputEntry {
    canvas: HTMLCanvasElement;
    scene: Scene;
    camera: { attachControl(noPreventDefault?: boolean): void; detachControl(): void };
  }
  let currentInput: InputEntry | null = null;
  const activateInput = (entry: InputEntry) => {
    if (disposed || currentInput?.canvas === entry.canvas) return;
    if (currentInput) {
      currentInput.camera.detachControl();
      // the scene's inputManager owns the DOM listeners — detach the old
      // scene and bind the new one, or events never reach the new camera
      currentInput.scene.detachControl();
    }
    engine.inputElement = entry.canvas;
    entry.scene.attachControl();
    entry.camera.attachControl(false);
    currentInput = entry;
  };

  // Direct pointer controls for a secondary view canvas. Babylon routes camera
  // input ONLY through the active scene's input manager, so feature windows
  // (their own splat scene, or a second camera in the hero scene) never get it
  // via scene.attachControl — we drive the camera ourselves. Button map matches
  // the hero: left = orbit, right/middle = ground pan, wheel = zoom. Every
  // handler preventDefaults so a drag never scrolls the page, opens the context
  // menu, or triggers middle-click autoscroll (the last needs preventDefault on
  // `mousedown`, which pointerdown's preventDefault does NOT suppress in Chrome).
  // getCamera is late-bound: the splat window's camera doesn't exist until its
  // .sog finishes loading. Returns a teardown that removes every listener.
  const attachDirectControls = (
    viewCanvas: HTMLCanvasElement,
    getCamera: () => GroundPanCamera | null,
    ctrl: CameraControls,
  ): (() => void) => {
    const rotK = 0.01 * ctrl.rotate_speed;
    const zoomK = 0.12 * ctrl.zoom_speed;
    let dragMode: "none" | "orbit" | "pan" = "none";
    let lastX = 0, lastY = 0;

    // orbit application with the authored limits (a view camera driven by
    // these handlers doesn't run Babylon's stock input clamp): distance
    // limits are applied on the wheel, angle limits here. Shared by the live
    // drag AND the glide so the glide can never escape the envelope.
    const applyOrbit = (cam: GroundPanCamera, dxPx: number, dyPx: number) => {
      cam.alpha = clampAlpha(cam.alpha - dxPx * rotK, cam.lowerAlphaLimit, cam.upperAlphaLimit);
      const bLo = Math.max(0.02, cam.lowerBetaLimit ?? 0.02);
      const bHi = Math.min(Math.PI - 0.02, cam.upperBetaLimit ?? Math.PI - 0.02);
      cam.beta = Math.min(bHi, Math.max(bLo, cam.beta - dyPx * rotK));
    };

    // glide_after_release: Babylon's stock inertia lives in the input pipeline
    // these windows bypass, so the direct controls implement it themselves —
    // pixel-velocity is tracked during the drag (EMA over move events) and
    // decayed per rendered frame after release, Babylon-style (v *= inertia).
    let vX = 0, vY = 0;
    let glideMode: "orbit" | "pan" = "orbit";
    let glideObs: Observer<Scene> | null = null;
    let glideScene: Scene | null = null;
    const stopGlide = () => {
      if (glideObs && glideScene) glideScene.onBeforeRenderObservable.remove(glideObs);
      glideObs = null;
      glideScene = null;
    };
    const startGlide = (cam: GroundPanCamera) => {
      const inertia = ctrl.glide_after_release;
      if (inertia <= 0 || Math.hypot(vX, vY) < 0.5) return;
      glideScene = cam.getScene();
      glideMode = dragMode === "pan" ? "pan" : "orbit";
      glideObs = glideScene.onBeforeRenderObservable.add(() => {
        const c = getCamera();
        if (!c) return stopGlide();
        if (glideMode === "orbit") applyOrbit(c, vX, vY);
        else c.panByPixels(vX, vY, ctrl.move_speed);
        vX *= inertia;
        vY *= inertia;
        if (Math.hypot(vX, vY) < 0.05) stopGlide();
      });
    };

    const onDown = (e: PointerEvent) => {
      const cam = getCamera();
      if (!cam) return;
      stopGlide(); // grabbing kills any in-flight glide
      vX = vY = 0;
      dragMode = e.button === 0 ? "orbit" : "pan"; // right(2)/middle(1) → pan
      lastX = e.clientX;
      lastY = e.clientY;
      try { viewCanvas.setPointerCapture(e.pointerId); } catch { /* headless */ }
      e.preventDefault();
    };
    const onMove = (e: PointerEvent) => {
      const cam = getCamera();
      if (dragMode === "none" || !cam) return;
      const dx = e.clientX - lastX;
      const dy = e.clientY - lastY;
      if (dragMode === "orbit") applyOrbit(cam, dx, dy);
      else cam.panByPixels(dx, dy, ctrl.move_speed);
      // release velocity ≈ recent per-event delta (EMA smooths jittery input)
      vX = 0.6 * dx + 0.4 * vX;
      vY = 0.6 * dy + 0.4 * vY;
      lastX = e.clientX;
      lastY = e.clientY;
      e.preventDefault();
    };
    const onUp = (e: PointerEvent) => {
      const cam = getCamera();
      if (dragMode !== "none" && cam) startGlide(cam);
      dragMode = "none";
      try { viewCanvas.releasePointerCapture(e.pointerId); } catch { /* already released */ }
    };
    // eased zoom: each tick feeds a per-frame zoom velocity that decays like
    // the drag glide (v *= glide_after_release). The initial velocity is set
    // so a full decay series still totals the same 12%-per-tick step:
    // exp(v0 / (1 - inertia)) = 1 + zoomK. glide 0 => the whole step at once.
    let vZoom = 0;
    let zoomObs: Observer<Scene> | null = null;
    let zoomScene: Scene | null = null;
    const stopZoom = () => {
      if (zoomObs && zoomScene) zoomScene.onBeforeRenderObservable.remove(zoomObs);
      zoomObs = null;
      zoomScene = null;
      vZoom = 0;
    };
    const zoomTick = (c: GroundPanCamera) => {
      const r = c.radius * Math.exp(vZoom);
      const clamped = Math.min(c.upperRadiusLimit ?? r, Math.max(c.lowerRadiusLimit ?? r, r));
      c.radius = clamped;
      if (clamped !== r) return stopZoom(); // hit a zoom limit: stop coasting
      vZoom *= ctrl.glide_after_release;
      if (Math.abs(vZoom) < 1e-4) stopZoom();
    };
    const onWheel = (e: WheelEvent) => {
      const cam = getCamera();
      if (cam) {
        const inertia = ctrl.glide_after_release;
        const step = Math.sign(e.deltaY) * Math.log(1 + zoomK);
        if (inertia <= 0) {
          vZoom = step;
          zoomTick(cam); // whole step immediately, no coast
        } else {
          vZoom += step * (1 - inertia);
          if (!zoomObs) {
            zoomScene = cam.getScene();
            zoomObs = zoomScene.onBeforeRenderObservable.add(() => {
              const c = getCamera();
              if (!c) return stopZoom();
              zoomTick(c);
            });
          }
        }
      }
      e.preventDefault();
    };
    // kill Chrome middle-click autoscroll before it starts (pointerdown's
    // preventDefault doesn't cover it)
    const onMouseDown = (e: MouseEvent) => { if (e.button === 1) e.preventDefault(); };
    viewCanvas.addEventListener("contextmenu", preventDefault);
    viewCanvas.addEventListener("pointerdown", onDown);
    viewCanvas.addEventListener("pointermove", onMove);
    viewCanvas.addEventListener("pointerup", onUp);
    viewCanvas.addEventListener("pointercancel", onUp);
    viewCanvas.addEventListener("wheel", onWheel, { passive: false });
    viewCanvas.addEventListener("mousedown", onMouseDown);
    return () => {
      stopGlide();
      stopZoom();
      viewCanvas.removeEventListener("contextmenu", preventDefault);
      viewCanvas.removeEventListener("pointerdown", onDown);
      viewCanvas.removeEventListener("pointermove", onMove);
      viewCanvas.removeEventListener("pointerup", onUp);
      viewCanvas.removeEventListener("pointercancel", onUp);
      viewCanvas.removeEventListener("wheel", onWheel);
      viewCanvas.removeEventListener("mousedown", onMouseDown);
    };
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
    engine.runRenderLoop(renderActiveView);
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
    currentInput = { canvas, camera: hero.camera, scene: hero.scene };

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

    // permanent QA overlays, each its own lazy chunk, never loaded without
    // the flag: ?debug=hotspots renders in-scene anchor spheres,
    // ?debug=camera mounts a live camera/envelope/config readout (both in
    // the asset-integration checklist; comma-combinable)
    const debugFlags = new URLSearchParams(location.search).get("debug")?.split(",") ?? [];
    if (debugFlags.includes("hotspots") && concept.hotspots.length > 0) {
      const startRadius = hero.camera.radius;
      void import("./debugHotspots").then((m) => {
        if (!disposed && gen === generation) m.mountHotspotDebug(hero.scene, concept.hotspots, startRadius);
      });
    }
    const debugParent = canvas.parentElement;
    if (debugFlags.includes("camera") && debugParent) {
      void import("./debugCamera").then((m) => {
        if (!disposed && gen === generation) {
          m.mountCameraDebug(hero.scene, hero.camera, concept.camera_envelope, debugParent);
        }
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

  // An Overview window that shows its OWN splat (concept feature scene_file):
  // a standalone scene, auto-framed to the splat's bounds, rendered into this
  // view canvas. Interactive via DIRECT pointer handlers driving its camera's
  // alpha/beta/radius — Babylon's camera pointer input routes through the ACTIVE
  // scene's input manager (scoped to the hero scene here), so a secondary
  // scene's camera never receives it; driving the angles directly is robust,
  // isolated, and prevent-defaults so a drag never scrolls the page. Torn down
  // with the feature view (scene swap / dispose).
  const attachSplatFeatureView = (
    viewCanvas: HTMLCanvasElement,
    sogUrl: string,
    alphaOffsetDeg: number,
    controls: CameraControls,
    cameraEnvelope: CameraEnvelope | null,
    pins: Hotspot[],
    hotspotLayer: HTMLElement | null,
  ) => {
    let featScene: Scene | null = null;
    let camera: GroundPanCamera | null = null;
    let view: { enabled: boolean } | null = null;
    let enabled = true;
    let killed = false;
    let poiLayer: HotspotLayer | null = null;
    let focuser: ReturnType<typeof makeFocuser> | null = null;
    const detachControls = attachDirectControls(viewCanvas, () => camera, controls);
    void (async () => {
      try {
        const built = await buildFeatureSplatScene(engine, sogUrl, profile.useSogTextures);
        if (disposed || killed) {
          built.scene.dispose();
          return;
        }
        featScene = built.scene;
        const cam = new GroundPanCamera(
          `feature-splat-${featureViews.length}`, -Math.PI / 2, 1.1, 9, Vector3.Zero(), featScene);
        // authored per-window framing wins; otherwise auto-fit the splat
        if (cameraEnvelope) {
          applyEnvelope(cam, cameraEnvelope);
        } else if (built.splat) {
          frameCameraToSplat(cam, built.splat, alphaOffsetDeg);
        } else {
          cam.fov = rad(45);
          cam.alpha = -Math.PI / 2 + rad(alphaOffsetDeg);
          cam.beta = rad(68);
        }
        camera = cam;
        view = engine.registerView(viewCanvas, cam);
        view.enabled = enabled;
        // POIs: hover = title, click = re-center on the point (no popup)
        if (hotspotLayer && pins.length > 0) {
          focuser = makeFocuser(featScene, cam);
          poiLayer = mountHotspots(featScene, cam, hotspotLayer, pins, (h) => focuser?.focus(h.position_m));
        }
      } catch (err) {
        console.error(`feature splat failed (${sogUrl})`, err);
      }
    })();
    const fv = {
      setEnabled(e: boolean) {
        enabled = e;
        if (view) view.enabled = e;
      },
      dispose() {
        const i = featureViews.indexOf(fv);
        if (i >= 0) featureViews.splice(i, 1);
        fv._teardown();
      },
      _teardown() {
        killed = true;
        detachControls();
        focuser?.cancel();
        poiLayer?.dispose();
        engine.unRegisterView(viewCanvas);
        camera?.dispose();
        featScene?.dispose();
        featScene = null;
      },
    };
    featureViews.push(fv);
    return fv;
  };

  const attachFeatureView: ViewerHandle["attachFeatureView"] = (viewCanvas, viewOpts) => {
    if (disposed) throw new Error("viewer disposed");
    if (mode !== "hero" || !activeScene) throw new Error("feature views attach to the live hero scene");
    const ctrl = viewOpts?.controls ?? FEATURE_CONTROLS_FALLBACK;
    const pins = viewOpts?.pins ?? [];
    const poiHost = viewOpts?.hotspotLayer ?? null;
    if (viewOpts?.sogUrl) {
      return attachSplatFeatureView(
        viewCanvas,
        viewOpts.sogUrl,
        viewOpts.alphaOffsetDeg ?? 0,
        ctrl,
        viewOpts.cameraEnvelope ?? null,
        pins,
        poiHost,
      );
    }
    const scene = activeScene;

    // No per-window splat: fall back to a second camera on the hero scene, so
    // this window shows the hero splat from its own angle. Per-window framing
    // wins when authored; otherwise use the hero envelope + view_angle_deg.
    const camera = new GroundPanCamera(
      `feature-${featureViews.length}`,
      -Math.PI / 2,
      1.1,
      9,
      Vector3.Zero(),
      scene,
    );
    const env = viewOpts?.cameraEnvelope ?? concept.camera_envelope;
    if (env) applyEnvelope(camera, env);
    // the azimuth offset only shapes the hero-fallback framing; an authored
    // per-window camera already specifies its opening angle_around_deg.start
    if (!viewOpts?.cameraEnvelope) camera.alpha += rad(viewOpts?.alphaOffsetDeg ?? 0);

    // Drive this camera directly (see attachDirectControls). It has its own
    // camera, so orbiting/panning here never disturbs the hero's main view;
    // preventDefault on every handler keeps a drag from scrolling the page.
    const detachControls = attachDirectControls(viewCanvas, () => camera, ctrl);

    const view = engine.registerView(viewCanvas, camera);

    // POIs: hover = title, click = re-center on the point (no popup). The layer
    // observer guards on this camera, so during the hero's own render pass these
    // pins stay put — only this window's pass writes their positions.
    let poiLayer: HotspotLayer | null = null;
    let focuser: ReturnType<typeof makeFocuser> | null = null;
    if (poiHost && pins.length > 0) {
      focuser = makeFocuser(scene, camera);
      poiLayer = mountHotspots(scene, camera, poiHost, pins, (h) => focuser?.focus(h.position_m));
    }

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
        detachControls();
        focuser?.cancel();
        poiLayer?.dispose();
        engine.unRegisterView(viewCanvas);
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
      // a swap that completed while hidden already registered its loop —
      // never stack a second one. Reuse the multi-view loop so feature windows
      // keep drawing their own splats after a hide/show.
      engine.stopRenderLoop();
      engine.runRenderLoop(renderActiveView);
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
      canvas.removeEventListener("mousedown", onMainMouseDown);
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
