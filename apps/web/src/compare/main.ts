// Local Gaussian-splat quality comparison tool (dev-only; compare/index.html,
// served by `npm run compare` → vite.compare.config.ts). Four Overview-style
// 3D windows, each loading a different .sog of the same dataset THROUGH THE
// PRODUCTION CODE PATH — the real loadViewer → attachFeatureView, the real
// concept.css window sizing, and the camera envelope + controls of an actual
// concept-page window (default: the first Overview window, F_01) read live
// from content/concepts/<id>.json. Same resolution, same settings — by
// construction, not by copy.
//
// This entry is NOT in vite.config.ts's rollup inputs: it is never built,
// never deployed, and touches no production file. Splats stream straight
// from the D: staging folder via the /splats-d/ middleware (no repo copies).
//
// URL state (shareable): ?files=a.sog,b.sog,c.sog,d.sog · window=<idx|auto> ·
// sync=0|1 · concept=<id> · cam=<camera block JSON> — plus the production
// viewer knobs (?tier= ?engine= ?dpr= ?hud=1), which pickTier reads exactly
// like the concept page does.

import {
  loadConceptPage,
  type CameraControls,
  type CameraEnvelope,
  type ConceptDoc,
  type PageFeature,
} from "../catalogue/concept";
import {
  camStateFromJson,
  defaultCamState,
  mountCameraPanel,
  stateFromEnvelope,
  type CamState,
  type CameraPanelHandle,
} from "./cameraPanel";
import { pickTier } from "../viewer/tiering";
import type { FeatureViewHandle, ViewerHandle } from "../viewer/types";
import type { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera";
import type { EngineView } from "@babylonjs/core/Engines/AbstractEngine/abstractEngine.views.pure";

interface SplatFile {
  name: string;
  size: number;
  mtime: number;
}

interface Cell {
  index: number;
  name: string;
  file: SplatFile | null;
  canvas: HTMLCanvasElement;
  chip: HTMLElement;
  select: HTMLSelectElement;
  attachedAt: number;
}

const app = document.getElementById("app") as HTMLElement;
const statusEl = document.getElementById("status") as HTMLElement;
const params = new URLSearchParams(location.search);

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

const fmtMB = (bytes: number): string => `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
const fmtCount = (n: number): string =>
  n >= 1e6 ? `${(n / 1e6).toFixed(2)}M` : `${Math.round(n / 1e3)}k`;

/** Default pick: the dataset family of the newest .sog (e.g. de_gerlache_*),
 *  name-sorted, padded with the next-newest other files — four slots. */
function defaultFour(files: SplatFile[]): string[] {
  if (files.length === 0) return [];
  const byNewest = [...files].sort((a, b) => b.mtime - a.mtime);
  const prefix = byNewest[0].name.replace(/_v\d.*$/i, "");
  const family = files
    .map((f) => f.name)
    .filter((n) => n.startsWith(prefix))
    .sort()
    .slice(-4); // a >4 family keeps its HIGHEST versions — never drop the newest
  const rest = byNewest.map((f) => f.name).filter((n) => !family.includes(n));
  return [...family, ...rest].slice(0, 4);
}

function setParamsAndReload(set: Record<string, string>, remove: readonly string[] = []): void {
  const qs = new URLSearchParams(location.search);
  for (const [k, v] of Object.entries(set)) qs.set(k, v);
  for (const k of remove) qs.delete(k);
  location.search = qs.toString();
}

// loadViewer's FEATURE_CONTROLS_FALLBACK — what an unauthored window gets.
const CONTROLS_FALLBACK: CameraControls = {
  rotate_speed: 1,
  move_speed: 1,
  zoom_speed: 1,
  glide_after_release: 0.9,
};

async function boot(): Promise<void> {
  // -------- data: file listing + the real concept JSON ---------------------
  const listingRes = await fetch("/api/splats");
  if (!listingRes.ok) throw new Error(`splat listing failed: HTTP ${listingRes.status}`);
  const listing = (await listingRes.json()) as { dir: string; files: SplatFile[] };
  listing.files.sort((a, b) => a.name.localeCompare(b.name));

  const conceptId = params.get("concept") ?? "moon-base";
  if (!/^[a-z0-9-]+$/i.test(conceptId)) throw new Error(`invalid concept id "${conceptId}"`);
  const page = await loadConceptPage(`/content/concepts/${conceptId}.json`);
  const features = page.page.overview.features;

  // -------- selection state (URL-driven) -----------------------------------
  const windowParam = params.get("window") ?? "0";
  const featureIdx = windowParam === "auto" ? -1 : Number(windowParam);
  const feature: PageFeature | null =
    featureIdx >= 0 && featureIdx < features.length ? features[featureIdx] : null;
  // exactly what page.ts passes for this window; "auto" = no authored camera,
  // which in production means auto-fit framing + default controls
  const envelope: CameraEnvelope | null = feature?.camera_envelope ?? null;
  const controls: CameraControls | undefined = feature?.controls;

  const names =
    params
      .get("files")
      ?.split(",")
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 4) ?? defaultFour(listing.files);
  while (names.length < 4 && listing.files.length > 0) {
    names.push(listing.files[Math.min(names.length, listing.files.length - 1)].name);
  }

  let sync = params.get("sync") !== "0";

  // -------- toolbar ---------------------------------------------------------
  const toolbar = el("div", "compare-toolbar");

  const windowSelect = el("select", "compare-select");
  windowSelect.setAttribute("aria-label", "Window camera settings");
  for (const [i, f] of features.entries()) {
    const opt = el("option", undefined, `camera: ${f.label || `window ${i + 1}`}${f.camera_envelope ? "" : " (auto-fit)"}`);
    opt.value = String(i);
    windowSelect.appendChild(opt);
  }
  const autoOpt = el("option", undefined, "camera: auto-fit (no authored window)");
  autoOpt.value = "auto";
  windowSelect.appendChild(autoOpt);
  windowSelect.value = feature ? String(featureIdx) : "auto";
  // a new source window brings its own camera block — drop any tuned override
  windowSelect.addEventListener("change", () => setParamsAndReload({ window: windowSelect.value }, ["cam"]));

  const syncLabel = el("label");
  const syncBox = el("input");
  syncBox.type = "checkbox";
  syncBox.checked = sync;
  syncBox.addEventListener("change", () => {
    sync = syncBox.checked;
    const qs = new URLSearchParams(location.search);
    qs.set("sync", sync ? "1" : "0");
    history.replaceState(null, "", `?${qs.toString()}`);
  });
  syncLabel.append(syncBox, document.createTextNode("sync cameras"));

  const reloadBtn = el("button", "compare-btn", "Reload");
  reloadBtn.type = "button";
  reloadBtn.addEventListener("click", () => location.reload());

  const readout = el("span", "compare-readout", "");
  toolbar.append(windowSelect, syncLabel, reloadBtn, readout);
  app.insertBefore(toolbar, statusEl);

  const dirNote = el(
    "p",
    "stage-note",
    `files from ${listing.dir} — pick per window; state lives in the URL. ` +
      `A splat at a different scale? press “Fit to splat”.`,
  );
  app.insertBefore(dirNote, statusEl);

  // -------- the four windows (production markup: .feature-media > canvas) --
  const grid = el("div", "compare-grid");
  app.appendChild(grid);

  const cells: Cell[] = names.map((name, index) => {
    const cell = el("div", "compare-cell");
    const select = el("select", "compare-select");
    select.setAttribute("aria-label", `Splat file for window ${index + 1}`);
    for (const f of listing.files) {
      const opt = el("option", undefined, `${f.name} — ${fmtMB(f.size)}`);
      opt.value = f.name;
      select.appendChild(opt);
    }
    // a ?files= name missing from the dir (renamed/deleted since the URL was
    // made) still needs an option, or select.value falls back to "" and the
    // change handler would serialize an empty slot — shifting every window
    // to its right on the next reload. Keep the slot positionally intact.
    if (!listing.files.some((f) => f.name === name)) {
      const missing = el("option", undefined, `${name} — NOT FOUND`);
      missing.value = name;
      missing.disabled = true;
      select.appendChild(missing);
    }
    select.value = name;
    select.addEventListener("change", () => {
      const four = cells.map((c) => c.select.value);
      setParamsAndReload({ files: four.join(",") });
    });

    const media = el("div", "feature-media");
    const canvas = el("canvas", "feature-canvas");
    canvas.setAttribute("aria-label", `Splat comparison window ${index + 1}: ${name}`);
    const chip = el("span", "scrim-chip", `${name} · loading…`);
    media.append(canvas, chip);

    cell.append(select, media);
    grid.appendChild(cell);
    return {
      index,
      name,
      file: listing.files.find((f) => f.name === name) ?? null,
      canvas,
      chip,
      select,
      attachedAt: 0,
    };
  });

  // -------- hidden reference canvas + the production viewer ----------------
  const heroHost = el("div", "compare-hero-host");
  const heroCanvas = el("canvas");
  heroHost.appendChild(heroCanvas);
  document.body.appendChild(heroHost);

  const present = cells.filter((c): c is Cell & { file: SplatFile } => c.file !== null);
  for (const c of cells) {
    if (!c.file) c.chip.textContent = `${c.name} · NOT FOUND in splat dir`;
  }
  if (present.length === 0) {
    statusEl.textContent = `no .sog files found in ${listing.dir}`;
    return;
  }
  // the viewer requires a hero splat; feed it the smallest selected file so
  // the hidden reference view costs as little as possible
  const heroFile = present.reduce((a, b) => (a.file.size <= b.file.size ? a : b)).file;
  const sogUrl = (n: string): string => `/splats-d/${encodeURIComponent(n)}`;

  const concept: ConceptDoc = {
    id: "splat-compare",
    title: "Splat quality comparison",
    assets: {
      poster: null,
      hero_video: null,
      hero_sog: { mobile: sogUrl(heroFile.name), desktop: sogUrl(heroFile.name) },
      inspect_glb: null,
      env: null,
    },
    camera_envelope: envelope,
    object_envelopes: {},
    hotspots: [],
  };

  const profile = pickTier(params);

  // -------- camera state: the panel drives every window ---------------------
  // One controls object, handed to every attachFeatureView and then mutated in
  // place by the panel: loadViewer's direct controls read move_speed and
  // glide_after_release live on each event (rotate_speed/zoom_speed are baked
  // at attach time, so those two ask for a re-attach).
  const liveControls: CameraControls = { ...(controls ?? CONTROLS_FALLBACK) };

  const cams = new Map<HTMLCanvasElement, ArcRotateCamera>();
  let leaderCanvas: HTMLCanvasElement | null = null;
  // default leader = window 1. The map fills in load-completion order (the
  // smallest .sog wins), so "first in the map" would make the readout, "fit"
  // and "capture view" depend on which file happened to decode first.
  const firstCam = (): ArcRotateCamera | null => {
    const win1 = cams.get(present[0].canvas);
    if (win1) return win1;
    for (const cam of cams.values()) return cam;
    return null;
  };
  const leaderCam = (): ArcRotateCamera | null =>
    (leaderCanvas ? (cams.get(leaderCanvas) ?? null) : null) ?? firstCam();
  // Interacting with a window makes it the leader — click or wheel, NOT hover:
  // the panel sits above the grid, so a hover-leader would change hands just
  // from moving the pointer up to "Fit"/"Capture view". The listener lives on
  // the canvas, which survives a re-attach — the camera behind it does not.
  for (const c of present) {
    for (const evName of ["pointerdown", "wheel"] as const) {
      c.canvas.addEventListener(evName, () => {
        leaderCanvas = c.canvas;
      });
    }
  }

  // authored window camera → panel; unauthored → placeholder until the first
  // splat lands and the panel adopts the viewer's own auto-fit numbers
  const baseState: CamState = envelope ? stateFromEnvelope(envelope) : defaultCamState(liveControls);
  // the feel the windows really attach with is the FEATURE's controls block
  // (page.ts passes features[i].controls; features[i].camera.controls is not
  // read by the window controls) — show and drive that, not the envelope's
  baseState.controls = { ...liveControls };
  const camParam = params.get("cam");
  const urlState = camParam ? camStateFromJson(camParam, baseState) : null;
  if (camParam && !urlState) console.warn("compare: ?cam= is not readable JSON — using the window's own camera");

  let camWrite: ReturnType<typeof setTimeout> | undefined;
  // the views only exist after the hero scene resolves; a speed field committed
  // during that load must not call into the (not yet initialised) attach code
  let viewsReady = false;
  const panel: CameraPanelHandle = mountCameraPanel({
    initial: urlState ?? baseState,
    startDirty: urlState != null,
    controls: liveControls,
    cameras: () => [...cams.values()],
    leader: () => leaderCam(),
    leaderLabel: () => {
      const canvas = leaderCanvas ?? present[0].canvas;
      const cell = present.find((c) => c.canvas === canvas);
      return `window ${(cell?.index ?? 0) + 1}`;
    },
    onStateChange: (st) => {
      clearTimeout(camWrite);
      camWrite = setTimeout(() => {
        const qs = new URLSearchParams(location.search);
        qs.set("cam", JSON.stringify(st));
        history.replaceState(null, "", `?${qs.toString()}`);
      }, 400);
    },
    onReattach: () => reattachViews(),
    onReset: () => setParamsAndReload({}, ["cam"]),
  });
  app.insertBefore(panel.el, statusEl);

  // same lazy boundary as page.ts — Babylon loads only here
  const { loadViewer } = await import("../viewer/loadViewer");
  const handle: ViewerHandle = await loadViewer({
    canvas: heroCanvas,
    hotspotLayer: null,
    concept,
    profile,
    onProgress: (p) => {
      statusEl.textContent = p.phase === "ready" ? "" : `reference scene: ${p.phase}…`;
    },
  });
  addEventListener("pagehide", () => {
    panel.dispose();
    handle.dispose();
  });

  // attachFeatureView deliberately hides its camera; reach it the way the
  // engine sees it — the registered view for each canvas (EngineStore is the
  // same Babylon the viewer just loaded, so this import is free).
  const { EngineStore } = await import("@babylonjs/core/Engines/engineStore");
  const engine = EngineStore.LastCreatedEngine;

  const views = new Map<HTMLCanvasElement, FeatureViewHandle>();
  // production parity: windows pause offscreen (same rootMargin as page.ts)
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) views.get(e.target as HTMLCanvasElement)?.setEnabled(e.isIntersecting);
    },
    { rootMargin: "120px" },
  );

  function attachAll(): void {
    for (const c of present) {
      c.attachedAt = performance.now();
      c.chip.textContent = `${c.file.name} · loading…`;
      views.set(
        c.canvas,
        handle.attachFeatureView(c.canvas, {
          alphaOffsetDeg: feature?.view_angle_deg ?? 0,
          controls: liveControls,
          sogUrl: sogUrl(c.file.name),
          cameraEnvelope: envelope,
          pins: [],
          hotspotLayer: null,
        }),
      );
      // re-observing re-fires with this window's current visibility, so a
      // freshly attached view is paused if it sits offscreen
      io.unobserve(c.canvas);
      io.observe(c.canvas);
    }
  }

  // rotate_speed / zoom_speed are captured when the direct controls attach, so
  // the panel applies them by rebuilding the four views (splats reload).
  function reattachViews(): void {
    if (!viewsReady) return; // still loading; the new speeds apply at first attach
    for (const v of views.values()) v.dispose();
    views.clear();
    cams.clear();
    attachAll();
    startPoll();
  }

  // -------- camera discovery, sync + per-window stats -----------------------
  let poll: ReturnType<typeof setInterval> | null = null;
  function startPoll(): void {
    if (poll) clearInterval(poll);
    let ticks = 0;
    const stop = (): void => {
      if (poll) clearInterval(poll);
      poll = null;
    };
    poll = setInterval(() => {
      ticks++;
      if (!engine) return;
      const engineViews = (engine as unknown as { views?: EngineView[] }).views ?? [];
      for (const cell of present) {
        if (cams.has(cell.canvas)) continue;
        const view = engineViews.find((v) => v.target === cell.canvas);
        const raw = view?.camera;
        const cam = (Array.isArray(raw) ? raw[0] : raw) as ArcRotateCamera | undefined;
        if (!cam) continue;
        cams.set(cell.canvas, cam);

        const secs = ((performance.now() - cell.attachedAt) / 1000).toFixed(1);
        const scene = cam.getScene();
        const splat = scene.meshes.find((m) => m.getClassName() === "GaussianSplattingMesh");
        const count = splat ? (splat as unknown as { splatCount?: number }).splatCount : undefined;
        cell.chip.textContent =
          `${cell.file.name} · ${fmtMB(cell.file.size)}` +
          (count ? ` · ${fmtCount(count)} splats` : "") +
          ` · ${secs}s`;

        // the panel owns the cameras as soon as anything has been tuned;
        // until then an unauthored window keeps the viewer's own auto-fit and
        // the panel adopts its measured numbers (the fields show real values)
        // An unauthored window auto-fits itself: adopt window 1's measured
        // numbers into the fields the author has NOT set (window 1 specifically,
        // not whichever .sog decoded first — the fields must describe the window
        // the readout and "Fit" default to). Then push what they HAVE set.
        if (!envelope && cell.canvas === present[0].canvas) panel.setFrom(cam);
        panel.applyTo(cam);

        // follower: copy the leader's pose right before this scene renders —
        // zero-lag inside the frame, and the leader's own glide/limits still
        // come from the production control code untouched
        scene.onBeforeRenderObservable.add(() => {
          const lead = leaderCam();
          if (!sync || !lead || lead === cam) return;
          // auto-fit mode gives each window its own zoom limits and clip planes
          // (framed to its own splat's r90), which would clamp the copied pose
          // and silently diverge at the zoom extremes — unify with the leader.
          // In envelope mode all four are identical anyway, so this is a no-op.
          cam.lowerRadiusLimit = lead.lowerRadiusLimit;
          cam.upperRadiusLimit = lead.upperRadiusLimit;
          cam.minZ = lead.minZ;
          cam.maxZ = lead.maxZ;
          cam.alpha = lead.alpha;
          cam.beta = lead.beta;
          cam.radius = lead.radius;
          cam.target.copyFrom(lead.target);
        });
      }
      if (cams.size >= present.length) stop();
      else if (ticks > 400) {
        // ~60 s: something failed to load (see console); stop polling
        for (const cell of present) {
          if (!cams.has(cell.canvas)) cell.chip.textContent = `${cell.file.name} · FAILED — see console`;
        }
        stop();
      }
    }, 150);
  }

  viewsReady = true;
  attachAll();
  startPoll();

  setInterval(() => {
    readout.textContent =
      `${handle.engineKind} · ${Math.round(handle.fps())} fps · ${cams.size}/${present.length} windows`;
  }, 500);

  // exposed for scripted verification (mirrors page.ts's __viewerHandle);
  // cams() is in WINDOW order (null until that window's splat is ready)
  (window as unknown as { __compare?: unknown }).__compare = {
    cams: () => present.map((c) => cams.get(c.canvas) ?? null),
    leader: () => leaderCam(),
    syncEnabled: () => sync,
    camState: () => panel.state(),
    reattach: () => reattachViews(),
  };
}

boot().catch((err: unknown) => {
  statusEl.textContent = "compare tool failed to start — see console";
  console.error(err);
});
