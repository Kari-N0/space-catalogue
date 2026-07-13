"""Capture-frame math — THE single home of the training↔runtime envelope contract.

Pure Python (no bpy, no mathutils, no numpy) so the exact same code runs inside
Blender 5.1 (py3.13), in WSL CPython, and under pipeline/checks/check_capture.py.

The contract (CAPTURE.md "Coordinate contract"):

    capture frame:  p_d = RX90 @ (p_blender - focus)        # (x, -z, y)
    Babylon world:  p_v = (p_d.x, -p_d.y, p_d.z)            # loader scaling.y *= -1
                        = (dx, dz, dy) of d = p_blender - focus

so viewer X = Blender X, viewer Y (up) = Blender Z, viewer Z = Blender Y, and the
COLMAP dataset / trained splat needs NO manual reorientation anywhere downstream
(SuperSplat pass = clean/crop only). Envelope terms for a camera at delta d:

    beta_deg  = angle(d, +Z_blender)          # Babylon polar angle, 90 = horizon
    alpha_deg = atan2(d.y, d.x) in degrees    # Babylon azimuth (x = r cosa sinb,
                                              #  z = r sina sinb, y = r cosb)

The world->camera OpenGL->OpenCV conversion is the make_scene.py math (validated
at PSNR 38.5 — which proves pose export, not frame preservation) conjugated into
the capture frame; keep it here and nowhere else. Frame preservation additionally
requires training with gsplat's world normalization OFF: simple_trainer.py
defaults normalize_world_space=True (recenter+rescale+PCA-rotate, baked into the
exported PLY), so run_capture.py MUST pass --no-normalize-world-space. Never drop
that flag.
"""

import hashlib
import json
import math

GOLDEN_RAD = math.radians(137.50776)

# p_capture = RX90 @ p : (x, y, z) -> (x, -z, y). det = +1 (proper rotation).
RX90 = ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))
# OpenGL camera (y up, looking -z) -> OpenCV camera (y down, z forward).
D_GL_CV = ((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0))


# ------------------------------------------------------------------ tiny linalg

def mat_vec(m, v):
    return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3))


def mat_mul(a, b):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
        for i in range(3)
    )


def mat_t(m):
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))


def vec_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec_len(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def vec_norm(v):
    n = vec_len(v)
    return (v[0] / n, v[1] / n, v[2] / n)


def vec_cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


# ------------------------------------------------------------- frame transforms

def capture_from_blender(p, focus):
    """Blender world point -> capture/COLMAP frame."""
    return mat_vec(RX90, vec_sub(p, focus))


def viewer_from_blender(p, focus):
    """Blender world point -> Babylon viewer world (post loader y-mirror): (dx, dz, dy)."""
    d = vec_sub(p, focus)
    return (d[0], d[2], d[1])


def beta_deg_from_delta(d):
    """Babylon ArcRotateCamera beta (deg from zenith) for a camera at Blender delta d."""
    r = vec_len(d)
    return math.degrees(math.acos(max(-1.0, min(1.0, d[2] / r))))


def alpha_deg_from_delta(d):
    """Babylon ArcRotateCamera alpha (deg) for a camera at Blender delta d."""
    return math.degrees(math.atan2(d[1], d[0]))


def fov_v_deg(focal_mm, sensor_mm):
    """Vertical FOV of the (square-render) rig camera — becomes zoom_fov_deg."""
    return math.degrees(2.0 * math.atan(sensor_mm / 2.0 / focal_mm))


# ------------------------------------------------------- camera pose -> COLMAP

def quat_from_mat(m):
    """Rotation matrix (row tuples) -> quaternion (w, x, y, z), normalized."""
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        w = 0.25 * s
        x = (m[2][1] - m[1][2]) / s
        y = (m[0][2] - m[2][0]) / s
        z = (m[1][0] - m[0][1]) / s
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2.0
        w = (m[2][1] - m[1][2]) / s
        x = 0.25 * s
        y = (m[0][1] + m[1][0]) / s
        z = (m[0][2] + m[2][0]) / s
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2.0
        w = (m[0][2] - m[2][0]) / s
        x = (m[0][1] + m[1][0]) / s
        y = 0.25 * s
        z = (m[1][2] + m[2][1]) / s
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2.0
        w = (m[1][0] - m[0][1]) / s
        x = (m[0][2] + m[2][0]) / s
        y = (m[1][2] + m[2][1]) / s
        z = 0.25 * s
    n = math.sqrt(w * w + x * x + y * y + z * z)
    return (w / n, x / n, y / n, z / n)


def look_at_rotation(pos, target, up=(0.0, 0.0, 1.0)):
    """World-from-camera rotation (columns = camera axes) for an OpenGL camera at
    pos looking at target — the pure-math twin of to_track_quat("-Z", "Y")."""
    if vec_len(vec_sub(target, pos)) < 1e-9:
        raise ValueError("camera position coincides with target")
    fwd = vec_norm(vec_sub(target, pos))
    z_cam = (-fwd[0], -fwd[1], -fwd[2])
    x_cam = vec_cross(up, z_cam)
    n = vec_len(x_cam)
    if n < 1e-8:  # looking straight up/down: fall back to world +Y as right hint
        x_cam = vec_cross((0.0, 1.0, 0.0), z_cam)
        n = vec_len(x_cam)
    x_cam = (x_cam[0] / n, x_cam[1] / n, x_cam[2] / n)
    y_cam = vec_cross(z_cam, x_cam)
    # rows of world-from-camera matrix = axis components per world coordinate
    return (
        (x_cam[0], y_cam[0], z_cam[0]),
        (x_cam[1], y_cam[1], z_cam[1]),
        (x_cam[2], y_cam[2], z_cam[2]),
    )


def colmap_pose(r_world_from_cam, cam_pos, focus):
    """Blender camera pose -> COLMAP (qw,qx,qy,qz, tx,ty,tz) in the capture frame.

    r_world_from_cam: 3x3 rows, the camera object's world rotation (OpenGL axes).
    cam_pos: camera world position (Blender). focus: capture-frame origin.
    """
    r_w2c_b = mat_t(r_world_from_cam)
    # conjugate into the capture frame, then OpenGL -> OpenCV
    r_w2c_d = mat_mul(r_w2c_b, mat_t(RX90))
    r_cv = mat_mul(D_GL_CV, r_w2c_d)
    pos_d = capture_from_blender(cam_pos, focus)
    t_d = mat_vec(r_w2c_d, (-pos_d[0], -pos_d[1], -pos_d[2]))
    t_cv = mat_vec(D_GL_CV, t_d)
    q = quat_from_mat(r_cv)
    return q, t_cv


# ----------------------------------------------------------------- rig sampling

def fibonacci_dirs(n, phase=0.0):
    """n deterministic unit directions on the full sphere (golden-angle spiral)."""
    dirs = []
    for i in range(n):
        z = 1.0 - 2.0 * (i + 0.5) / n
        rho = math.sqrt(max(0.0, 1.0 - z * z))
        az = i * GOLDEN_RAD + phase
        dirs.append((rho * math.cos(az), rho * math.sin(az), z))
    return dirs


def farthest_point_downsample(dirs, k, start=0):
    """Greedy farthest-point subset of unit vectors — deterministic, O(n*k)."""
    if k >= len(dirs):
        return list(range(len(dirs)))
    chosen = [start]
    # min angular distance to chosen set, tracked as max dot (cos of angle)
    best_dot = [
        dirs[i][0] * dirs[start][0] + dirs[i][1] * dirs[start][1] + dirs[i][2] * dirs[start][2]
        for i in range(len(dirs))
    ]
    while len(chosen) < k:
        nxt = min(range(len(dirs)), key=lambda i: (best_dot[i], i))
        chosen.append(nxt)
        d = dirs[nxt]
        for i in range(len(dirs)):
            dot = dirs[i][0] * d[0] + dirs[i][1] * d[1] + dirs[i][2] * d[2]
            if dot > best_dot[i]:
                best_dot[i] = dot
    return sorted(chosen)


def max_azimuth_gap_deg(azimuths_deg):
    """Largest empty azimuth gap (deg) in a sample set; 360 when empty."""
    if not azimuths_deg:
        return 360.0
    az = sorted(a % 360.0 for a in azimuths_deg)
    gaps = [az[i + 1] - az[i] for i in range(len(az) - 1)]
    gaps.append(az[0] + 360.0 - az[-1])
    return max(gaps)


def alpha_arc(azimuths_deg, free_gap_deg=30.0, anchor_deg=-90.0):
    """Azimuth samples -> (min_deg, max_deg) alpha limits, or None for free orbit.

    None when no gap >= free_gap_deg exists (coverage is effectively full-circle).
    Otherwise the limits span the complement of the largest gap, expressed as a
    continuous arc shifted by k*360 so its midpoint sits closest to anchor_deg
    (the viewer's default alpha is -90; Babylon limits are continuous radians).
    """
    if not azimuths_deg:
        return None
    az = sorted(a % 360.0 for a in azimuths_deg)
    gaps = [(az[i + 1] - az[i], i) for i in range(len(az) - 1)]
    gaps.append((az[0] + 360.0 - az[-1], len(az) - 1))
    gap, idx = max(gaps)
    if gap < free_gap_deg:
        return None
    lo = az[(idx + 1) % len(az)]
    hi = lo + (360.0 - gap)
    if hi - lo < 1.0:  # all samples at one azimuth: lock a minimal arc around it
        lo, hi = lo - 0.5, hi + 0.5
    mid = (lo + hi) / 2.0
    shift = round((anchor_deg - mid) / 360.0) * 360.0
    lo, hi = lo + shift, hi + shift
    # invariant the viewer depends on: a continuous unwrapped arc. A wrapped pair
    # (min > max) would pin Babylon's alpha clamp to one endpoint every frame.
    assert lo < hi and hi - lo <= 360.0, f"alpha arc invariant broken: {(lo, hi)}"
    return (lo, hi)


# ------------------------------------------------------------ envelope derivation

def derive_envelope(deltas_blender, focal_mm, sensor_mm, free_gap_deg=30.0,
                    beta_floor_deg=2.0, beta_ceil_deg=178.0):
    """Playback rig sample deltas (Blender, camera - focus) -> friendly camera dict.

    Returns the generated portion of the concept-JSON live_view.camera block
    (authoring format). look_at_m is [0,0,0] by construction — the dataset frame
    is focus-centered; callers place child envelopes via viewer_from_blender().
    The exported beta min is floored at beta_floor_deg (default 2°): Babylon's
    ArcRotateCamera degenerates at the zenith pole; dataset cameras may still go
    higher — margins live in the dataset, never in the viewer limits.
    """
    radii = [vec_len(d) for d in deltas_blender]
    betas = [beta_deg_from_delta(d) for d in deltas_blender]
    alphas = [alpha_deg_from_delta(d) for d in deltas_blender]
    arc = alpha_arc(alphas, free_gap_deg)
    clamp_beta = lambda b: min(beta_ceil_deg, max(beta_floor_deg, b))  # noqa: E731
    # clamp BOTH endpoints into [floor, ceil] so an all-near-zenith rig can never
    # emit min > max (Babylon would freeze the camera between inverted limits)
    return {
        "look_at_m": [0.0, 0.0, 0.0],
        "distance_m": {"min": round(min(radii), 2), "max": round(max(radii), 2)},
        "angle_up_down_deg": {
            "min": round(clamp_beta(min(betas)), 1),
            "max": round(clamp_beta(max(betas)), 1),
        },
        "angle_around_deg": (
            {"min": None, "max": None} if arc is None
            else {"min": round(arc[0], 1), "max": round(arc[1], 1)}
        ),
        "zoom_fov_deg": round(fov_v_deg(focal_mm, sensor_mm), 1),
    }


# -------------------------------------------------------------- rig approval hash

def contract_hash(payload):
    """Deterministic short hash of a JSON-serializable payload.

    The preview stamps the rig with contract_hash({configs, env meshes, focus
    positions, seed}); export_dataset refuses to render unless it recomputes the
    same value and is passed --approved-rig <hash> ("nothing renders without my
    go" — mechanically enforced, not just by convention).
    """
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(blob.encode()).hexdigest()[:12]


# ------------------------------------------------------------- COLMAP text files

def write_colmap_text(sparse_dir, cameras, images, points):
    """Write cameras.txt / images.txt / points3D.txt (gsplat-validated layout).

    cameras: [(camera_id, width, height, fx, fy, cx, cy)]           (PINHOLE)
    images:  [(image_id, (qw,qx,qy,qz), (tx,ty,tz), camera_id, name)]
    points:  [((x,y,z), (r,g,b))]  0-255 ints for rgb
    Format quirks that MUST stay: the blank points2D line after every image row.
    """
    import os

    os.makedirs(sparse_dir, exist_ok=True)
    with open(os.path.join(sparse_dir, "cameras.txt"), "w") as fh:
        fh.write("# CAMERA_ID MODEL WIDTH HEIGHT PARAMS\n")
        for cid, w, h, fx, fy, cx, cy in cameras:
            fh.write(f"{cid} PINHOLE {w} {h} {fx} {fy} {cx} {cy}\n")
    with open(os.path.join(sparse_dir, "images.txt"), "w") as fh:
        fh.write("# IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME\n")
        for iid, q, t, cid, name in images:
            fh.write(f"{iid} {q[0]} {q[1]} {q[2]} {q[3]} {t[0]} {t[1]} {t[2]} {cid} {name}\n\n")
    with open(os.path.join(sparse_dir, "points3D.txt"), "w") as fh:
        fh.write("# POINT3D_ID X Y Z R G B ERROR TRACK[]\n")
        for pid, (p, rgb) in enumerate(points, start=1):
            fh.write(f"{pid} {p[0]} {p[1]} {p[2]} {rgb[0]} {rgb[1]} {rgb[2]} 0.1\n")
