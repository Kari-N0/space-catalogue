// Concept-page template renderer — the LOCKED base template (Kari 2026-07-13).
// Reads content/concepts/<id>.json (?id= query, default lunar-base), builds
// every section from it, and wires the live viewer. Zero per-concept code:
// a new concept page is a new JSON file only.

import { assetUrl, loadConceptPage, type ArticleBlock, type ConceptPage, type Hotspot } from "./concept";
import { pickTier } from "../viewer/tiering";
import type { FeatureViewHandle, ViewerHandle } from "../viewer/types";

const app = document.getElementById("app") as HTMLElement;

/* ---------------- tiny DOM helpers (textContent only — XSS-safe) --------- */

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

function section(labelId: string, kicker: string): { root: HTMLElement; container: HTMLElement } {
  const root = el("section", "section");
  root.setAttribute("aria-labelledby", labelId);
  const container = el("div", "container");
  const head = el("div", "section-head");
  const k = el("span", "kicker", kicker);
  k.id = labelId;
  head.appendChild(k);
  container.appendChild(head);
  root.appendChild(container);
  return { root, container };
}

function statusChip(text: string): HTMLElement {
  const chip = el("span", "status-chip");
  const dot = el("span", "dot");
  dot.setAttribute("aria-hidden", "true");
  chip.append(dot, document.createTextNode(text));
  return chip;
}

/* ---------------- section renderers -------------------------------------- */

function renderHero(data: ConceptPage): HTMLElement {
  const { hero } = data.page;
  const { assets } = data.viewer;
  const root = el("section", "hero");
  root.setAttribute("aria-label", "Concept hero");

  if (assets.hero_video) {
    const video = el("video", "hero-media");
    video.autoplay = true;
    video.muted = true;
    video.loop = true;
    video.playsInline = true;
    if (assets.poster) video.poster = assetUrl(assets.poster);
    video.setAttribute("aria-hidden", "true");
    const source = el("source");
    source.src = assetUrl(assets.hero_video);
    source.type = "video/mp4";
    video.appendChild(source);
    root.appendChild(video);
  } else {
    root.classList.add("no-video");
  }
  if (assets.poster) {
    const poster = el("img", "hero-poster");
    poster.src = assetUrl(assets.poster);
    poster.alt = `Still render — ${data.viewer.title}`;
    root.appendChild(poster);
  }

  const content = el("div", "hero-content");
  const container = el("div", "container");
  const meta = el("div", "hero-meta");
  meta.append(el("span", "ref-label", hero.label), statusChip(hero.status));
  const title = el("h1", "hero-title");
  title.append(el("span", "line-1", hero.title_line_1), el("span", "line-2", hero.title_line_2));
  const era = el("p", "hero-era", hero.era_line);
  const cta = el("a", "pill-primary", hero.button_text);
  cta.href = "#live-view";
  container.append(meta, title, era, cta);
  content.appendChild(container);
  root.appendChild(content);
  return root;
}

interface StageRefs {
  canvas: HTMLCanvasElement;
  overlay: HTMLElement;
  poster: HTMLElement | null;
  status: HTMLElement;
  stage: HTMLElement;
  fsBtn: HTMLButtonElement;
  fsLabel: HTMLElement;
  popup: HTMLElement;
  popupImage: HTMLImageElement;
  popupTitle: HTMLElement;
  popupBody: HTMLElement;
  popupClose: HTMLButtonElement;
}

function renderLiveView(data: ConceptPage): { root: HTMLElement; refs: StageRefs } {
  const { live_view } = data.page;
  const { root, container } = section("kicker-live", live_view.heading);
  root.id = "live-view";

  const stage = el("div", "stage");
  const canvas = el("canvas");
  canvas.setAttribute("aria-label", `Interactive 3D view — ${data.viewer.title}`);
  stage.appendChild(canvas);

  let poster: HTMLElement | null = null;
  if (data.viewer.assets.poster) {
    const img = el("img", "stage-poster");
    img.src = assetUrl(data.viewer.assets.poster);
    img.alt = "";
    img.setAttribute("aria-hidden", "true");
    stage.appendChild(img);
    poster = img;
  }

  const overlay = el("div", "overlay");
  stage.appendChild(overlay);

  const fsBtn = el("button", "stage-fs");
  fsBtn.type = "button";
  fsBtn.hidden = true;
  const fsDot = el("span", "dot");
  fsDot.setAttribute("aria-hidden", "true");
  const fsLabel = el("span", undefined, "Fullscreen");
  fsBtn.append(fsDot, fsLabel);
  stage.appendChild(fsBtn);

  const status = el("p", "stage-status", "loading 3D…");
  status.setAttribute("role", "status");
  stage.appendChild(status);

  const popup = el("aside", "hotspot-popup");
  popup.setAttribute("role", "dialog");
  const popupClose = el("button", "popup-close", "Close");
  popupClose.type = "button";
  const popupImage = el("img");
  popupImage.hidden = true;
  const popupTitle = el("h3");
  const popupBody = el("p");
  popup.append(popupClose, popupImage, popupTitle, popupBody);
  stage.appendChild(popup);

  container.appendChild(stage);
  container.appendChild(el("p", "stage-note", live_view.note));

  return {
    root,
    refs: { canvas, overlay, poster, status, stage, fsBtn, fsLabel, popup, popupImage, popupTitle, popupBody, popupClose },
  };
}

function renderOverview(data: ConceptPage): { root: HTMLElement; featureCanvases: HTMLCanvasElement[] } {
  const { overview } = data.page;
  const { root, container } = section("kicker-overview", overview.heading);
  container.appendChild(el("p", "overview-lead", overview.intro));

  const featureCanvases: HTMLCanvasElement[] = [];
  for (const f of overview.features) {
    const row = el("div", "feature");
    const media = el("div", "feature-media");
    const canvas = el("canvas", "feature-canvas");
    canvas.setAttribute("aria-label", `Live 3D detail view: ${f.title}`);
    media.append(canvas, el("span", "scrim-chip", "Live — Sample Scene"));
    const copy = el("div", "feature-copy");
    copy.append(el("span", "idx", f.label), el("h3", undefined, f.title), el("p", undefined, f.text));
    row.append(media, copy);
    container.appendChild(row);
    featureCanvases.push(canvas);
  }
  return { root, featureCanvases };
}

function renderArticle(data: ConceptPage): HTMLElement {
  const { article } = data.page;
  const { root, container } = section("kicker-specs", article.heading);
  const body = el("div", "article");
  for (const block of article.blocks) {
    body.appendChild(renderArticleBlock(block));
  }
  container.appendChild(body);
  return root;
}

function renderArticleBlock(block: ArticleBlock): HTMLElement {
  if (block.type === "chapter") return el("h3", undefined, block.text);
  if (block.type === "paragraph") return el("p", undefined, block.text);
  const figure = el("figure");
  const img = el("img");
  img.src = assetUrl(block.file);
  img.alt = block.caption;
  figure.append(img, el("figcaption", undefined, block.caption));
  return figure;
}

function renderSources(data: ConceptPage): HTMLElement {
  const { sources } = data.page;
  const { root, container } = section("kicker-sources", sources.heading);
  const list = el("div");
  list.setAttribute("role", "list");
  list.setAttribute("aria-label", "Source references");
  for (const s of sources.items) {
    const row = el("div", "source-row");
    row.setAttribute("role", "listitem");
    row.append(el("span", "idx", s.label), el("span", undefined, `— ${s.text}`));
    list.appendChild(row);
  }
  container.appendChild(list);
  return root;
}

function renderSignup(data: ConceptPage): HTMLElement {
  const { signup } = data.page;
  const root = el("section", "notify");
  root.setAttribute("aria-labelledby", "notify-heading");
  const container = el("div", "container");
  const kicker = el("span", "kicker", signup.kicker);
  const title = el("h2", "notify-title");
  title.id = "notify-heading";
  title.append(
    document.createTextNode(signup.heading_line_1),
    el("span", "tone-2", signup.heading_line_2),
  );
  const form = el("form", "notify-form");
  form.action = "#";
  const fieldset = el("fieldset");
  fieldset.disabled = true;
  const label = el("label", undefined, signup.label);
  label.htmlFor = "notify-email";
  const row = el("div", "field-row");
  const input = el("input");
  input.type = "email";
  input.id = "notify-email";
  input.name = "email";
  input.placeholder = signup.placeholder;
  input.autocomplete = "email";
  const button = el("button", "pill-primary", signup.button);
  button.type = "submit";
  row.append(input, button);
  fieldset.append(label, row);
  form.appendChild(fieldset);
  container.append(kicker, title, form, el("p", "notify-note", signup.note));
  root.appendChild(container);
  return root;
}

/* ---------------- viewer wiring ------------------------------------------ */

function wireViewer(data: ConceptPage, refs: StageRefs, featureCanvases: HTMLCanvasElement[]): void {
  let handle: ViewerHandle | null = null;
  let lastPin: HTMLElement | null = null;

  const openPopup = (h: Hotspot): void => {
    lastPin = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    if (h.image) {
      refs.popupImage.src = assetUrl(h.image);
      refs.popupImage.alt = h.title;
      refs.popupImage.hidden = false;
    } else {
      refs.popupImage.hidden = true;
      refs.popupImage.removeAttribute("src");
    }
    refs.popupTitle.textContent = h.title;
    refs.popupBody.textContent = h.body;
    refs.popup.setAttribute("data-open", "");
    refs.popupClose.focus();
  };
  const closePopup = (): void => {
    refs.popup.removeAttribute("data-open");
    lastPin?.focus();
    lastPin = null;
  };
  refs.popupClose.addEventListener("click", closePopup);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && refs.popup.hasAttribute("data-open")) closePopup();
  });

  if (refs.stage.requestFullscreen) {
    refs.fsBtn.hidden = false;
    refs.fsBtn.addEventListener("click", () => {
      if (document.fullscreenElement) void document.exitFullscreen();
      else void refs.stage.requestFullscreen();
    });
    document.addEventListener("fullscreenchange", () => {
      // swap only the label span — the pulsing dot must survive the change
      refs.fsLabel.textContent = document.fullscreenElement ? "Exit Fullscreen" : "Fullscreen";
    });
  }

  const attachFeatureViews = (h: ViewerHandle): void => {
    const views = new Map<HTMLCanvasElement, FeatureViewHandle>();
    for (const [i, c] of featureCanvases.entries()) {
      try {
        views.set(c, h.attachFeatureView(c, { alphaOffsetDeg: data.page.overview.features[i]?.view_angle_deg ?? 0 }));
      } catch (err) {
        console.error("feature view failed", err);
      }
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) views.get(e.target as HTMLCanvasElement)?.setEnabled(e.isIntersecting);
      },
      { rootMargin: "120px" },
    );
    for (const c of views.keys()) io.observe(c);
  };

  const init3d = async (): Promise<void> => {
    try {
      const profile = pickTier(new URLSearchParams(location.search));
      // the lazy boundary — the first Babylon bytes cross the network here
      const { loadViewer } = await import("../viewer/loadViewer");
      handle = await loadViewer({
        canvas: refs.canvas,
        hotspotLayer: refs.overlay,
        concept: data.viewer,
        profile,
        onProgress: (p) => {
          refs.status.textContent =
            p.phase === "download" && p.ratio != null
              ? `loading scene… ${(p.ratio * 100).toFixed(0)}%`
              : p.phase === "ready"
                ? ""
                : `${p.phase}…`;
        },
        onHotspotSelect: openPopup,
      });
      refs.poster?.remove();
      attachFeatureViews(handle);
    } catch (err) {
      refs.status.textContent = "could not load the 3D scene";
      console.error(err);
    }
  };

  // concept pages auto-init the viewer after the page load event
  const start = () => setTimeout(() => void init3d(), 0);
  if (document.readyState === "complete") start();
  else addEventListener("load", start, { once: true });
  addEventListener("pagehide", () => handle?.dispose());

  // exposed for scripted verification
  (window as unknown as { __viewerHandle?: () => ViewerHandle | null }).__viewerHandle = () => handle;
}

/* ---------------- boot ---------------------------------------------------- */

async function boot(): Promise<void> {
  const pageStatus = document.getElementById("page-status");
  try {
    const id = new URLSearchParams(location.search).get("id") ?? "lunar-base";
    if (!/^[a-z0-9-]+$/i.test(id)) throw new Error(`invalid concept id "${id}"`);
    const data = await loadConceptPage(`${import.meta.env.BASE_URL}content/concepts/${id}.json`);

    document.title = `${data.page.page_title} — Space Engineering Catalogue`;
    const footerLabel = document.getElementById("footer-label");
    if (footerLabel) footerLabel.textContent = data.page.footer_label;

    const hero = renderHero(data);
    const live = renderLiveView(data);
    const overview = renderOverview(data);
    const article = renderArticle(data);
    const sources = renderSources(data);
    const signup = renderSignup(data);

    app.replaceChildren(hero, live.root, overview.root, article, sources, signup);
    wireViewer(data, live.refs, overview.featureCanvases);
  } catch (err) {
    if (pageStatus) pageStatus.textContent = "could not load this concept — check the JSON (see content/concepts/README.md)";
    console.error(err);
    throw err;
  }
}

void boot();
