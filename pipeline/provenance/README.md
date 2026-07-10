# pipeline/provenance

One JSON per asset or source-collection. Two record types (M2 will grow tooling
around these; until then they are written by hand — the hard rule applies
regardless):

**Generated asset** (`type: "generated"`) — required by CLAUDE.md hard rules:
```json
{
  "type": "generated",
  "asset": "assets_src/lunar-base/props/regolith-drill.glb",
  "tool": "TRELLIS 1",
  "model_version": "microsoft/TRELLIS-image-large @ <commit/rev>",
  "prompt_or_input": "ref/drill-photo-042.png (sha256 …)",
  "seed": 42,
  "date": "2026-07-12",
  "license_at_generation": "MIT (TRELLIS 1); input image Apache-2.0 (Qwen-Image-2512 output)",
  "notes": "formats=['mesh','radiance_field']"
}
```

**Reference material** (`type: "reference"`) — external documents/images consulted
or used as modeling reference:
```json
{
  "type": "reference",
  "used_for": "lunar-base scene bible, element dimensions",
  "source": "https://…",
  "publisher": "NASA",
  "accessed": "2026-07-10",
  "usage_terms": "NASA media guidelines (generally free, no endorsement implied)",
  "notes": "dimension X taken from figure 3"
}
```

Layout: `pipeline/provenance/<concept>/…json`. Reference collections may be one
file with an `entries: []` array. License snapshots are point-in-time — re-check
PLAN.md §5 before launch.
