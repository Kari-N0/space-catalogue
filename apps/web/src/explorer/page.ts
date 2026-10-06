// Concept 002 page — the engine explorer (/concept/rocket-engines/). A page
// type of its own, next to the locked concept template (catalogue/page.ts),
// which it does not touch: it renders its sections from
// content/explorers/rocket-engines.json and wires the explorer UI.
//
// Ported 1:1 from the approved standalone demo (js/main.js); markup, class
// names and copy are the demo's. Engine-free by contract: the Babylon viewer
// (./engineViewer) is reached ONLY through the dynamic import() below
// (CLAUDE.md viewer lazy boundary), after the page load event.

import { DIAGRAMS } from "./diagrams";
import type { EngineViewer } from "./engineViewer";
import type { EngineDef, EngineManifest, ExplorerContent, FlowColors, FlownOn, ViewMode } from "./types";

const CONTENT_URL = `${import.meta.env.BASE_URL}content/explorers/rocket-engines.json`;
/** Lighting environment for the 3D view (prefiltered IBL), under public/. */
const ENV_PATH = "assets/rocket-engines/env/studio.env";

const MODES: { id: ViewMode; label: string; key: string }[] = [
  { id: "explore", label: "Explore", key: "1" },
  { id: "explode", label: "Explode", key: "2" },
  { id: "cutaway", label: "Cutaway", key: "3" },
  { id: "flow", label: "Flow", key: "4" },
];
const MEDIA: Record<string, string> = { air: "Air", electric: "Electric power", xenon: "Xenon gas", electrons: "Electrons", ion_beam: "Ion beam", detonation: "Detonation wave", pressurant: "Pressurant", oxidizer: "Oxidizer", fuel: "Fuel", ox_rich_gas: "Oxygen-rich gas", turbine_gas: "Turbine gas", hot_gas: "Exhaust" };

/** querySelector for elements this page renders itself (present by construction). */
const $ = <T extends Element = HTMLElement>(sel: string, root: ParentNode = document): T => root.querySelector(sel) as T;
/** querySelector for elements that may legitimately be absent. */
const $opt = <T extends Element = HTMLElement>(sel: string, root: ParentNode = document): T | null => root.querySelector<T>(sel);

const HTML_ESCAPES: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" };
const esc = (s: unknown): string => String(s ?? "").replace(/[&<>"]/g, (c) => HTML_ESCAPES[c]);
const cssVar = (name: string, fallback: string): string => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
const pad2 = (n: number): string => String(n).padStart(2, "0");

/** Resolve a content/manifest asset path against the deploy base (same rule as
 *  catalogue/concept.ts assetUrl; kept local so this entry shares no chunk with
 *  the locked concept template). */
const assetUrl = (path: string): string => new URL(path, new URL(import.meta.env.BASE_URL, document.baseURI)).href;

// Each stream has a cold and a hot colour. Only the fuel (warming in the cooling channels) and the
// exhaust (cooling as it expands) change temperature, so the other two use one colour for both ends.
const FLOW_COLORS = (): FlowColors => ({
  pressurant: [cssVar("--flow-pressurant", "#4ade80"), cssVar("--flow-pressurant", "#4ade80")],
  oxidizer: [cssVar("--flow-oxidizer", "#60a5fa"), cssVar("--flow-oxidizer", "#60a5fa")],
  fuel: [cssVar("--flow-fuel", "#fb923c"), cssVar("--flow-fuel-warm", "#fde68a")],
  air: [cssVar("--flow-air-cold", "#e0f2fe"), cssVar("--flow-air-hot", "#fda4af")],
  electric: [cssVar("--flow-electric", "#fde047"), cssVar("--flow-electric", "#fde047")],
  detonation: [cssVar("--flow-detonation-edge", "#f0abfc"), cssVar("--flow-detonation", "#ffffff")],
  xenon: [cssVar("--flow-xenon", "#c4b5fd"), cssVar("--flow-xenon", "#c4b5fd")],
  electrons: [cssVar("--flow-electrons", "#86efac"), cssVar("--flow-electrons", "#86efac")],
  ion_beam: [cssVar("--flow-ion-beam-slow", "#0ea5e9"), cssVar("--flow-ion-beam", "#a5f3fc")],
  ox_rich_gas: [cssVar("--flow-ox-rich-gas-cool", "#2dd4bf"), cssVar("--flow-ox-rich-gas-hot", "#99f6e4")],
  turbine_gas: [cssVar("--flow-turbine-gas-cool", "#7c5cc4"), cssVar("--flow-turbine-gas-hot", "#c084fc")],
  hot_gas: [cssVar("--flow-hot-gas-cool", "#e2502c"), cssVar("--flow-hot-gas-hot", "#fff3cf")],
});

// Plausible custom events (goals). The inline stub in <head> queues calls
// until the async script arrives; optional chaining keeps this a no-op when
// the script is blocked or absent.
function trackEvent(name: string): void {
  (window as { plausible?: (event: string) => void }).plausible?.(name);
}

interface State {
  content: ExplorerContent | null;
  engine: EngineDef | null;
  manifest: EngineManifest | null;
  mode: ViewMode;
  part: string | null;
  photo: number | null;
  variant: string | null;
  viewer: EngineViewer | null;
}
const state: State = { content: null, engine: null, manifest: null, mode: "explore", part: null, photo: null, variant: null, viewer: null };

const errorText = (err: unknown): string => String(err instanceof Error && err.message ? err.message : err);
const setStatus = (text: string): void => {
  const s = $opt(".ex-status");
  if (s) s.textContent = text;
};

init().catch(fail);

function fail(err: unknown): void {
  console.error(err);
  document.documentElement.dataset.error = errorText(err);
  const s = $opt("#page-status") || $opt(".ex-status");
  if (s) s.textContent = "Could not load this page. Reload to try again.";
}

/**
 * Phone tier, by the same rule as the concept template (pickTier in viewer/tiering.ts): a touch device with a
 * small screen or little memory, or ?tier=mobile. Copied here on purpose: importing viewer/tiering from this
 * page makes the bundler re-split the shared chunks and rename every engine file of the template's build.
 */
function isPhoneTier(): boolean {
  const forced = new URLSearchParams(location.search).get("tier");
  if (forced) return forced === "mobile";
  const smallScreen = Math.min(screen.width, screen.height) < 820;
  const lowMemory = ((navigator as Navigator & { deviceMemory?: number }).deviceMemory ?? 8) <= 6;
  return matchMedia("(pointer: coarse)").matches && (smallScreen || lowMemory);
}

/** Concept pages start their 3D view after the page load event (CLAUDE.md viewer rules). */
function pageLoaded(): Promise<void> {
  return new Promise((resolve) => {
    const start = (): void => void setTimeout(resolve, 0);
    if (document.readyState === "complete") start();
    else addEventListener("load", start, { once: true });
  });
}

async function init(): Promise<void> {
  // always revalidate: GitHub Pages caches JSON for up to 10 min, which would
  // make freshly-pushed content edits invisible on a plain refresh
  const res = await fetch(CONTENT_URL, { cache: "no-cache" });
  if (!res.ok) throw new Error(`failed to load ${CONTENT_URL}: HTTP ${res.status}`);
  const content = (state.content = (await res.json()) as ExplorerContent);
  document.title = `${content.page_title} · FarsideLab`;
  $("#footer-label").textContent = content.footer_label;
  $("#app").innerHTML = renderPage(content);
  const poster = $opt(".hero-poster");
  if (poster) poster.addEventListener("error", () => poster.remove());
  // autoplay can be denied (iOS Low Power Mode, data saver) — a paused video
  // would sit as a dead play glyph over the poster, so fall back to the
  // poster underneath, same as the landing and concept heroes.
  const video = $opt<HTMLVideoElement>(".hero-video");
  if (video) {
    const posterFallback = (): void => video.remove();
    video.addEventListener("error", posterFallback);
    requestAnimationFrame(() => void video.play().catch(posterFallback));
  }
  // The sections did not exist when the browser first looked for the #hash target, so jump there now.
  if (location.hash.length > 1) document.getElementById(location.hash.slice(1))?.scrollIntoView({ behavior: "auto" });

  setStatus("Loading model…");
  await pageLoaded();
  // the lazy boundary — the first Babylon bytes cross the network here
  const { EngineViewer, isSupported } = await import("./engineViewer");
  if (!isSupported()) {
    setStatus("This view needs WebGL 2. Try a current Chrome, Edge or Firefox.");
    return;
  }

  const q = new URLSearchParams(location.search);
  const engines = content.explorer.engines;
  const first = engines.find((e) => e.id === q.get("engine") && e.status === "live") || engines.find((e) => e.status === "live");
  const wantedMode = MODES.find((m) => m.id === q.get("mode"));
  if (wantedMode) state.mode = wantedMode.id;

  const canvas = $<HTMLCanvasElement>("#ex-canvas");
  const viewer = (state.viewer = new EngineViewer(canvas, {
    envUrl: assetUrl(ENV_PATH),
    flowColors: FLOW_COLORS(),
    highlight: cssVar("--chip-blue-text", "#60a5fa"),
    onStatus: setStatus,
    onHover,
    onSelect,
  }));
  viewer.mode = state.mode;

  // analytics goal "Enter 3D" (same definition as the concept template):
  // the first real interaction with the 3D canvas, once per page view
  let entered3d = false;
  const enter3d = (): void => {
    if (entered3d) return;
    entered3d = true;
    trackEvent("Enter 3D");
  };
  canvas.addEventListener("pointerdown", enter3d);
  canvas.addEventListener("wheel", enter3d, { passive: true });

  wireUi(viewer);
  await loadEngine(first);

  const part = q.get("part");
  if (part && viewer.byId.has(part)) viewer.select(part);
  const cam = (q.get("cam") || "").split(",").map(Number);
  if (cam.length === 3 && cam.every(Number.isFinite)) viewer.setCamera(cam[0], cam[1], cam[2]);
  // exposed for scripted verification
  (window as unknown as { __c002?: State }).__c002 = state;
  document.documentElement.dataset.ready = "1";
}

// ------------------------------------------------------------------ page sections
function renderPage(c: ExplorerContent): string {
  const ex = c.explorer;
  const rail = ex.groups
    .map((g) => {
      const items = ex.engines
        .filter((e) => e.group === g.id)
        .map((e) => `<button class="ex-engine" data-engine="${esc(e.id)}" ${e.status === "live" ? "" : "disabled"}>
            <span class="ref-label">${esc(e.ref)}</span><span>${esc(e.title)}</span>${e.status === "live" ? "" : "<small>In build</small>"}</button>`)
        .join("");
      return `<h3 class="ref-label">${esc(g.title)}</h3>${items}`;
    })
    .join("");
  const sources = c.sources.items
    .map((s) => `<div class="source-row"><span class="idx">${esc(s.label)}</span><span>${s.url ? `<a href="${esc(s.url)}" rel="noopener">${esc(s.text)}</a>` : esc(s.text)}</span></div>`)
    .join("");
  const poster = c.hero.poster_image ? esc(assetUrl(c.hero.poster_image)) : "";
  // a11y: reduced-motion visitors get the poster instead of the autoplaying
  // video whenever a poster exists (and never download the video)
  // phones get the 720p encode when the content file provides one
  const heroVideo = (isPhoneTier() ? c.hero.video_mobile : null) ?? c.hero.video;
  const withVideo = !!heroVideo && !(poster && matchMedia("(prefers-reduced-motion: reduce)").matches);
  // the hero status chip is optional: no `hero.status` in the content file, no chip
  const statusChip = c.hero.status ? `<span class="status-chip"><span class="dot" aria-hidden="true"></span>${esc(c.hero.status)}</span>` : "";

  return `
  <section class="hero">
    ${poster ? `<img class="hero-poster" src="${poster}" alt="" aria-hidden="true">` : ""}
    ${withVideo && heroVideo ? `<video class="hero-video" src="${esc(assetUrl(heroVideo))}"${poster ? ` poster="${poster}"` : ""} autoplay muted loop playsinline preload="metadata" aria-hidden="true" tabindex="-1"></video>` : ""}
    <div class="hero-content"><div class="container">
      <div class="hero-meta"><span class="ref-label">${esc(c.hero.label)}</span>${statusChip}</div>
      <h1 class="hero-title"><span class="line-1">${esc(c.hero.title_line_1)}</span><span class="line-2">${esc(c.hero.title_line_2)}</span></h1>
      <p class="hero-era">${esc(c.hero.era_line)}</p>
      <a class="pill-primary" href="#explorer">${esc(c.hero.button_text)}</a>
    </div></div>
  </section>

  <section class="section" id="explorer" aria-labelledby="kicker-explorer">
    <div class="container container--wide">
      <div class="section-head"><h2 class="kicker" id="kicker-explorer">${esc(ex.heading)}</h2></div>
      <div class="explorer" id="ex">
        <nav class="ex-rail" aria-label="Engine types">${rail}</nav>
        <div class="ex-view">
          <canvas id="ex-canvas" aria-label="3D view of the selected engine"></canvas>
          <div class="ex-legend" hidden></div>
          <p class="ex-caption" hidden></p>
          <div class="ex-corner">
            <button class="ex-chip" data-act="link">Copy view link</button>
            <button class="ex-chip" data-act="help"><kbd>?</kbd>Help</button>
            <button class="ex-chip" data-act="fs"><kbd>F</kbd>Fullscreen</button>
          </div>
          <div class="ex-tip" hidden></div>
          <p class="ex-status" role="status"></p>
          <div class="ex-help" hidden><div class="ex-help-card">
            <h2>Controls</h2>
            <dl>
              <dt>Drag</dt><dd>Orbit</dd><dt>Right-drag</dt><dd>Pan</dd><dt>Scroll</dt><dd>Zoom</dd>
              <dt>Click</dt><dd>Inspect a part</dd><dt>Double-click</dt><dd>Reset the view</dd>
              <dt>1 – 4</dt><dd>Explore, Explode, Cutaway, Flow</dd>
              <dt>← →</dt><dd>Previous or next part</dd>
              <dt>H</dt><dd>Hide or show the side panels</dd><dt>F</dt><dd>Fullscreen</dd><dt>Esc</dt><dd>Clear the selection</dd>
            </dl>
            <button class="ex-chip" data-act="help">Close</button>
          </div></div>
        </div>
        <div class="ex-bar">
          <div class="ex-modes" role="group" aria-label="View mode">
            ${MODES.map((m) => `<button class="ex-chip" data-mode="${m.id}" aria-pressed="false"><kbd>${m.key}</kbd>${m.label}</button>`).join("")}
          </div>
          <label class="ex-slider" hidden><span class="ref-label">Spread</span><input type="range" min="0" max="100" step="1" value="100" aria-label="How far the parts spread apart"></label>
          <span class="ex-hint">Double-click resets the view</span>
        </div>
        <aside class="ex-panel" aria-label="Engine and part details"></aside>
        <div class="ex-lightbox" hidden></div>
      </div>
      <p class="stage-note">${esc(ex.note)}</p>
    </div>
  </section>

  <section class="section" aria-labelledby="kicker-sources">
    <div class="container">
      <div class="section-head"><h2 class="kicker" id="kicker-sources">${esc(c.sources.heading)}</h2></div>
      <p class="sources-intro">${esc(c.sources.intro)}</p>
      ${sources}
    </div>
  </section>`;
}

// ------------------------------------------------------------------ explorer
async function loadEngine(def: EngineDef | undefined): Promise<void> {
  const viewer = state.viewer;
  if (!def || !viewer) return;
  state.engine = def;
  state.part = null;
  document.querySelectorAll<HTMLElement>(".ex-engine").forEach((b) => b.setAttribute("aria-current", String(b.dataset.engine === def.id)));
  // narrow windows: the rail is one sideways-scrolling row, so bring the current engine into view (the desktop column is left alone)
  const current = document.querySelector<HTMLElement>('.ex-engine[aria-current="true"]');
  const railEl = current?.closest<HTMLElement>(".ex-rail");
  if (current && railEl && matchMedia("(max-width: 1023px)").matches) {
    railEl.scrollLeft += current.getBoundingClientRect().left - railEl.getBoundingClientRect().left - (railEl.clientWidth - current.offsetWidth) / 2;
  }
  try {
    state.manifest = await viewer.load({ model: assetUrl(def.model), manifest: assetUrl(def.manifest) });
  } catch (err) {
    console.error(err);
    document.documentElement.dataset.error = errorText(err);
    setStatus("The model did not load. Reload the page to try again.");
    return;
  }
  if (!state.variant) state.variant = new URLSearchParams(location.search).get("variant");
  renderFlowInfo();
  setMode(state.mode, true);
  renderPanel();
}

// Legend, caption and, for engines with more than one operating mode, the switch between them.
function renderFlowInfo(): void {
  const man = state.manifest;
  if (!man || !state.viewer) return;
  const fm = man.flow_model || {};
  const variants = fm.variants || [];
  if (!variants.some((v) => v.id === state.variant)) state.variant = variants.length ? variants[0].id : null;
  const cur = variants.find((v) => v.id === state.variant);
  const order = Object.keys(MEDIA);
  const sw = variants.length
    ? `<span class="ex-variants" role="group" aria-label="Operating mode">${variants.map((v) => `<button class="ex-chip" data-variant="${esc(v.id)}" aria-pressed="${v.id === state.variant}">${esc(v.label)}</button>`).join("")}</span>`
    : "";
  $(".ex-legend").innerHTML = sw + (man.flows || [])
    .filter((f) => !f.variant || f.variant === state.variant)
    .sort((a, b) => order.indexOf(a.medium) - order.indexOf(b.medium))
    .map((f) => `<span class="m-${f.medium.replace(/_/g, "-")}"><i></i>${esc(f.label || MEDIA[f.medium] || f.medium)}</span>`)
    .join("");
  const gas = fm.hot_gas;
  $(".ex-caption").textContent = (cur && cur.caption) || fm.caption ||
    "Each streak moves at the local flow speed, on a compressed scale." +
    (gas ? ` Exhaust colour follows temperature: about ${gas.assumed_chamber_temp_K} K in the chamber, ${gas.exit_temp_K} K at the nozzle exit, leaving at ${(gas.exit_speed_ms / 1000).toFixed(1)} km/s (1-D estimate).` : "");
  state.viewer.setFlowVariant(state.variant);
}

function setMode(mode: ViewMode, instant = false): void {
  if (!state.viewer) return;
  state.mode = mode;
  document.querySelectorAll<HTMLElement>("[data-mode]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
  $(".ex-slider").hidden = mode !== "explode";
  $(".ex-legend").hidden = mode !== "flow";
  $(".ex-caption").hidden = mode !== "flow";
  state.viewer.setMode(mode, { instant });
  syncUrl();
}

function onHover(id: string | null, pos: { x: number; y: number } | null): void {
  const tip = $(".ex-tip");
  const part = id && state.viewer ? state.viewer.byId.get(id) : null;
  if (part && pos) {
    tip.textContent = part.def.title;
    tip.style.left = pos.x + "px";
    tip.style.top = pos.y + "px";
    tip.hidden = false;
  } else {
    tip.hidden = true;
  }
  markFocus(id || state.part);
}

function onSelect(id: string | null): void {
  state.part = id;
  renderPanel();
  markFocus(id);
  syncUrl();
}

// The diagram's lines stay thin, but each shape gets an invisible, much wider twin on top of it,
// so pointing at a line does not have to be exact.
function widenDiagramHits(): void {
  const svg = $opt<SVGSVGElement>(".ex-diagram");
  if (!svg || svg.dataset.hits) return;
  svg.dataset.hits = "1";
  svg.querySelectorAll("g[data-part]").forEach((g) => {
    [...g.children].forEach((el) => {
      if (!/^(path|rect|circle)$/.test(el.tagName)) return;
      const hit = el.cloneNode(false) as Element;
      hit.setAttribute("class", "hit");
      g.appendChild(hit);
    });
  });
}

function markFocus(id: string | null): void {
  const svg = $opt<SVGSVGElement>(".ex-diagram");
  if (svg) {
    svg.classList.toggle("has-focus", !!id);
    svg.querySelectorAll<SVGElement>("[data-part]").forEach((g) => g.classList.toggle("on", !!id && (g.dataset.part ?? "").split(" ").includes(id)));
  }
  document.querySelectorAll<HTMLElement>(".ex-parts button").forEach((b) => b.classList.toggle("on", b.dataset.part === id));
}

function renderPanel(): void {
  const panel = $(".ex-panel");
  const man = state.manifest;
  const def = state.engine;
  const viewer = state.viewer;
  if (!man || !def || !viewer || !state.content) return;
  const parts = viewer.parts;
  if (state.part) {
    const i = parts.findIndex((p) => p.id === state.part);
    const d = parts[i].def;
    panel.innerHTML = `
      <button class="ex-chip ex-back" data-act="back">All parts</button><br>
      <span class="ref-label">Part ${pad2(i + 1)} of ${parts.length}</span>
      <h2>${esc(d.title)}</h2>
      <p>${esc(d.description)}</p>
      <div class="ex-nav"><button class="ex-chip" data-act="prev"><kbd>←</kbd>Previous</button><button class="ex-chip" data-act="next">Next<kbd>→</kbd></button></div>`;
    panel.scrollTop = 0;
    return;
  }
  const group = state.content.explorer.groups.find((g) => g.id === def.group);
  const pub = (man.reference && man.reference.published) || {};
  const rows = ([
    ["Thrust, sea level", pub.thrust_sl_kN, "kN"],
    ["Thrust, vacuum", pub.thrust_vac_kN, "kN"],
    ["Specific impulse, sea level", pub.isp_sl_s, "s"],
    [pub.isp_sl_s ? "Specific impulse, vacuum" : "Specific impulse", pub.isp_vac_s, "s"],
    ["Chamber pressure", pub.chamber_pressure_bar, "bar"],
    ["Expansion ratio", pub.expansion_ratio, ": 1"],
    ["Mixture ratio", pub.mixture_ratio, ""],
    ["Propellants", pub.propellants, ""],
    ["Dry mass", pub.dry_mass_kg, "kg"],
    ["Length", pub.length_m, "m"],
    [pub.length_m ? "Diameter" : "Nozzle exit diameter", pub.max_diameter_m, "m"],
    ...(pub.extra || []).map(([label, value]) => [label, value, ""]),
  ] as [string, string | number | null | undefined, string][]).filter((r) => r[1] !== undefined && r[1] !== null);
  panel.innerHTML = `
    <span class="ref-label">${esc(def.ref)} — ${esc(group ? group.title : "")}</span>
    <h2>${esc(man.title)}</h2>
    ${def.summary ? `<p>${esc(def.summary)}</p>` : ""}
    <p>${esc(def.description ?? man.description)}</p>
    ${renderFlownOn(def.flown_on)}
    ${DIAGRAMS[def.id] ? `<span class="ref-label ex-sub">Cycle</span>${DIAGRAMS[def.id]}` : ""}
    ${rows.length && man.reference ? `<span class="ref-label ex-sub">Reference engine</span>
      <p>${esc(man.reference.engine)}</p>
      <dl class="ex-spec" style="margin-top:10px">${rows.map((r) => `<dt>${esc(r[0])}</dt><dd>${esc(r[1])}${r[2] ? " " + esc(r[2]) : ""}</dd>`).join("")}</dl>
      <p class="ex-fine">${esc(man.reference.note || "Outer dimensions match the published figures. The internal layout is representative.")}</p>` : ""}
    <span class="ref-label ex-sub">Parts</span>
    <ol class="ex-parts">${parts.map((p, i) => `<li><button data-part="${esc(p.id)}"><span class="ref-label">${pad2(i + 1)}</span><span>${esc(p.def.title)}</span></button></li>`).join("")}</ol>`;
}

// Real photos of the vehicles the reference engine flew on. Each thumbnail opens a larger view.
function renderFlownOn(f: FlownOn | undefined): string {
  if (!f) return "";
  if (!f.photos || !f.photos.length) return `<span class="ref-label ex-sub">${esc(f.heading || "Flown on")}</span><p>${esc(f.text)}</p>`;
  return `<span class="ref-label ex-sub">${esc(f.heading || "Flown on")}</span>
    <p>${esc(f.text)}</p>
    <div class="ex-photos">${f.photos.map((p, i) => `<button class="ex-photo" data-photo="${i}" aria-label="Enlarge photo: ${esc(p.alt)}"><img src="${esc(assetUrl(p.src))}" alt="${esc(p.alt)}" loading="lazy"${p.position ? ` style="object-position:${esc(p.position)}"` : ""}></button>`).join("")}</div>
    <p class="ex-fine">Photos: ${esc([...new Set(f.photos.map((p) => p.credit.split(/[,/]/)[0].trim()))].join(", "))}. Select one to enlarge.</p>`;
}

function showPhoto(i: number | null): void {
  const box = $(".ex-lightbox");
  const photos = (state.engine && state.engine.flown_on && state.engine.flown_on.photos) || [];
  if (i === null || !photos.length) {
    box.hidden = true;
    state.photo = null;
    return;
  }
  const n = photos.length;
  const p = photos[(state.photo = ((i % n) + n) % n)];
  box.innerHTML = `<figure>
      <img src="${esc(assetUrl(p.src))}" alt="${esc(p.alt)}">
      <figcaption>
        <p>${esc(p.caption)}</p>
        <p class="ref-label">Credit — ${esc(p.credit)} / ${esc(p.license)} / <a href="${esc(p.source_url)}" rel="noopener" target="_blank">Source</a></p>
        <div class="ex-nav">
          <button class="ex-chip" data-act="photo-prev"><kbd>←</kbd>Previous</button>
          <button class="ex-chip" data-act="photo-next">Next<kbd>→</kbd></button>
          <button class="ex-chip" data-act="photo-close"><kbd>Esc</kbd>Close</button>
        </div>
      </figcaption>
    </figure>`;
  box.hidden = false;
}

function syncUrl(): void {
  if (!state.engine) return;
  const q = new URLSearchParams({ engine: state.engine.id, mode: state.mode });
  if (state.part) q.set("part", state.part);
  if (state.variant) q.set("variant", state.variant);
  history.replaceState(null, "", `${location.pathname}?${q}${location.hash}`);
}

function wireUi(v: EngineViewer): void {
  const ex = $("#ex");

  ex.addEventListener("click", (e) => {
    const t = (e.target as Element).closest<HTMLButtonElement>("button");
    if (!t || !ex.contains(t)) return;
    if (t.dataset.variant) {
      state.variant = t.dataset.variant;
      renderFlowInfo();
      syncUrl();
      return;
    }
    if (t.dataset.engine) void loadEngine(state.content?.explorer.engines.find((x) => x.id === t.dataset.engine));
    else if (t.dataset.mode) setMode(t.dataset.mode as ViewMode);
    else if (t.dataset.photo) showPhoto(Number(t.dataset.photo));
    else if (t.dataset.act === "photo-prev") showPhoto((state.photo ?? 0) - 1);
    else if (t.dataset.act === "photo-next") showPhoto((state.photo ?? 0) + 1);
    else if (t.dataset.act === "photo-close") showPhoto(null);
    else if (t.dataset.part) v.select(t.dataset.part);
    else if (t.dataset.act === "back") v.select(null);
    else if (t.dataset.act === "prev") v.step(-1);
    else if (t.dataset.act === "next") v.step(1);
    else if (t.dataset.act === "help") toggleHelp();
    else if (t.dataset.act === "fs") toggleFullscreen();
    else if (t.dataset.act === "link") void copyLink(t);
  });

  new MutationObserver(widenDiagramHits).observe($(".ex-panel"), { childList: true });
  widenDiagramHits();

  // Hovering a row in the parts list or a shape in the cycle diagram highlights the part in 3D.
  ex.addEventListener("pointerover", (e) => {
    const el = (e.target as Element).closest<HTMLElement | SVGElement>(".ex-panel [data-part]");
    if (el) v.hover((el.dataset.part ?? "").split(" ")[0]);
  });
  ex.addEventListener("pointerout", (e) => {
    if ((e.target as Element).closest(".ex-panel [data-part]")) v.hover(null);
  });
  $(".ex-panel").addEventListener("click", (e) => {
    const g = (e.target as Element).closest<SVGElement>(".ex-diagram [data-part]");
    if (g) v.select((g.dataset.part ?? "").split(" ")[0]);
  });

  $(".ex-lightbox").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) showPhoto(null); // click on the backdrop
  });
  $<HTMLInputElement>(".ex-slider input").addEventListener("input", (e) => v.setExplode(Number((e.target as HTMLInputElement).value) / 100));

  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey || (e.target instanceof Element && /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName))) return;
    if (state.photo !== null && state.photo !== undefined) {
      if (e.key === "Escape") showPhoto(null);
      else if (e.key === "ArrowRight") showPhoto(state.photo + 1);
      else if (e.key === "ArrowLeft") showPhoto(state.photo - 1);
      return;
    }
    const m = MODES.find((x) => x.key === e.key);
    if (m) setMode(m.id);
    else if (e.key === "h" || e.key === "H") {
      ex.classList.toggle("panels-hidden");
      setTimeout(() => v.resetView(), 60); // the canvas changed width, so frame the engine again
    } else if (e.key === "f" || e.key === "F") toggleFullscreen();
    else if (e.key === "?") toggleHelp();
    else if (e.key === "Escape") {
      if (!$(".ex-help").hidden) toggleHelp();
      else v.select(null);
    } else if (e.key === "ArrowRight") v.step(1);
    else if (e.key === "ArrowLeft") v.step(-1);
  });
}

function toggleHelp(): void {
  const h = $(".ex-help");
  h.hidden = !h.hidden;
}

function toggleFullscreen(): void {
  if (document.fullscreenElement) void document.exitFullscreen();
  else void $("#ex").requestFullscreen?.();
}

async function copyLink(btn: HTMLElement): Promise<void> {
  if (!state.engine || !state.viewer) return;
  const q = new URLSearchParams({ engine: state.engine.id, mode: state.mode });
  if (state.part) q.set("part", state.part);
  q.set("cam", state.viewer.getCamera().join(","));
  const url = `${location.origin}${location.pathname}?${q}#explorer`;
  const label = btn.textContent;
  try {
    await navigator.clipboard.writeText(url);
    btn.textContent = "Link copied";
  } catch {
    btn.textContent = "Copy failed";
  }
  setTimeout(() => (btn.textContent = label), 1600);
}
