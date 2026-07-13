// Concept content contract: content/concepts/<id>.json is the single source
// of truth for a concept page (launch acceptance criterion: new concept =
// new JSON + assets, zero new code). The JSON uses friendly author-facing
// names (see content/concepts/README.md); this module validates it and maps
// it to the internal viewer types. No engine imports — this loads on the
// landing route.

/* ---------------- viewer-facing types (consumed by src/viewer/) ---------- */

export interface Range3 {
  min: number | null;
  max: number | null;
  default?: number;
}

export interface CameraControls {
  /** Multipliers, 1 = default feel. Clamped to 0.1–10. */
  rotate_speed: number;
  move_speed: number;
  zoom_speed: number;
  /** Inertia after release: 0 = stops instantly … 0.95 = long glide. */
  glide_after_release: number;
}

export interface CameraEnvelope {
  target_m: [number, number, number];
  radius_m: Range3;
  alpha_deg: Range3;
  beta_deg: Range3;
  fov_deg: number;
  /** Ground panning (right-drag): max distance from target_m; null/absent = panning off. */
  pan_m?: { max_from_center: number } | null;
  controls: CameraControls;
}

export interface Hotspot {
  position_m: [number, number, number];
  title: string;
  body: string;
  /** Optional image shown in the hotspot info box. */
  image?: string | null;
}

export interface ConceptAssets {
  poster: string | null;
  hero_video: string | null;
  hero_sog: { mobile: string | null; desktop: string | null };
  inspect_glb: string | null;
  env: string | null;
}

export interface ConceptDoc {
  id: string;
  title: string;
  assets: ConceptAssets;
  camera_envelope: CameraEnvelope | null;
  hotspots: Hotspot[];
}

/* ---------------- page-facing types (consumed by catalogue/page.ts) ------ */

export interface PageHero {
  label: string;
  status: string;
  title_line_1: string;
  title_line_2: string;
  era_line: string;
  button_text: string;
}

export interface PageFeature {
  label: string;
  title: string;
  text: string;
  view_angle_deg: number;
  /** Camera feel for this window — defaults to the main view's controls. */
  controls: CameraControls;
}

export type ArticleBlock =
  | { type: "chapter"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "image"; file: string; caption: string };

export interface PageDoc {
  id: string;
  page_title: string;
  hero: PageHero;
  live_view: { heading: string; note: string };
  overview: { heading: string; intro: string; features: PageFeature[] };
  article: { heading: string; blocks: ArticleBlock[] };
  sources: { heading: string; items: { label: string; text: string }[] };
  signup: {
    kicker: string;
    heading_line_1: string;
    heading_line_2: string;
    label: string;
    placeholder: string;
    button: string;
    note: string;
  };
  footer_label: string;
}

export interface ConceptPage {
  page: PageDoc;
  viewer: ConceptDoc;
}

/* ---------------- validation ------------------------------------------- */

class ConceptValidationError extends Error {
  constructor(id: string, problem: string) {
    super(`concept "${id}": ${problem}`);
    this.name = "ConceptValidationError";
  }
}

const str = (v: unknown, fallback = ""): string => (typeof v === "string" ? v : fallback);
const num = (v: unknown, fallback: number): number =>
  typeof v === "number" && Number.isFinite(v) ? v : fallback;
const obj = (v: unknown): Record<string, unknown> =>
  typeof v === "object" && v !== null ? (v as Record<string, unknown>) : {};

function isVec3(v: unknown): v is [number, number, number] {
  return Array.isArray(v) && v.length === 3 && v.every((n) => typeof n === "number" && Number.isFinite(n));
}

function limit(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

const DEFAULT_CONTROLS: CameraControls = {
  rotate_speed: 1,
  move_speed: 1,
  zoom_speed: 1,
  glide_after_release: 0.9,
};

/** Missing fields fall back to `base` (main-view controls, or the defaults). */
function parseControls(v: unknown, base: CameraControls = DEFAULT_CONTROLS): CameraControls {
  const c = obj(v);
  return {
    rotate_speed: clamp(num(c.rotate_speed, base.rotate_speed), 0.1, 10),
    move_speed: clamp(num(c.move_speed, base.move_speed), 0.1, 10),
    zoom_speed: clamp(num(c.zoom_speed, base.zoom_speed), 0.1, 10),
    glide_after_release: clamp(num(c.glide_after_release, base.glide_after_release), 0, 0.95),
  };
}

/** Friendly camera block → viewer envelope. */
function parseCamera(id: string, v: unknown): CameraEnvelope | null {
  if (v == null) return null;
  const c = obj(v);
  if (!isVec3(c.look_at_m)) throw new ConceptValidationError(id, "camera.look_at_m must be [x, y, z] numbers");
  const distance = obj(c.distance_m);
  const upDown = obj(c.angle_up_down_deg);
  const around = obj(c.angle_around_deg);
  const fov = num(c.zoom_fov_deg, 60);
  if (fov < 1 || fov > 179) throw new ConceptValidationError(id, "camera.zoom_fov_deg must be between 1 and 179");
  const move = limit(c.move_limit_m);
  return {
    controls: parseControls(c.controls),
    target_m: c.look_at_m,
    radius_m: { min: limit(distance.min), max: limit(distance.max), default: limit(distance.start) ?? undefined },
    beta_deg: { min: limit(upDown.min), max: limit(upDown.max) },
    alpha_deg: { min: limit(around.min), max: limit(around.max) },
    fov_deg: fov,
    pan_m: move && move > 0 ? { max_from_center: move } : null,
  };
}

function parsePins(v: unknown): Hotspot[] {
  if (!Array.isArray(v)) return [];
  return v
    .filter((p) => isVec3(obj(p).position_m) && typeof obj(p).title === "string")
    .map((p) => {
      const pin = obj(p);
      return {
        position_m: pin.position_m as [number, number, number],
        title: pin.title as string,
        body: str(pin.text),
        image: typeof pin.image === "string" ? pin.image : null,
      };
    });
}

function parseArticleBlocks(v: unknown): ArticleBlock[] {
  if (!Array.isArray(v)) return [];
  const blocks: ArticleBlock[] = [];
  for (const raw of v) {
    const b = obj(raw);
    if (b.type === "chapter" || b.type === "paragraph") {
      blocks.push({ type: b.type, text: str(b.text) });
    } else if (b.type === "image" && typeof b.file === "string") {
      blocks.push({ type: "image", file: b.file, caption: str(b.caption) });
    }
    // unknown block types are skipped, never fatal
  }
  return blocks;
}

/** Parse + validate a concept JSON (friendly authoring format). */
export function parseConceptPage(raw: unknown): ConceptPage {
  const c = obj(raw);
  const id = str(c.id);
  if (!id) throw new ConceptValidationError("?", 'missing "id"');

  const hero = obj(c.hero);
  const live = obj(c.live_view);
  const overview = obj(c.overview);
  const article = obj(c.article);
  const sources = obj(c.sources);
  const signup = obj(c.signup);

  const sceneFile = str(live.scene_file) || null;
  const sceneFileMobile = str(live.scene_file_mobile) || null;
  const camera = parseCamera(id, live.camera);
  const mainControls = camera?.controls ?? DEFAULT_CONTROLS;

  const page: PageDoc = {
    id,
    page_title: str(c.page_title, id),
    hero: {
      label: str(hero.label),
      status: str(hero.status),
      title_line_1: str(hero.title_line_1),
      title_line_2: str(hero.title_line_2),
      era_line: str(hero.era_line),
      button_text: str(hero.button_text, "Enter 3D"),
    },
    live_view: { heading: str(live.heading, "Live View"), note: str(live.note) },
    overview: {
      heading: str(overview.heading, "Overview"),
      intro: str(overview.intro),
      features: Array.isArray(overview.features)
        ? overview.features.map((f) => {
            const feat = obj(f);
            return {
              label: str(feat.label),
              title: str(feat.title),
              text: str(feat.text),
              view_angle_deg: num(feat.view_angle_deg, 0),
              controls: parseControls(feat.controls, mainControls),
            };
          })
        : [],
    },
    article: { heading: str(article.heading, "Specifications"), blocks: parseArticleBlocks(article.blocks) },
    sources: {
      heading: str(sources.heading, "Sources"),
      items: Array.isArray(sources.items)
        ? sources.items.map((s) => ({ label: str(obj(s).label), text: str(obj(s).text) }))
        : [],
    },
    signup: {
      kicker: str(signup.kicker, "Notify"),
      heading_line_1: str(signup.heading_line_1),
      heading_line_2: str(signup.heading_line_2),
      label: str(signup.label, "Email Address"),
      placeholder: str(signup.placeholder, "you@example.com"),
      button: str(signup.button, "Notify Me"),
      note: str(signup.note),
    },
    footer_label: str(c.footer_label),
  };

  const viewer: ConceptDoc = {
    id,
    title: `${page.hero.title_line_1} ${page.hero.title_line_2}`.trim(),
    assets: {
      poster: str(hero.poster_image) || null,
      hero_video: str(hero.video) || null,
      hero_sog: { mobile: sceneFileMobile, desktop: sceneFile },
      inspect_glb: null,
      env: null,
    },
    camera_envelope: camera,
    hotspots: parsePins(live.pins),
  };

  return { page, viewer };
}

/** Resolve a concept-JSON asset path against the deploy base (Pages sub-path safe). */
export function assetUrl(path: string): string {
  return new URL(path, new URL(import.meta.env.BASE_URL, document.baseURI)).href;
}

export async function loadConceptPage(url: string): Promise<ConceptPage> {
  // always revalidate: GitHub Pages caches JSON for up to 10 min, which would
  // make freshly-pushed content edits invisible on a plain refresh
  const res = await fetch(url, { cache: "no-cache" });
  if (!res.ok) throw new Error(`failed to load concept ${url}: HTTP ${res.status}`);
  return parseConceptPage(await res.json());
}

/** Viewer-only view of a concept (used by the dev harness). */
export async function loadConcept(url: string): Promise<ConceptDoc> {
  return (await loadConceptPage(url)).viewer;
}
