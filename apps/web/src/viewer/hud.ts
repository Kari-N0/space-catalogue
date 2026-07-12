// Dev-only fps/diagnostics HUD (?hud=1). Reports the numbers the M1 done-check
// needs: fps, engine kind, tier, hardware-scaling level.

import type { AbstractEngine } from "@babylonjs/core/Engines/abstractEngine";
import type { EngineKind, TierProfile } from "./types";

export interface Hud {
  dispose(): void;
}

export function mountHud(engine: AbstractEngine, kind: EngineKind, profile: TierProfile, host: HTMLElement): Hud {
  const el = document.createElement("pre");
  el.style.cssText =
    "position:absolute;top:8px;left:8px;margin:0;padding:6px 8px;background:rgba(0,0,0,.6);" +
    "color:#4ade80;font:11px/1.4 ui-monospace,monospace;z-index:10;pointer-events:none;border-radius:4px";
  host.appendChild(el);

  let ema = 0;
  const timer = setInterval(() => {
    const fps = engine.getFps();
    ema = ema === 0 ? fps : ema * 0.8 + fps * 0.2;
    el.textContent =
      `${kind} · ${profile.tier}\n` +
      `fps ${fps.toFixed(0)} (ema ${ema.toFixed(0)}, target ${profile.targetFps})\n` +
      `hwScale ${engine.getHardwareScalingLevel().toFixed(2)} · dprCap ${profile.dprCap}`;
  }, 500);

  return {
    dispose() {
      clearInterval(timer);
      el.remove();
    },
  };
}
