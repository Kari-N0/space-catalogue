"""build_gn_kit.py — build the reusable Geometry Nodes generator kit (asset 001).

bpy script (ML-free), run headless on Windows Blender:
    pipeline/blender/blender-win.sh -b --python pipeline/blender/build_gn_kit.py -- \
        --out <assets/gn_kit/gn_kit_v001.blend>

Creates six node groups (PLAN.md §4.2 kit, ASSETS.md row 001) + one demo object
each in collection AST_gn_kit:
  GN_truss                4 chords + 2 side Warren zigzags, tube profile
  GN_panel_array          instanced panel grid with depth jitter
  GN_mli_wrap             subdivide + noise crinkle along normals
  GN_scaffold             lattice from a gridded cube's edges, tube profile
  GN_regolith_berm        arc ring w/ corridor gap, half-ellipse section, noise
  GN_surface_disturbance  radial-falloff clod scatter on a host surface

All groups end in a Set Material node fed by a Material group input, so
consumers assign real materials per use. Demo objects are flagged
`procedural_ok` (GN output has no UVs; materials must be procedural).

Importable: build_kit(out_path) -> None
"""

import argparse
import math
import sys

import bpy

X = 180  # node column spacing


def add(tr, bl_id, col, row=0, ins=None, **props):
    n = tr.nodes.new(bl_id)
    n.location = (col * X, row * -160)
    for k, v in props.items():
        setattr(n, k, v)
    for key, val in (ins or {}).items():
        sock = n.inputs[key]
        if isinstance(val, bpy.types.NodeSocket):
            tr.links.new(val, sock)
        else:
            sock.default_value = val
    return n


def new_group(name, inputs, has_geo_in=False):
    tr = bpy.data.node_groups.new(name, "GeometryNodeTree")
    if has_geo_in:
        tr.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    for nm, stype, default in inputs:
        s = tr.interface.new_socket(nm, in_out="INPUT", socket_type=stype)
        if default is not None:
            s.default_value = default
    tr.interface.new_socket("Material", in_out="INPUT", socket_type="NodeSocketMaterial")
    tr.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gin = add(tr, "NodeGroupInput", -2)
    gout = add(tr, "NodeGroupOutput", 12)
    return tr, gin, gout


def finish(tr, gin, gout, last_geo_socket, col=10):
    setmat = add(tr, "GeometryNodeSetMaterial", col, 0,
                 ins={"Geometry": last_geo_socket, "Material": gin.outputs["Material"]})
    tr.links.new(setmat.outputs["Geometry"], gout.inputs["Geometry"])


def _zigzag(tr, gin, row, length_s, bays_s, width_s, height_s, side, flat=False):
    """Warren zigzag brace line on one truss face, spanning chord-to-chord.

    side faces (flat=False): y fixed at side*W/2, z alternates -H/2 <-> +H/2
    top/bottom (flat=True):  z fixed at side*H/2, y alternates -W/2 <-> +W/2
    Alternation spans the FULL section so brace ends land on the chords.
    """
    count = add(tr, "ShaderNodeMath", 0, row, ins={0: bays_s, 1: 1.0}, operation="ADD")
    line = add(tr, "GeometryNodeMeshLine", 1, row, ins={"Count": count.outputs[0]})
    idx = add(tr, "GeometryNodeInputIndex", 1, row + 0.6)
    bay = add(tr, "ShaderNodeMath", 2, row, ins={0: length_s, 1: bays_s}, operation="DIVIDE")
    px = add(tr, "ShaderNodeMath", 3, row, ins={0: idx.outputs[0], 1: bay.outputs[0]}, operation="MULTIPLY")
    odd = add(tr, "ShaderNodeMath", 2, row + 0.6, ins={0: idx.outputs[0], 1: 2.0}, operation="MODULO")
    alt_amp, fix_amp = (width_s, height_s) if flat else (height_s, width_s)
    a1 = add(tr, "ShaderNodeMath", 3, row + 0.6, ins={0: odd.outputs[0], 1: alt_amp}, operation="MULTIPLY")
    ah = add(tr, "ShaderNodeMath", 4, row + 1.2, ins={0: alt_amp, 1: 0.5}, operation="MULTIPLY")
    alt = add(tr, "ShaderNodeMath", 5, row + 0.6, ins={0: a1.outputs[0], 1: ah.outputs[0]}, operation="SUBTRACT")
    fix = add(tr, "ShaderNodeMath", 4, row, ins={0: fix_amp, 1: side * 0.5}, operation="MULTIPLY")
    axes = {"X": px.outputs[0], "Y": alt.outputs[0], "Z": fix.outputs[0]} if flat else \
           {"X": px.outputs[0], "Y": fix.outputs[0], "Z": alt.outputs[0]}
    pos = add(tr, "ShaderNodeCombineXYZ", 6, row, ins=axes)
    sp = add(tr, "GeometryNodeSetPosition", 7, row,
             ins={"Geometry": line.outputs["Mesh"], "Position": pos.outputs["Vector"]})
    return sp.outputs["Geometry"]


def gn_truss():
    tr, gin, gout = new_group("GN_truss", [
        ("Length", "NodeSocketFloat", 6.0), ("Width", "NodeSocketFloat", 0.6),
        ("Height", "NodeSocketFloat", 0.6), ("Bays", "NodeSocketFloat", 6.0),
        ("Chord Radius", "NodeSocketFloat", 0.035), ("Brace Radius", "NodeSocketFloat", 0.02),
    ])
    L, W, H, B = (gin.outputs[k] for k in ("Length", "Width", "Height", "Bays"))
    # 4 chords
    chord_join = add(tr, "GeometryNodeJoinGeometry", 4, -2)
    for i, (sy, sz) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
        y = add(tr, "ShaderNodeMath", 0, -4 - i, ins={0: W, 1: sy * 0.5}, operation="MULTIPLY")
        z = add(tr, "ShaderNodeMath", 1, -4 - i, ins={0: H, 1: sz * 0.5}, operation="MULTIPLY")
        start = add(tr, "ShaderNodeCombineXYZ", 2, -4 - i, ins={"Y": y.outputs[0], "Z": z.outputs[0]})
        off = add(tr, "ShaderNodeCombineXYZ", 2, -3.4 - i, ins={"X": L})
        line = add(tr, "GeometryNodeMeshLine", 3, -4 - i,
                   ins={"Count": 2, "Start Location": start.outputs["Vector"], "Offset": off.outputs["Vector"]})
        tr.links.new(line.outputs["Mesh"], chord_join.inputs[0])
    c2c = add(tr, "GeometryNodeMeshToCurve", 5, -2, ins={"Mesh": chord_join.outputs[0]})
    cprof = add(tr, "GeometryNodeCurvePrimitiveCircle", 5, -3, ins={"Resolution": 8, "Radius": gin.outputs["Chord Radius"]})
    chords = add(tr, "GeometryNodeCurveToMesh", 6, -2,
                 ins={"Curve": c2c.outputs["Curve"], "Profile Curve": cprof.outputs["Curve"]})
    # zigzag braces on all four faces, ends landing on the chords
    brace_join = add(tr, "GeometryNodeJoinGeometry", 8, 2)
    for side, row, flat in ((1, 2, False), (-1, 4, False), (1, 6, True), (-1, 8, True)):
        tr.links.new(_zigzag(tr, gin, row, L, B, W, H, side, flat), brace_join.inputs[0])
    b2c = add(tr, "GeometryNodeMeshToCurve", 8.6, 2, ins={"Mesh": brace_join.outputs[0]})
    bprof = add(tr, "GeometryNodeCurvePrimitiveCircle", 8.6, 3, ins={"Resolution": 6, "Radius": gin.outputs["Brace Radius"]})
    braces = add(tr, "GeometryNodeCurveToMesh", 9, 2,
                 ins={"Curve": b2c.outputs["Curve"], "Profile Curve": bprof.outputs["Curve"]})
    total = add(tr, "GeometryNodeJoinGeometry", 9.5, 0)
    tr.links.new(chords.outputs["Mesh"], total.inputs[0])
    tr.links.new(braces.outputs["Mesh"], total.inputs[0])
    finish(tr, gin, gout, total.outputs[0])


def gn_panel_array():
    tr, gin, gout = new_group("GN_panel_array", [
        ("Count X", "NodeSocketInt", 8), ("Count Y", "NodeSocketInt", 6),
        ("Panel W", "NodeSocketFloat", 1.0), ("Panel H", "NodeSocketFloat", 1.0),
        ("Gap", "NodeSocketFloat", 0.06), ("Depth", "NodeSocketFloat", 0.05),
        ("Jitter", "NodeSocketFloat", 0.006), ("Seed", "NodeSocketInt", 0),
    ])
    cx, cy = gin.outputs["Count X"], gin.outputs["Count Y"]
    pw, ph = gin.outputs["Panel W"], gin.outputs["Panel H"]
    sx1 = add(tr, "ShaderNodeMath", 0, 0, ins={0: cx, 1: 1.0}, operation="SUBTRACT")
    sx = add(tr, "ShaderNodeMath", 1, 0, ins={0: sx1.outputs[0], 1: pw}, operation="MULTIPLY")
    sy1 = add(tr, "ShaderNodeMath", 0, 1, ins={0: cy, 1: 1.0}, operation="SUBTRACT")
    sy = add(tr, "ShaderNodeMath", 1, 1, ins={0: sy1.outputs[0], 1: ph}, operation="MULTIPLY")
    grid = add(tr, "GeometryNodeMeshGrid", 2, 0,
               ins={"Size X": sx.outputs[0], "Size Y": sy.outputs[0], "Vertices X": cx, "Vertices Y": cy})
    pw_g = add(tr, "ShaderNodeMath", 2, 2, ins={0: pw, 1: gin.outputs["Gap"]}, operation="SUBTRACT")
    ph_g = add(tr, "ShaderNodeMath", 2, 3, ins={0: ph, 1: gin.outputs["Gap"]}, operation="SUBTRACT")
    size = add(tr, "ShaderNodeCombineXYZ", 3, 2,
               ins={"X": pw_g.outputs[0], "Y": ph_g.outputs[0], "Z": gin.outputs["Depth"]})
    cube = add(tr, "GeometryNodeMeshCube", 3, 3, ins={"Size": size.outputs["Vector"]})
    inst = add(tr, "GeometryNodeInstanceOnPoints", 4, 0,
               ins={"Points": grid.outputs["Mesh"], "Instance": cube.outputs["Mesh"]})
    rnd = add(tr, "FunctionNodeRandomValue", 4, 2, data_type="FLOAT")
    tr.links.new(gin.outputs["Seed"], rnd.inputs[8])          # Seed
    rnd.inputs[2].default_value, rnd.inputs[3].default_value = -1.0, 1.0  # float Min/Max
    jit = add(tr, "ShaderNodeMath", 5, 2, ins={0: rnd.outputs[1], 1: gin.outputs["Jitter"]}, operation="MULTIPLY")
    jvec = add(tr, "ShaderNodeCombineXYZ", 6, 2, ins={"Z": jit.outputs[0]})
    trans = add(tr, "GeometryNodeTranslateInstances", 6, 0,
                ins={"Instances": inst.outputs["Instances"], "Translation": jvec.outputs["Vector"]})
    real = add(tr, "GeometryNodeRealizeInstances", 7, 0, ins={"Geometry": trans.outputs["Instances"]})
    finish(tr, gin, gout, real.outputs[0])


def gn_mli_wrap():
    tr, gin, gout = new_group("GN_mli_wrap", [
        ("Amplitude", "NodeSocketFloat", 0.03), ("Crinkle Scale", "NodeSocketFloat", 8.0),
        ("Subdiv", "NodeSocketInt", 2), ("Seed", "NodeSocketFloat", 0.0),
    ], has_geo_in=True)
    sub = add(tr, "GeometryNodeSubdivideMesh", 0, 0,
              ins={"Mesh": gin.outputs["Geometry"], "Level": gin.outputs["Subdiv"]})
    pos = add(tr, "GeometryNodeInputPosition", 0, 2)
    noise = add(tr, "ShaderNodeTexNoise", 1, 2, noise_dimensions="4D",
                ins={"Vector": pos.outputs[0], "W": gin.outputs["Seed"],
                     "Scale": gin.outputs["Crinkle Scale"], "Detail": 4.0})
    cent = add(tr, "ShaderNodeMath", 2, 2, ins={0: noise.outputs["Fac"], 1: 0.5}, operation="SUBTRACT")
    amp2 = add(tr, "ShaderNodeMath", 2, 3, ins={0: gin.outputs["Amplitude"], 1: 2.0}, operation="MULTIPLY")
    mag = add(tr, "ShaderNodeMath", 3, 2, ins={0: cent.outputs[0], 1: amp2.outputs[0]}, operation="MULTIPLY")
    nrm = add(tr, "GeometryNodeInputNormal", 3, 3)
    off = add(tr, "ShaderNodeVectorMath", 4, 2, operation="SCALE",
              ins={0: nrm.outputs[0], "Scale": mag.outputs[0]})
    sp = add(tr, "GeometryNodeSetPosition", 5, 0,
             ins={"Geometry": sub.outputs["Mesh"], "Offset": off.outputs["Vector"]})
    smooth = add(tr, "GeometryNodeSetShadeSmooth", 6, 0, ins={"Geometry": sp.outputs["Geometry"]})
    finish(tr, gin, gout, smooth.outputs["Geometry"])


def gn_scaffold():
    tr, gin, gout = new_group("GN_scaffold", [
        ("Size X", "NodeSocketFloat", 2.0), ("Size Y", "NodeSocketFloat", 2.0),
        ("Size Z", "NodeSocketFloat", 3.0), ("Bays X", "NodeSocketInt", 2),
        ("Bays Y", "NodeSocketInt", 2), ("Bays Z", "NodeSocketInt", 3),
        ("Member Radius", "NodeSocketFloat", 0.025),
    ])
    size = add(tr, "ShaderNodeCombineXYZ", 0, 0,
               ins={"X": gin.outputs["Size X"], "Y": gin.outputs["Size Y"], "Z": gin.outputs["Size Z"]})
    vx = add(tr, "ShaderNodeMath", 0, 1, ins={0: gin.outputs["Bays X"], 1: 1.0}, operation="ADD")
    vy = add(tr, "ShaderNodeMath", 0, 2, ins={0: gin.outputs["Bays Y"], 1: 1.0}, operation="ADD")
    vz = add(tr, "ShaderNodeMath", 0, 3, ins={0: gin.outputs["Bays Z"], 1: 1.0}, operation="ADD")
    cube = add(tr, "GeometryNodeMeshCube", 1, 0,
               ins={"Size": size.outputs["Vector"], "Vertices X": vx.outputs[0],
                    "Vertices Y": vy.outputs[0], "Vertices Z": vz.outputs[0]})
    up = add(tr, "ShaderNodeMath", 2, 2, ins={0: gin.outputs["Size Z"], 1: 0.5}, operation="MULTIPLY")
    upv = add(tr, "ShaderNodeCombineXYZ", 3, 2, ins={"Z": up.outputs[0]})
    lift = add(tr, "GeometryNodeTransform", 3, 0,
               ins={"Geometry": cube.outputs["Mesh"], "Translation": upv.outputs["Vector"]})
    m2c = add(tr, "GeometryNodeMeshToCurve", 4, 0, ins={"Mesh": lift.outputs["Geometry"]})
    prof = add(tr, "GeometryNodeCurvePrimitiveCircle", 4, 1,
               ins={"Resolution": 6, "Radius": gin.outputs["Member Radius"]})
    tubes = add(tr, "GeometryNodeCurveToMesh", 5, 0,
                ins={"Curve": m2c.outputs["Curve"], "Profile Curve": prof.outputs["Curve"]})
    finish(tr, gin, gout, tubes.outputs["Mesh"])


def gn_regolith_berm():
    tr, gin, gout = new_group("GN_regolith_berm", [
        ("Radius", "NodeSocketFloat", 30.0), ("Height", "NodeSocketFloat", 2.5),
        ("Base Width", "NodeSocketFloat", 9.0), ("Gap Angle", "NodeSocketFloat", 40.0),
        ("End Taper", "NodeSocketFloat", 8.0),
        ("Noise", "NodeSocketFloat", 0.15), ("Seed", "NodeSocketFloat", 0.0),
        ("Ground", "NodeSocketObject", None),
    ])
    # arc with the corridor gap centered on +Y
    gap_r = add(tr, "ShaderNodeMath", 0, 0, ins={0: gin.outputs["Gap Angle"], 1: math.pi / 180}, operation="MULTIPLY")
    half = add(tr, "ShaderNodeMath", 1, 0, ins={0: gap_r.outputs[0], 1: 0.5}, operation="MULTIPLY")
    start = add(tr, "ShaderNodeMath", 2, 0, ins={0: half.outputs[0], 1: math.pi / 2}, operation="ADD")
    sweep = add(tr, "ShaderNodeMath", 2, 1, ins={0: 2 * math.pi, 1: gap_r.outputs[0]}, operation="SUBTRACT")
    arc = add(tr, "GeometryNodeCurveArc", 3, 0,
              ins={"Resolution": 96, "Radius": gin.outputs["Radius"],
                   "Start Angle": start.outputs[0], "Sweep Angle": sweep.outputs[0]})
    res = add(tr, "GeometryNodeResampleCurve", 4, 0, ins={"Curve": arc.outputs["Curve"], "Count": 160})
    # tapered closed ends: curve radius ramps 0->1 over End Taper meters, so
    # the profile pinches to a point like a pushed pile; End Taper sets the
    # end's angle to ground (shallower = longer taper)
    total = add(tr, "ShaderNodeMath", 4, 1, ins={0: gin.outputs["Radius"], 1: sweep.outputs[0]}, operation="MULTIPLY")
    sparam = add(tr, "GeometryNodeSplineParameter", 4, 2)
    from_end = add(tr, "ShaderNodeMath", 5, 1, ins={0: total.outputs[0], 1: sparam.outputs["Length"]}, operation="SUBTRACT")
    edge = add(tr, "ShaderNodeMath", 5, 2, ins={0: sparam.outputs["Length"], 1: from_end.outputs[0]}, operation="MINIMUM")
    t_raw = add(tr, "ShaderNodeMath", 6, 2, ins={0: edge.outputs[0], 1: gin.outputs["End Taper"]}, operation="DIVIDE")
    t = add(tr, "ShaderNodeMath", 6.5, 2, ins={0: t_raw.outputs[0], 1: 1.0}, operation="MINIMUM")
    t2 = add(tr, "ShaderNodeMath", 7, 2, ins={0: t.outputs[0], 1: t.outputs[0]}, operation="MULTIPLY")
    tm2 = add(tr, "ShaderNodeMath", 7, 3, ins={0: t.outputs[0], 1: 2.0}, operation="MULTIPLY")
    a3 = add(tr, "ShaderNodeMath", 7.5, 3, ins={0: 3.0, 1: tm2.outputs[0]}, operation="SUBTRACT")
    smooth_t = add(tr, "ShaderNodeMath", 8, 2.5, ins={0: t2.outputs[0], 1: a3.outputs[0]}, operation="MULTIPLY")
    rad = add(tr, "GeometryNodeSetCurveRadius", 5, 0,
              ins={"Curve": res.outputs["Curve"], "Radius": smooth_t.outputs[0]})
    # cosine-bell profile: zero slope at BOTH ground contacts and at the crest
    # (angle-of-repose pile, not a half-ellipse); profile local +Y maps DOWN in
    # the sweep -> negate, FlipFaces later restores winding
    pline = add(tr, "GeometryNodeMeshLine", 3, 4, ins={"Count": 17})
    pidx = add(tr, "GeometryNodeInputIndex", 3, 5)
    u = add(tr, "ShaderNodeMath", 4, 4, ins={0: pidx.outputs[0], 1: 16.0}, operation="DIVIDE")
    ang = add(tr, "ShaderNodeMath", 4.5, 4, ins={0: u.outputs[0], 1: 2 * math.pi}, operation="MULTIPLY")
    cosv = add(tr, "ShaderNodeMath", 5, 4, ins={0: ang.outputs[0]}, operation="COSINE")
    bell = add(tr, "ShaderNodeMath", 5.5, 4, ins={0: 1.0, 1: cosv.outputs[0]}, operation="SUBTRACT")
    hh = add(tr, "ShaderNodeMath", 5.5, 5, ins={0: gin.outputs["Height"], 1: -0.5}, operation="MULTIPLY")
    py = add(tr, "ShaderNodeMath", 6, 4, ins={0: bell.outputs[0], 1: hh.outputs[0]}, operation="MULTIPLY")
    uc = add(tr, "ShaderNodeMath", 6, 5, ins={0: u.outputs[0], 1: 0.5}, operation="SUBTRACT")
    pxp = add(tr, "ShaderNodeMath", 6.5, 5, ins={0: uc.outputs[0], 1: gin.outputs["Base Width"]}, operation="MULTIPLY")
    ppos = add(tr, "ShaderNodeCombineXYZ", 7, 4, ins={"X": pxp.outputs[0], "Y": py.outputs[0]})
    pset = add(tr, "GeometryNodeSetPosition", 7.5, 4,
               ins={"Geometry": pline.outputs["Mesh"], "Position": ppos.outputs["Vector"]})
    pcurve = add(tr, "GeometryNodeMeshToCurve", 8, 4, ins={"Mesh": pset.outputs["Geometry"]})
    swept = add(tr, "GeometryNodeCurveToMesh", 6, 0,
                ins={"Curve": rad.outputs["Curve"], "Profile Curve": pcurve.outputs["Curve"]})
    # noise displacement
    pos = add(tr, "GeometryNodeInputPosition", 6, 2)
    noise = add(tr, "ShaderNodeTexNoise", 7, 2, noise_dimensions="4D",
                ins={"Vector": pos.outputs[0], "W": gin.outputs["Seed"], "Scale": 0.35, "Detail": 5.0})
    cent = add(tr, "ShaderNodeMath", 8, 2, ins={0: noise.outputs["Fac"], 1: 0.5}, operation="SUBTRACT")
    amp = add(tr, "ShaderNodeMath", 8, 3, ins={0: gin.outputs["Height"], 1: gin.outputs["Noise"]}, operation="MULTIPLY")
    mag = add(tr, "ShaderNodeMath", 9, 2, ins={0: cent.outputs[0], 1: amp.outputs[0]}, operation="MULTIPLY")
    nrm = add(tr, "GeometryNodeInputNormal", 9, 3)
    off = add(tr, "ShaderNodeVectorMath", 10, 2, operation="SCALE",
              ins={0: nrm.outputs[0], "Scale": mag.outputs[0]})
    sp = add(tr, "GeometryNodeSetPosition", 10, 0,
             ins={"Geometry": swept.outputs["Mesh"], "Offset": off.outputs["Vector"]})
    # shrinkwrap-to-ground: raycast down onto the Ground object and lift each
    # vertex by the terrain height, so the berm follows uneven ground smoothly
    ginfo = add(tr, "GeometryNodeObjectInfo", 9, 5, transform_space="RELATIVE",
                ins={"Object": gin.outputs["Ground"]})
    rpos = add(tr, "GeometryNodeInputPosition", 9, 6)
    high = add(tr, "ShaderNodeVectorMath", 9.5, 6, operation="ADD",
               ins={0: rpos.outputs[0], 1: (0.0, 0.0, 200.0)})
    ray = add(tr, "GeometryNodeRaycast", 10, 5,
              ins={"Target Geometry": ginfo.outputs["Geometry"],
                   "Source Position": high.outputs["Vector"],
                   "Ray Direction": (0.0, 0.0, -1.0), "Ray Length": 500.0})
    hitz = add(tr, "ShaderNodeSeparateXYZ", 10.5, 5, ins={0: ray.outputs["Hit Position"]})
    gated = add(tr, "ShaderNodeMath", 11, 5, ins={0: hitz.outputs["Z"], 1: ray.outputs["Is Hit"]}, operation="MULTIPLY")
    lift = add(tr, "ShaderNodeCombineXYZ", 11.5, 5, ins={"Z": gated.outputs[0]})
    wrap = add(tr, "GeometryNodeSetPosition", 12, 0,
               ins={"Geometry": sp.outputs["Geometry"], "Offset": lift.outputs["Vector"]})
    flip = add(tr, "GeometryNodeFlipFaces", 12.5, 0, ins={"Mesh": wrap.outputs["Geometry"]})
    smooth = add(tr, "GeometryNodeSetShadeSmooth", 13, 0, ins={"Geometry": flip.outputs["Mesh"]})
    finish(tr, gin, gout, smooth.outputs["Geometry"], col=13.5)


def gn_surface_disturbance():
    tr, gin, gout = new_group("GN_surface_disturbance", [
        ("Density", "NodeSocketFloat", 0.4), ("Falloff Radius", "NodeSocketFloat", 60.0),
        ("Inner Radius", "NodeSocketFloat", 0.0),
        ("Rocks", "NodeSocketCollection", None),
        ("Scale Min", "NodeSocketFloat", 0.06), ("Scale Max", "NodeSocketFloat", 0.3),
        ("Yaw Random", "NodeSocketFloat", 1.0), ("Tilt Random", "NodeSocketFloat", 0.15),
        ("Seed", "NodeSocketInt", 0),
    ], has_geo_in=True)
    pos = add(tr, "GeometryNodeInputPosition", -1, 2)
    dist = add(tr, "ShaderNodeVectorMath", 0, 2, operation="LENGTH", ins={0: pos.outputs[0]})
    ratio = add(tr, "ShaderNodeMath", 1, 2, ins={0: dist.outputs["Value"], 1: gin.outputs["Falloff Radius"]}, operation="DIVIDE")
    fall = add(tr, "ShaderNodeMath", 2, 2, ins={0: 1.0, 1: ratio.outputs[0]}, operation="SUBTRACT")
    clamped = add(tr, "ShaderNodeMath", 3, 2, ins={0: fall.outputs[0], 1: 0.0}, operation="MAXIMUM")
    outside = add(tr, "ShaderNodeMath", 3, 3, ins={0: dist.outputs["Value"], 1: gin.outputs["Inner Radius"]}, operation="GREATER_THAN")
    ring = add(tr, "ShaderNodeMath", 4, 3, ins={0: clamped.outputs[0], 1: outside.outputs[0]}, operation="MULTIPLY")
    dens = add(tr, "ShaderNodeMath", 4, 2, ins={0: ring.outputs[0], 1: gin.outputs["Density"]}, operation="MULTIPLY")
    pts = add(tr, "GeometryNodeDistributePointsOnFaces", 5, 0,
              ins={"Mesh": gin.outputs["Geometry"], "Density": dens.outputs[0], "Seed": gin.outputs["Seed"]})
    # rock models from a collection, random pick per point
    rocks = add(tr, "GeometryNodeCollectionInfo", 5, 3,
                ins={"Collection": gin.outputs["Rocks"], "Separate Children": True, "Reset Children": True})
    # rotation: surface-aligned, then random yaw/tilt scaled by the inputs
    yaw = add(tr, "ShaderNodeMath", 4, 4, ins={0: gin.outputs["Yaw Random"], 1: math.pi}, operation="MULTIPLY")
    tilt = add(tr, "ShaderNodeMath", 4, 5, ins={0: gin.outputs["Tilt Random"], 1: 0.6}, operation="MULTIPLY")
    nyaw = add(tr, "ShaderNodeMath", 5, 4, ins={0: yaw.outputs[0], 1: -1.0}, operation="MULTIPLY")
    ntilt = add(tr, "ShaderNodeMath", 5, 5, ins={0: tilt.outputs[0], 1: -1.0}, operation="MULTIPLY")
    rmin = add(tr, "ShaderNodeCombineXYZ", 6, 4,
               ins={"X": ntilt.outputs[0], "Y": ntilt.outputs[0], "Z": nyaw.outputs[0]})
    rmax = add(tr, "ShaderNodeCombineXYZ", 6, 5,
               ins={"X": tilt.outputs[0], "Y": tilt.outputs[0], "Z": yaw.outputs[0]})
    rrot = add(tr, "FunctionNodeRandomValue", 7, 4, data_type="FLOAT_VECTOR")
    tr.links.new(rmin.outputs["Vector"], rrot.inputs[0])
    tr.links.new(rmax.outputs["Vector"], rrot.inputs[1])
    tr.links.new(gin.outputs["Seed"], rrot.inputs[8])
    rot = add(tr, "FunctionNodeRotateRotation", 8, 4, rotation_space="LOCAL",
              ins={"Rotation": pts.outputs["Rotation"], "Rotate By": rrot.outputs[0]})
    inst = add(tr, "GeometryNodeInstanceOnPoints", 6, 0,
               ins={"Points": pts.outputs["Points"], "Instance": rocks.outputs["Instances"],
                    "Pick Instance": True, "Rotation": rot.outputs[0]})
    rnd = add(tr, "FunctionNodeRandomValue", 6, 2, data_type="FLOAT")
    tr.links.new(gin.outputs["Scale Min"], rnd.inputs[2])
    tr.links.new(gin.outputs["Scale Max"], rnd.inputs[3])
    tr.links.new(gin.outputs["Seed"], rnd.inputs[8])
    scaled = add(tr, "GeometryNodeScaleInstances", 8, 0,
                 ins={"Instances": inst.outputs["Instances"], "Scale": rnd.outputs[1]})
    real = add(tr, "GeometryNodeRealizeInstances", 9, 0, ins={"Geometry": scaled.outputs["Instances"]})
    finish(tr, gin, gout, real.outputs[0])


def build_kit(out_path: str) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for fn in (gn_truss, gn_panel_array, gn_mli_wrap, gn_scaffold, gn_regolith_berm, gn_surface_disturbance):
        fn()

    mat = bpy.data.materials.new("M_gn_kit_proxy")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.45, 0.45, 0.45, 1)
    mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85

    coll = bpy.data.collections.new("AST_gn_kit")
    bpy.context.scene.collection.children.link(coll)

    # demo rock set for GN_surface_disturbance (swap for real rocks per scene)
    import random
    rng = random.Random(7)
    rocks_coll = bpy.data.collections.new("gn_kit_rocks")
    bpy.context.scene.collection.children.link(rocks_coll)
    for i in range(4):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0, location=(170 + i * 3, -40, 1.0))
        rock = bpy.context.object
        rock.name = f"gn_kit_rock_{chr(97 + i)}"
        squash = (1.0, 0.75 + 0.2 * rng.random(), 0.55 + 0.2 * rng.random())
        for v in rock.data.vertices:
            v.co.x *= squash[0] * (1 + 0.5 * (rng.random() - 0.5))
            v.co.y *= squash[1] * (1 + 0.5 * (rng.random() - 0.5))
            v.co.z *= squash[2] * (1 + 0.5 * (rng.random() - 0.5))
        bpy.ops.object.shade_smooth()
        rock.data.materials.append(mat)
        for c in rock.users_collection:
            c.objects.unlink(rock)
        rocks_coll.objects.link(rock)

    demos = [
        ("gn_kit_truss", "GN_truss", None, (0, 0)),
        ("gn_kit_panel_array", "GN_panel_array", None, (10, 0)),
        ("gn_kit_mli_wrap", "GN_mli_wrap", "cylinder", (22, 0)),
        ("gn_kit_scaffold", "GN_scaffold", None, (30, 0)),
        ("gn_kit_regolith_berm", "GN_regolith_berm", None, (110, 0)),
        ("gn_kit_disturbance", "GN_surface_disturbance", "grid", (190, 0)),
    ]
    for name, group, base, (px, py) in demos:
        if base == "cylinder":
            bpy.ops.mesh.primitive_cylinder_add(radius=1.5, depth=3.0, location=(px, py, 1.5))
        elif base == "grid":
            bpy.ops.mesh.primitive_plane_add(size=60, location=(px, py, 0))
        else:
            bpy.ops.mesh.primitive_plane_add(size=0.01, location=(px, py, 0))
        ob = bpy.context.object
        ob.name = name
        ob["procedural_ok"] = 1
        mod = ob.modifiers.new(group, "NODES")
        mod.node_group = bpy.data.node_groups[group]
        ids = {it.name: it.identifier for it in mod.node_group.interface.items_tree
               if it.item_type == "SOCKET" and it.in_out == "INPUT"}
        mod[ids["Material"]] = mat
        if group == "GN_surface_disturbance":
            mod[ids["Rocks"]] = rocks_coll
        ob.data.materials.append(mat)  # slot mirrors the GN Set Material (validator A007)
        for c in ob.users_collection:
            c.objects.unlink(ob)
        coll.objects.link(ob)

    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    print(f"GN KIT SAVED: {out_path} ({len(bpy.data.node_groups)} groups, {len(coll.objects)} demos)")


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    build_kit(args.out)


if __name__ == "__main__":
    main()
