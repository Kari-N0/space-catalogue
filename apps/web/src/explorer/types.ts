// Engine-explorer data shapes — the content file (content/explorers/<id>.json)
// and the per-engine manifest written by the Blender export
// (public/assets/<concept>/engines/<id>.json). Deliberately free of Babylon
// imports so the page entry can use them at zero bundle cost.

export type ViewMode = "explore" | "explode" | "cutaway" | "flow";

/* ---------------- content file ------------------------------------------- */

export interface ExplorerPhoto {
  src: string;
  alt: string;
  caption: string;
  credit: string;
  license: string;
  source_url: string;
  /** CSS object-position for the thumbnail crop (optional). */
  position?: string;
}

export interface FlownOn {
  heading?: string;
  text: string;
  photos?: ExplorerPhoto[];
}

export interface EngineDef {
  id: string;
  ref: string;
  group: string;
  title: string;
  summary?: string;
  /** Second paragraph of the panel. Replaces the manifest's description (written by the Blender export). */
  description?: string;
  reference_engine: string;
  /** "live" = selectable in the 3D view; anything else renders as "In build". */
  status: string;
  model: string;
  manifest: string;
  flown_on?: FlownOn;
}

export interface ExplorerContent {
  id: string;
  page_title: string;
  footer_label: string;
  hero: {
    label: string;
    /** Text of the chip beside the label. Leave it out (or empty) for no chip. */
    status?: string;
    title_line_1: string;
    title_line_2: string;
    era_line: string;
    button_text: string;
    poster_image?: string;
    video?: string;
    /** Smaller (720p) encode served to phones. Optional: without it phones get `video`. */
    video_mobile?: string;
  };
  explorer: {
    heading: string;
    note: string;
    groups: { id: string; title: string }[];
    engines: EngineDef[];
  };
  sources: {
    heading: string;
    intro: string;
    items: { label: string; text: string; url?: string }[];
  };
  /** The "Notify" section with the email form, as on the concept template. Leave it out for no section. */
  signup?: {
    kicker: string;
    heading_line_1: string;
    heading_line_2: string;
    label: string;
    placeholder: string;
    button: string;
    note: string;
  };
  /** The "Contact" section. Leave it out (or the email empty) for no section. */
  contact?: { label: string; email: string };
}

/* ---------------- engine manifest (Blender export) ------------------------ */

export interface ManifestPart {
  /** glTF node name — also the part id used in URLs and cycle diagrams. */
  node: string;
  role?: string;
  title: string;
  description: string;
  /** metres, Blender axes */
  explode_offset?: [number, number, number];
  explode_order?: number;
  /** overrides the on-axis rule for Cutaway */
  cut?: boolean;
  spin?: { axis?: [number, number, number]; rev_per_s?: number };
}

export interface ManifestFlow {
  node: string;
  medium: string;
  label?: string | null;
  variant?: string | null;
  period_s?: number;
}

export interface FlowVariant {
  id: string;
  label: string;
  caption?: string;
}

export interface EngineManifest {
  id: string;
  title: string;
  description: string;
  parts: ManifestPart[];
  flows?: ManifestFlow[];
  flow_model?: {
    caption?: string;
    variants?: FlowVariant[];
    hot_gas?: { assumed_chamber_temp_K: number; exit_temp_K: number; exit_speed_ms: number };
  };
  reference?: {
    engine: string;
    note?: string;
    published?: {
      thrust_sl_kN?: number;
      thrust_vac_kN?: number;
      isp_sl_s?: number;
      isp_vac_s?: number;
      chamber_pressure_bar?: number;
      expansion_ratio?: number;
      mixture_ratio?: number;
      propellants?: string;
      dry_mass_kg?: number;
      length_m?: number;
      max_diameter_m?: number;
      extra?: [string, string][];
    };
  };
}

/* ---------------- viewer contract ---------------------------------------- */

/** [cold, hot] colours as CSS hex strings, keyed by flow medium. */
export type FlowColors = Record<string, [string, string]>;

export interface ViewerCallbacks {
  /** absolute URL of the prefiltered .env lighting environment */
  envUrl: string;
  flowColors?: FlowColors;
  /** outline colour for hovered/selected parts (CSS hex) */
  highlight?: string;
  onStatus?: (text: string) => void;
  onHover?: (id: string | null, pos: { x: number; y: number } | null) => void;
  onSelect?: (id: string | null) => void;
}
