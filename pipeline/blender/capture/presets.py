"""Capture quality presets + per-vantage config resolution.

Pure Python (no bpy) — imported both inside Blender and by the WSL-side
orchestrator (pipeline/splats/run_capture.py), so render and train parameters
can never drift apart. Timing expectations per preset live in CAPTURE.md
(measured anchors; the draft rehearsal re-measures them).
"""

PRESETS = {
    # views: parent rig; child_views/bridge_views: per child rig defaults.
    # resolution: square render, px. samples: Cycles. max_steps/cap_max: gsplat MCMC.
    "draft": {
        "views": 100, "child_views": 60, "bridge_views": 15,
        "resolution": 1080, "samples": 64,
        "max_steps": 10_000, "cap_max": 500_000,
    },
    "standard": {
        "views": 200, "child_views": 120, "bridge_views": 25,
        "resolution": 1440, "samples": 128,
        "max_steps": 20_000, "cap_max": 1_000_000,
    },
    "hero": {
        "views": 320, "child_views": 180, "bridge_views": 40,
        "resolution": 1920, "samples": 192,
        "max_steps": 30_000, "cap_max": 2_000_000,
    },
}

# Vantage-level defaults, written as explicit custom properties by
# convention.create_vantage() so every knob is visible in Blender's
# Properties > Collection > Custom Properties panel.
VANTAGE_DEFAULTS = {
    "preset": "draft",
    "views": 0,                 # 0 = take from preset
    "resolution": 0,            # 0 = take from preset
    "samples": 0,               # 0 = take from preset
    "distance_shells_m": [30.0, 45.0, 65.0],
    "min_height_m": 5.0,        # camera height above terrain (evaluated mesh, ±2 m
                                # viewport-vs-render subdiv tolerance — keep >= 5)
    "clearance_m": 2.0,         # min distance from any render geometry
    "require_los": True,        # reject cameras whose view of FOCUS is blocked
    "los_slack_m": 2.0,         # allowed obstruction distance near the focus point
    "train_margin_radius_pct": 5.0,   # dataset-only margin (ADDON.md §3): renders
    "train_margin_beta_deg": 5.0,     # beyond playback envelope, NEVER viewer limits
    "focal_mm": 40.0,           # rehearsal-validated rig camera
    "sensor_mm": 36.0,
    "clip_start_m": 0.1,        # camera clip range — check per capture with the
    "clip_end_m": 100_000.0,    # panel's camera preview; distances vary a lot
    "assembly": "merged",       # merged | separate (parent vantages only)
    "ground_objects": "",       # semicolon-separated ground meshes for min-height
                                # ("" = any terrain* mesh) — tiled grounds welcome
    "seed": 0,                  # rotates the fibonacci spiral phase
}

# Child-rig extras (child collections also carry the VANTAGE_DEFAULTS knobs and
# may override views/resolution/shells; shells default from the target object's
# bounding radius at creation time — see convention.create_child_rig()).
CHILD_DEFAULTS = {
    "target_object": "",
    "standoff_min_m": 0.5,      # min camera distance from the object surface
    "shell_factors": [2.5, 4.0, 6.0],  # x bounds-radius -> distance_shells_m at creation
}

VALID_ASSEMBLY = ("merged", "separate")


def resolve_config(props, child=False):
    """Merge collection custom properties over preset + defaults -> flat dict.

    props: a plain dict of the CAPTURE_ collection's custom properties (bpy id-props
    already converted; convention.read_config() does that). Unknown keys are kept
    (forward compatibility), typed defaults win only when a key is absent or 0.
    """
    preset_name = str(props.get("preset", VANTAGE_DEFAULTS["preset"]))
    if preset_name not in PRESETS:
        raise ValueError(f"unknown preset {preset_name!r} (valid: {sorted(PRESETS)})")
    preset = PRESETS[preset_name]

    cfg = dict(VANTAGE_DEFAULTS)
    if child:
        cfg.update(CHILD_DEFAULTS)
    cfg.update({k: v for k, v in props.items() if v is not None})
    cfg["preset"] = preset_name

    # 0/empty = inherit from preset
    cfg["views"] = int(cfg.get("views") or (preset["child_views"] if child else preset["views"]))
    cfg["resolution"] = int(cfg.get("resolution") or preset["resolution"])
    cfg["samples"] = int(cfg.get("samples") or preset["samples"])
    cfg["bridge_views"] = int(cfg.get("bridge_views") or preset["bridge_views"])
    cfg["max_steps"] = int(cfg.get("max_steps") or preset["max_steps"])
    cfg["cap_max"] = int(cfg.get("cap_max") or preset["cap_max"])

    cfg["distance_shells_m"] = [float(s) for s in cfg["distance_shells_m"]]
    if not cfg["distance_shells_m"] or min(cfg["distance_shells_m"]) <= 0:
        raise ValueError(f"distance_shells_m must be positive: {cfg['distance_shells_m']}")
    for key in ("min_height_m", "clearance_m", "los_slack_m", "focal_mm", "sensor_mm",
                "clip_start_m", "clip_end_m",
                "train_margin_radius_pct", "train_margin_beta_deg"):
        cfg[key] = float(cfg[key])
    cfg["require_los"] = bool(cfg["require_los"])
    cfg["seed"] = int(cfg["seed"])
    if cfg["assembly"] not in VALID_ASSEMBLY:
        raise ValueError(f"assembly must be one of {VALID_ASSEMBLY}: {cfg['assembly']!r}")
    return cfg


def shell_counts(total_views, shells_m):
    """Split a view count across shells, weight ∝ r² (area). Sums to exactly
    total_views; when total_views < len(shells) the largest shells get 1 each
    and the rest 0 (a 0-count shell is simply skipped)."""
    if total_views <= 0:
        return [0] * len(shells_m)
    order = sorted(range(len(shells_m)), key=lambda i: -shells_m[i])
    if total_views < len(shells_m):
        counts = [0] * len(shells_m)
        for i in order[:total_views]:
            counts[i] = 1
        return counts
    weights = [r * r for r in shells_m]
    wsum = sum(weights)
    counts = [max(1, round(total_views * w / wsum)) for w in weights]
    i = 0
    while sum(counts) != total_views:
        j = order[i % len(order)]
        if sum(counts) > total_views and counts[j] > 1:
            counts[j] -= 1
        elif sum(counts) < total_views:
            counts[j] += 1
        i += 1
    return counts
