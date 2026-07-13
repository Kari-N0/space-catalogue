// Viewer public types — deliberately free of Babylon imports so landing-route
// code can import them at zero bundle cost.

import type { CameraControls, ConceptDoc, Hotspot } from "../catalogue/concept";

export type EngineKind = "webgpu" | "webgl2";
export type Tier = "mobile" | "desktop";

export interface TierProfile {
  tier: Tier;
  dprCap: number;
  targetFps: number;
  useSogTextures: boolean;
  engineForce: EngineKind | null;
  hud: boolean;
}

export type ViewerMode = "hero" | "inspect";

export interface ViewerProgress {
  phase: "engine" | "download" | "decode" | "ready";
  /** 0..1 when byte progress is known, undefined while indeterminate. */
  ratio?: number;
}

export interface ViewerOptions {
  canvas: HTMLCanvasElement;
  /** Absolutely positioned container the viewer may fill with hotspot elements. */
  hotspotLayer: HTMLElement | null;
  concept: ConceptDoc;
  profile: TierProfile;
  onProgress?: (p: ViewerProgress) => void;
  onModeChange?: (m: ViewerMode) => void;
  /** Fired when the user clicks a hotspot pin (pages open their popup here). */
  onHotspotSelect?: (h: Hotspot) => void;
}

export interface FeatureViewHandle {
  /** Pause/resume rendering of this view (wire to an IntersectionObserver). */
  setEnabled(enabled: boolean): void;
  dispose(): void;
}

export interface ViewerHandle {
  engineKind: EngineKind;
  mode(): ViewerMode;
  /** Rejects when the concept has no inspect_glb (button should not exist). */
  enterInspect(): Promise<void>;
  enterHero(): Promise<void>;
  /**
   * Render the live hero scene into an additional canvas with its own
   * envelope-constrained camera (one engine, one scene, N views). Hero mode
   * only; views are torn down on scene swap and dispose().
   */
  attachFeatureView(
    canvas: HTMLCanvasElement,
    opts?: { alphaOffsetDeg?: number; controls?: CameraControls },
  ): FeatureViewHandle;
  fps(): number;
  dispose(): void;
}
