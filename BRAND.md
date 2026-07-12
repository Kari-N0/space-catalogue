# BRAND.md — Space Engineering Catalogue brand rules

**STATUS: APPROVED by Kari, 2026-07-12** — with these decisions on the §8 questions: (1) ref label format is **"CONCEPT 001"** (mono uppercase, three-digit series number — no "Ref:" prefix); (2) Vidro credit appears in **both** nav and footer; (3) **a single accent triad for all status chips** (blue triad as the default pick — one-line token change if Kari prefers another); (4) **two-tone display treatment: yes**; (5) no amendments. `tokens.css` is ground truth from this date. Layout/sections still follow the mockup pick (CLAUDE.md brand boundary).
Source: rendered audit of https://www.vidro.fi on 2026-07-12 (computed styles + screenshots; method in §9). Companion file: `apps/web/src/styles/tokens.css` (not imported anywhere until approved).

The catalogue is a Vidro production and should read as a sibling of vidro.fi: same dark, engineering-calm surface; same type system; same Ref-code labeling language. Below, "observed" = measured on vidro.fi; "proposed" = adaptation for the catalogue needing Kari's sign-off.

---

## 1. Palette (dark theme)

Observed (vidro.fi is near-monochrome; color is used only as functional labeling, never decorative washes):

| Token | Value | Observed use |
|---|---|---|
| `--color-bg` | `#030304` (rgb 3,3,4) | page background |
| `--color-surface` | `#0B0B0D` (rgb 11,11,13) | raised band/sections (`bg-surface`), cards |
| `--color-text` | `#EEEEF0` | default text |
| `--color-text-emphasis` | `#FFFFFF` | headings, quotes, emphasized UI |
| `--color-text-secondary` | `#888891` | leads, kickers, ref labels, nav idle |
| hairlines | `rgba(255,255,255,.05/.06/.10/.20)` | section separators, card borders, pill borders |
| glass nav | `rgba(3,3,4,.70)` + `backdrop-blur(12px)` | fixed nav |
| image scrim chip | `rgba(0,0,0,.50)` + `blur(8px)`, border white/10 | shot-label chips on imagery |
| availability green | `#22C55E` dot (+ `#4ADE80` ping) | "Available for…" status |
| category chip triads | text-400 / bg-500 @10% / border-500 @20% — observed blue (`#60A5FA`), purple (`#C084FC`), orange (`#FB923C`) | project category tags |

Proposed for the catalogue: identical neutrals and hairline system. Category-chip triads become **concept status/domain chips** (e.g. IN DEVELOPMENT / STUDIED / THEORETICAL from the concept JSON `status`). Which triad maps to which status — **Kari's call (§8 Q3)**.

## 2. Typography

Observed stack (three roles, only two font families shipped):

- **Display — Space Grotesk**, weight 500 only. Hero 128px/1.0, tracking −0.05em, UPPERCASE, two-tone treatment (line 1 `#EEEEF0`/white, line 2 secondary/faded — see hero and "ENGINEERING LOGIC. / CINEMATIC ARTISTRY."). Section display ~48–60px uppercase; project/page titles 36px/40 mixed-case, tracking −0.025em; H2 30px/36 tracking −0.025em; large quotes 30px/36.
- **Body — Inter.** Base 16px/24 w400; leads 20px/28 **w300**; UI emphasis w500–600; nav links 12px uppercase w500 tracking 0.3px.
- **Mono — system stack** (`ui-monospace, SFMono-Regular, Menlo, Consolas, …`): kickers 12px uppercase tracking 1.2px; ref/category labels 10px uppercase tracking 1px; timestamps/counters ("02:22", "CLIENT_STORIES_01-03"). Zero font payload by design — keep this.

**Licenses (verified upstream 2026-07-12):** Inter — SIL OFL 1.1 (rsms/inter LICENSE.txt); Space Grotesk — SIL OFL 1.1 (floriankarsten/space-grotesk OFL.txt). Both permit commercial web use on any site and self-hosting; no substitution needed. **Deviation from vidro.fi: we self-host woff2 subsets** (Inter 300/400/500/600, Space Grotesk 500, latin subset) instead of the Google Fonts CDN — fonts.googleapis.com transmits visitor IPs to Google (LG München precedent) and we want the site consent-banner-free; self-hosting is also faster and CSP-friendly.

## 3. Ref-code & label conventions (the system Kari asked to match)

Observed grammar on vidro.fi project cards:

```
[CATEGORY CHIP]  Ref: XX-NN        ← e.g. [AEROSPACE] Ref: SP-01, [BROADCAST VFX] Ref: TV-02, [VIRTUAL REALITY] Ref: VR-03
Project Title (Space Grotesk 36px)
One-line description (secondary)
[image] [image] [image]            ← each may carry a scrim chip shot label ("IN ORBIT", "EARTH RISE SHOT")
```

- **Category chip:** mono 10px UPPERCASE, tracking 1px, padding 2×8px, radius 4px, colored triad (§1).
- **Ref label:** mono 10px UPPERCASE, tracking 1px, `--color-text-secondary`, format `Ref: <PREFIX>-<NN>` — prefix encodes domain, number is series order.
- **Section kickers:** mono 12px UPPERCASE tracking 1.2px secondary ("SHOWREEL", "COLLABORATIONS").
- **Scrim chips on imagery:** Inter 10px uppercase on black/50 + blur(8px), border white/10, radius 4px — ideal reuse for viewer hotspot/shot labels.
- Stat blocks: large display number + tiny mono label ("15+ / YEARS EXP.").

Proposed for the series: launch title **"Concept 001: Artemis Lunar Base"** with ref label e.g. `Ref: SC-001` ("Space Catalogue") or `Ref: C-001` — **prefix is Kari's call (§8 Q1)**; the concept JSON gets a `ref` field so the template renders it, never hardcodes it.

## 4. Spacing & layout

Observed: container max-width **1280px**; section rhythm **128px** (major) / **96px** (standard) / **80px** (minor) vertical padding; hairline `white/5` separators between sections; cards radius **12px**, padding **32px**, border white/6, on `--color-surface`; pills fully rounded; hero = full viewport (`min-height 700px`).

## 5. Components observed (for reuse)

- **Primary pill button:** white bg, black text, 16px w500, icon right ("Get Started ✈").
- **Secondary pill button:** transparent, 1px white/10–20 border, white text, often UPPERCASE 12px tracked ("VIEW REEL", "CONTACT →").
- **Pill nav cluster:** links grouped in a rounded dark container; fixed glass nav (blur 12) with hairline bottom border.
- **Availability chip:** dark pill, green dot + ping animation, 11px uppercase tracked secondary text.
- **Quote block:** Space Grotesk 30px white + small attribution (name w500, role secondary 12px).
- **Footer:** minimal — lockup left, social icons right, hairline top, 48px padding.
- **Logo lockup:** triangle "V" mark + "KARI NÖJD" + 10px uppercase tracked "VISUALS BY VIDRO". Catalogue credit uses `logo_vidro_placeholder.png` while in placeholder phase; placement — **Kari's call (§8 Q2)**.

## 6. Motion feel

Observed: transitions **300ms `cubic-bezier(0.4, 0, 0.2, 1)`** on color/opacity/transform hovers (secondary→white links, card borders); `ping` keyframe on availability dot; `bounce` on scroll cue; smooth scrolling; no parallax, no scroll-jacking. Feel: **calm, quick, functional**.

Proposed for the catalogue: same single duration/easing token pair for all UI; 3D scene entry = simple fade/opacity ramp using the same easing; `prefers-reduced-motion` honored globally (animations off, posters instead of autoplaying media — feeds M6 accessibility).

## 7. Voice cues (from vidro.fi copy)

Short declarative UPPERCASE displays ("VISUALIZING THE FUTURE", "READY TO START?"); technical-precision framing; mono microcopy in system-log style ("CLIENT_STORIES_01-03"). Catalogue equivalents should keep fact-layer honesty (status labels per PLAN.md §10 "scale honesty").

## 8. Open questions — RESOLVED by Kari 2026-07-12

1. **Ref format:** `CONCEPT 001` (mono 10–12px uppercase tracked label, three-digit series number).
2. **Credit lockup:** Vidro credit in **both** nav and footer.
3. **Status chips:** one accent triad for all statuses — **blue** (`--chip-blue-*`) as the standing default; swap is a one-line token edit if Kari ever prefers another.
4. **Two-tone display treatment:** yes — line 1 near-white, line 2 secondary/faded, per vidro.fi.
5. No amendments; §1–§7 stand as written.

## 9. Method / provenance

Rendered audit 2026-07-12: Windows Chrome 122 headless (`--remote-debugging-port=9222`) driven from WSL via puppeteer-core connect — **deviation:** the configured chrome-devtools MCP server cannot launch (no Chrome inside WSL; proposed `.mcp.json` fix: add `--browserUrl=http://127.0.0.1:9222` and start Windows Chrome headless first). Extracted computed styles, cssRules, font requests + full-page screenshots (desktop 1440w, mobile 390w). Data + screenshots: session scratchpad `brand/` (`vidro-brand-data*.json`, `home-desktop-*.png/jpg`, `home-mobile-*.jpg`). vidro.fi is Tailwind (Play CDN) with custom `background/surface/secondary` colors; it loads ~22 Google-Fonts stylesheets but **renders only Inter + Space Grotesk + system mono** — the rest are unused template leftovers, deliberately not carried over.
