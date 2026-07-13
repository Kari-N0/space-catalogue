"""Capture-system self-test — pins the training↔runtime coordinate contract.

Runs on plain system python3 (no bpy/torch/numpy):
    python3 pipeline/checks/check_capture.py

Covers pipeline/blender/capture/frames.py (the ONLY home of the contract math)
and presets.py. If any fixture here changes meaning, CAPTURE.md and
apps/web/src/viewer/cameraEnvelope.ts must be re-reviewed together.
"""

import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from pipeline.blender.capture import frames, presets  # noqa: E402

FAIL = 0


def check(name, ok, detail=""):
    global FAIL
    print(f"  {'ok' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))
    if not ok:
        FAIL += 1


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def vclose(a, b, tol=1e-9):
    return all(close(x, y, tol) for x, y in zip(a, b))


print("frames: frame transforms")
# RX90 is a proper rotation mapping (x,y,z)->(x,-z,y)
det = (
    frames.RX90[0][0] * (frames.RX90[1][1] * frames.RX90[2][2] - frames.RX90[1][2] * frames.RX90[2][1])
    - frames.RX90[0][1] * (frames.RX90[1][0] * frames.RX90[2][2] - frames.RX90[1][2] * frames.RX90[2][0])
    + frames.RX90[0][2] * (frames.RX90[1][0] * frames.RX90[2][1] - frames.RX90[1][1] * frames.RX90[2][0])
)
check("RX90 det=+1 (no mirror in the dataset frame)", close(det, 1.0))
check("capture_from_blender (x,y,z)->(x,-z,y)",
      vclose(frames.capture_from_blender((3, 4, 5), (0, 0, 0)), (3, -5, 4)))
check("viewer_from_blender = (dx,dz,dy)",
      vclose(frames.viewer_from_blender((3, 4, 5), (1, 1, 1)), (2, 4, 3)))
# composition: loader mirror y on capture frame == viewer_from_blender
pc = frames.capture_from_blender((3, 4, 5), (1, 1, 1))
check("loader y-mirror on capture frame lands at viewer frame",
      vclose((pc[0], -pc[1], pc[2]), frames.viewer_from_blender((3, 4, 5), (1, 1, 1))))

print("frames: envelope angles")
# camera 45 deg above horizon => beta 45; east (+X) => alpha 0; north (+Y) => alpha 90
check("beta: zenith=0", close(frames.beta_deg_from_delta((0, 0, 10)), 0.0))
check("beta: horizon=90", close(frames.beta_deg_from_delta((10, 0, 0)), 90.0))
check("beta: 45 above horizon = 45", close(frames.beta_deg_from_delta((1, 0, 1)), 45.0, 1e-6))
check("alpha: +X=0", close(frames.alpha_deg_from_delta((5, 0, 2)), 0.0))
check("alpha: +Y=90", close(frames.alpha_deg_from_delta((0, 5, 2)), 90.0))
check("fov 40mm/36mm = 48.5 vertical", close(round(frames.fov_v_deg(40, 36), 1), 48.5))

print("frames: COLMAP pose (the make_scene math, conjugated)")
focus = (5842.5, -4882.5, 1662.0)
pos = (focus[0], focus[1] - 50.0, focus[2] + 20.0)  # 50 m south, 20 m up
rwc = frames.look_at_rotation(pos, focus)
q, t = frames.colmap_pose(rwc, pos, focus)
dist = math.dist(pos, focus)
# the focus point (capture-frame origin) must sit on the optical axis at +Z(cv)=dist
check("focus lands on optical axis (0,0,+dist)", vclose(t, (0, 0, dist), 1e-6),
      f"t={t}, dist={dist}")
# reconstruct R from q and verify orthonormality/consistency
w, x, y, z = q
R = (
    (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
    (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
    (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
)
p_above = frames.capture_from_blender((focus[0], focus[1], focus[2] + 5.0), focus)
cv = tuple(frames.mat_vec(R, p_above)[i] + t[i] for i in range(3))
check("point above focus appears in upper image half (y_cv < 0)", cv[1] < 0, f"cv={cv}")
p_east = frames.capture_from_blender((focus[0] + 5.0, focus[1], focus[2]), focus)
cv_e = tuple(frames.mat_vec(R, p_east)[i] + t[i] for i in range(3))
check("east of focus appears right of center (x_cv > 0) from a south camera",
      cv_e[0] > 0, f"cv={cv_e}")
check("quat normalized", close(w * w + x * x + y * y + z * z, 1.0, 1e-9))

print("frames: sampling helpers")
dirs = frames.fibonacci_dirs(200)
check("fibonacci: unit norms", all(close(frames.vec_len(d), 1.0, 1e-9) for d in dirs))
check("fibonacci: deterministic", frames.fibonacci_dirs(200) == dirs)
sub = frames.farthest_point_downsample(dirs, 50)
check("farthest-point: count + deterministic",
      len(sub) == 50 and sub == frames.farthest_point_downsample(dirs, 50))
gap = frames.max_azimuth_gap_deg([frames.alpha_deg_from_delta(d) for d in dirs])
check("fibonacci full sphere has no big azimuth gap", gap < 15.0, f"gap={gap}")

print("frames: alpha arc export semantics")
check("full circle -> free orbit (None)",
      frames.alpha_arc([i * 10.0 for i in range(36)]) is None)
arc = frames.alpha_arc([150, 160, 170, 180, 190, 200, 210])
check("wrapped cluster 150..210 (crosses 180)", arc is not None and
      close((arc[1] - arc[0]) % 360, 60.0, 1e-6), f"arc={arc}")
arc2 = frames.alpha_arc([-120, -110, -100, -90, -80, -70, -60])
check("arc re-anchored near viewer default -90",
      arc2 is not None and arc2[0] <= -90 <= arc2[1] and close(arc2[0], -120, 1e-6),
      f"arc={arc2}")
arc3 = frames.alpha_arc([45.0])  # degenerate single-azimuth rig must not crash
check("single azimuth -> minimal locked arc", arc3 is not None and
      arc3[1] - arc3[0] >= 1.0 - 1e-9 and arc3[0] < arc3[1], f"arc={arc3}")

print("frames: derive_envelope fixture")
deltas = []
for az in range(0, 360, 10):
    for r in (30.0, 60.0):
        a = math.radians(az)
        el = math.radians(30)  # beta 60
        deltas.append((r * math.cos(el) * math.cos(a), r * math.cos(el) * math.sin(a), r * math.sin(el)))
env = frames.derive_envelope(deltas, 40, 36)
check("distance min/max", env["distance_m"] == {"min": 30.0, "max": 60.0}, str(env))
check("beta 60/60", env["angle_up_down_deg"] == {"min": 60.0, "max": 60.0}, str(env))
check("full orbit -> nulls", env["angle_around_deg"] == {"min": None, "max": None})
check("look_at centered", env["look_at_m"] == [0.0, 0.0, 0.0])
# all samples within the 2-deg zenith floor: min must never exceed max
env_top = frames.derive_envelope([(0.001, 0, 1.0), (0.002, 0.001, 1.0)], 40, 36)
ud = env_top["angle_up_down_deg"]
check("near-zenith rig keeps beta min <= max", ud["min"] <= ud["max"], str(ud))

print("frames: COLMAP text format")
with tempfile.TemporaryDirectory() as td:
    frames.write_colmap_text(
        td,
        cameras=[(1, 1080, 1080, 1200.0, 1200.0, 540.0, 540.0)],
        images=[(1, (1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 8.0), 1, "00000.png")],
        points=[((1.0, 2.0, 3.0), (10, 20, 30))],
    )
    cams = open(os.path.join(td, "cameras.txt")).read()
    imgs = open(os.path.join(td, "images.txt")).read()
    pts = open(os.path.join(td, "points3D.txt")).read()
check("cameras.txt PINHOLE line", "1 PINHOLE 1080 1080 1200.0 1200.0 540.0 540.0\n" in cams)
check("images.txt keeps blank points2D line (gsplat parser contract)",
      imgs.endswith("1 1.0 0.0 0.0 0.0 0.0 0.0 8.0 1 00000.png\n\n"), repr(imgs[-60:]))
check("points3D.txt row shape", "1 1.0 2.0 3.0 10 20 30 0.1\n" in pts)

print("presets")
cfg = presets.resolve_config({"preset": "draft"})
check("draft parent views 100", cfg["views"] == 100)
check("hero >= 300 views / 1600-2000 px",
      presets.PRESETS["hero"]["views"] >= 300 and 1600 <= presets.PRESETS["hero"]["resolution"] <= 2000)
ccfg = presets.resolve_config({"preset": "draft", "target_object": "x"}, child=True)
check("draft child views 60", ccfg["views"] == 60)
check("override wins", presets.resolve_config({"preset": "draft", "views": 42})["views"] == 42)
counts = presets.shell_counts(100, [30.0, 45.0, 65.0])
check("shell counts sum to total", sum(counts) == 100, str(counts))
check("outer shell gets most views", counts[2] == max(counts), str(counts))
check("views < shells still sums exactly",
      sum(presets.shell_counts(2, [30.0, 45.0, 65.0])) == 2,
      str(presets.shell_counts(2, [30.0, 45.0, 65.0])))
try:
    presets.resolve_config({"preset": "nope"})
    check("unknown preset raises", False)
except ValueError:
    check("unknown preset raises", True)

print()
if FAIL:
    print(f"CHECK CAPTURE: {FAIL} FAILURE(S)")
    sys.exit(1)
print("CHECK CAPTURE: all ok")
