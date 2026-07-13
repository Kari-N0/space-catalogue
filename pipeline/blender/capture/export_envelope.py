"""Envelope sidecar export — bpy script (ML-free), no rendering.

Re-derives a vantage's runtime envelope from the rig (deterministic, same code
as preview/export) and writes the sidecar JSON that
pipeline/pack/envelope_to_concept.py merges into the concept page. Lets a
preview-approved envelope reach the web contract without a full dataset run.

Headless:
    pipeline/blender/blender-win.sh -b <scene.blend> --python \\
        pipeline/blender/capture/export_envelope.py -- --vantage <name> \\
        --out /home/karin/dev/space-catalogue/pipeline/provenance/<concept>/capture-<name>.envelope.json

Importable / MCP:
    from pipeline.blender.capture import export_envelope
    export_envelope.export_envelope("rehearsal", out_path=None)  # returns dict
"""

import argparse
import json
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import bpy  # noqa: E402

from pipeline.blender.capture import convention, rig  # noqa: E402


def export_envelope(vantage, out_path=None, concept="lunar-base"):
    if out_path and os.name == "nt" and out_path.startswith("/"):
        raise RuntimeError(
            f"--out reached Windows Blender unconverted: {out_path!r}. blender-win.sh only "
            "wslpath-converts paths whose parent exists — create the directory WSL-side first")
    vantages = convention.find_vantages()
    if vantage not in vantages:
        raise RuntimeError(f"no vantage {vantage!r} (have: {sorted(vantages)})")
    result = rig.generate_rig(vantages[vantage], render_fidelity=bpy.app.background)
    sidecar = {
        "schema": "capture-envelope v1",
        "concept": concept,
        "vantage": vantage,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "blend_file": bpy.data.filepath,
        "rig_hash": result["hash"],
        "focus_blender": result["focus_blender"],
        "envelope": result["envelope"],
        "object_envelopes": result["object_envelopes"],
        "warnings": result["warnings"],
    }
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as fh:
            json.dump(sidecar, fh, indent=2)
        print(f"ENVELOPE SIDECAR -> {out_path}")
    else:
        print(json.dumps(sidecar, indent=2))
    return sidecar


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vantage", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--concept", default="lunar-base")
    args = ap.parse_args(argv)
    export_envelope(args.vantage, out_path=args.out, concept=args.concept)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
