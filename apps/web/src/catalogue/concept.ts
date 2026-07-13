// ConceptDoc: typed view of content/concepts/<id>.json — the single source of
// truth for a concept page (launch acceptance criterion: new concept = new
// JSON + assets, zero new code). Pure types + a small structural validator;
// no engine imports (this module loads on the landing route).

export interface Range3 {
  min: number | null;
  max: number | null;
  default?: number;
}

export interface CameraEnvelope {
  target_m: [number, number, number];
  radius_m: Range3;
  alpha_deg: Range3;
  beta_deg: Range3;
  fov_deg: number;
  /** Ground panning (right-drag): max distance from target_m; null/absent = panning off. */
  pan_m?: { max_from_center: number } | null;
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
  ref: string | null;
  status: string;
  era: string;
  stats: Record<string, unknown>;
  summary: string;
  physics_notes: string[];
  sources: { label: string; url: string }[];
  assets: ConceptAssets;
  camera_envelope: CameraEnvelope | null;
  hotspots: Hotspot[];
}

class ConceptValidationError extends Error {
  constructor(id: string, problem: string) {
    super(`concept "${id}": ${problem}`);
    this.name = "ConceptValidationError";
  }
}

function isVec3(v: unknown): v is [number, number, number] {
  return Array.isArray(v) && v.length === 3 && v.every((n) => typeof n === "number" && Number.isFinite(n));
}

function isRange(v: unknown): v is Range3 {
  if (typeof v !== "object" || v === null) return false;
  const r = v as Record<string, unknown>;
  const ok = (x: unknown) => x === null || (typeof x === "number" && Number.isFinite(x));
  return ok(r.min) && ok(r.max) && (r.default == null || (typeof r.default === "number" && Number.isFinite(r.default)));
}

function validateEnvelope(id: string, v: unknown): CameraEnvelope {
  const e = v as Record<string, unknown>;
  if (typeof e !== "object" || e === null) throw new ConceptValidationError(id, "camera_envelope must be an object");
  if (!isVec3(e.target_m)) throw new ConceptValidationError(id, "camera_envelope.target_m must be [x,y,z]");
  for (const k of ["radius_m", "alpha_deg", "beta_deg"] as const) {
    if (!isRange(e[k])) throw new ConceptValidationError(id, `camera_envelope.${k} must be {min,max} numbers or null`);
  }
  if (typeof e.fov_deg !== "number" || !Number.isFinite(e.fov_deg) || e.fov_deg < 1 || e.fov_deg > 179) {
    throw new ConceptValidationError(id, "camera_envelope.fov_deg must be a finite number in 1–179");
  }
  if (e.pan_m != null) {
    const pan = e.pan_m as Record<string, unknown>;
    if (typeof pan.max_from_center !== "number" || !Number.isFinite(pan.max_from_center) || pan.max_from_center <= 0) {
      throw new ConceptValidationError(id, "camera_envelope.pan_m.max_from_center must be a positive number");
    }
  }
  return e as unknown as CameraEnvelope;
}

/** Structural validation — throws ConceptValidationError with a pointed message. */
export function validateConcept(raw: unknown): ConceptDoc {
  const c = raw as Record<string, unknown>;
  if (typeof c !== "object" || c === null) throw new ConceptValidationError("?", "document is not an object");
  const id = typeof c.id === "string" ? c.id : "?";
  if (typeof c.id !== "string" || !c.id) throw new ConceptValidationError(id, "missing id");
  if (typeof c.title !== "string" || !c.title) throw new ConceptValidationError(id, "missing title");
  const assets = c.assets as Record<string, unknown> | undefined;
  if (typeof assets !== "object" || assets === null) throw new ConceptValidationError(id, "missing assets");
  const sog = assets.hero_sog as Record<string, unknown> | undefined;
  if (typeof sog !== "object" || sog === null) throw new ConceptValidationError(id, "missing assets.hero_sog");

  const doc: ConceptDoc = {
    id: c.id,
    title: c.title,
    ref: typeof c.ref === "string" ? c.ref : null,
    status: typeof c.status === "string" ? c.status : "",
    era: typeof c.era === "string" ? c.era : "",
    stats: (c.stats as Record<string, unknown>) ?? {},
    summary: typeof c.summary === "string" ? c.summary : "",
    physics_notes: Array.isArray(c.physics_notes) ? (c.physics_notes as string[]) : [],
    sources: Array.isArray(c.sources) ? (c.sources as ConceptDoc["sources"]) : [],
    assets: {
      poster: (assets.poster as string) ?? null,
      hero_video: (assets.hero_video as string) ?? null,
      hero_sog: { mobile: (sog.mobile as string) ?? null, desktop: (sog.desktop as string) ?? null },
      inspect_glb: (assets.inspect_glb as string) ?? null,
      env: (assets.env as string) ?? null,
    },
    camera_envelope: c.camera_envelope == null ? null : validateEnvelope(id, c.camera_envelope),
    hotspots: Array.isArray(c.hotspots)
      ? (c.hotspots as Record<string, unknown>[])
          .filter((h) => isVec3(h.position_m) && typeof h.title === "string")
          .map((h) => ({
            position_m: h.position_m as [number, number, number],
            title: h.title as string,
            // normalize so the emitted objects actually satisfy the type
            body: typeof h.body === "string" ? h.body : "",
            image: typeof h.image === "string" ? h.image : null,
          }))
      : [],
  };
  return doc;
}

/** Resolve a concept-JSON asset path against the deploy base (Pages sub-path safe). */
export function assetUrl(path: string): string {
  return new URL(path, new URL(import.meta.env.BASE_URL, document.baseURI)).href;
}

export async function loadConcept(url: string): Promise<ConceptDoc> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`failed to load concept ${url}: HTTP ${res.status}`);
  return validateConcept(await res.json());
}
