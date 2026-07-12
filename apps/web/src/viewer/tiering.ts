// Device tier selection — pure and Babylon-free; unit-testable in isolation.
// Heuristics only pick defaults; every knob has a query override for testing
// (?tier= ?dpr= ?engine= ?hud=1).

import type { EngineKind, TierProfile } from "./types";

interface NavigatorWithMemory extends Navigator {
  deviceMemory?: number;
}

export function pickTier(search: URLSearchParams): TierProfile {
  const forced = search.get("tier");
  const coarse = typeof matchMedia !== "undefined" && matchMedia("(pointer: coarse)").matches;
  const smallScreen = Math.min(screen.width, screen.height) < 820;
  const lowMemory = ((navigator as NavigatorWithMemory).deviceMemory ?? 8) <= 6; // Chromium-only hint
  const mobile = forced ? forced === "mobile" : coarse && (smallScreen || lowMemory);

  const engineParam = search.get("engine");
  const engineForce: EngineKind | null =
    engineParam === "webgl" || engineParam === "webgl2" ? "webgl2" : engineParam === "webgpu" ? "webgpu" : null;

  const dprOverride = Number(search.get("dpr"));
  const dprCap = Number.isFinite(dprOverride) && dprOverride > 0 ? dprOverride : mobile ? 1.5 : 2;

  return {
    tier: mobile ? "mobile" : "desktop",
    dprCap,
    targetFps: mobile ? 30 : 60,
    useSogTextures: true, // loader falls back to CPU decode below WebGL2 on its own
    engineForce,
    hud: search.get("hud") === "1",
  };
}

/** Pick the SOG tier file: prefer own tier, fall back to the other (DPR cap absorbs the cost). */
export function pickSogUrl(tier: TierProfile["tier"], sog: { mobile: string | null; desktop: string | null }): string | null {
  return tier === "mobile" ? (sog.mobile ?? sog.desktop) : (sog.desktop ?? sog.mobile);
}
