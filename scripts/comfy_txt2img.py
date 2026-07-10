#!/usr/bin/env python3
"""Queue a text-to-image workflow on a running ComfyUI server and save the PNG.

The pipeline's programmatic entry point (Phase 6, SETUP.md). Talks plain HTTP
to 127.0.0.1:8188 — run scripts/comfy-server.sh first.

Usage:
    comfy_txt2img.py "a lunar habitat at dawn" [--checkpoint FILE] [--out DIR]
                     [--template workflow_api.json] [--width N] [--height N]
                     [--steps N] [--cfg F] [--seed N] [--negative TEXT]

A workflow template is a ComfyUI *API format* JSON export whose string values
may contain the placeholders {PROMPT}, {NEGATIVE}, {CHECKPOINT}, {WIDTH},
{HEIGHT}, {STEPS}, {CFG}, {SEED}. Without --template, a minimal
CheckpointLoaderSimple->KSampler graph is used (fits all-in-one SD-style
checkpoints; model-specific templates live next to this script).
"""

import argparse
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8188"

DEFAULT_TEMPLATE = {
    "1": {"class_type": "CheckpointLoaderSimple",
          "inputs": {"ckpt_name": "{CHECKPOINT}"}},
    "2": {"class_type": "CLIPTextEncode",
          "inputs": {"text": "{PROMPT}", "clip": ["1", 1]}},
    "3": {"class_type": "CLIPTextEncode",
          "inputs": {"text": "{NEGATIVE}", "clip": ["1", 1]}},
    "4": {"class_type": "EmptyLatentImage",
          "inputs": {"width": "{WIDTH}", "height": "{HEIGHT}", "batch_size": 1}},
    "5": {"class_type": "KSampler",
          "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
                     "latent_image": ["4", 0], "seed": "{SEED}", "steps": "{STEPS}",
                     "cfg": "{CFG}", "sampler_name": "euler", "scheduler": "normal",
                     "denoise": 1.0}},
    "6": {"class_type": "VAEDecode",
          "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
    "7": {"class_type": "SaveImage",
          "inputs": {"images": ["6", 0], "filename_prefix": "txt2img"}},
}

INT_KEYS = {"{WIDTH}", "{HEIGHT}", "{STEPS}", "{SEED}"}
FLOAT_KEYS = {"{CFG}"}


def fill(node, subs):
    if isinstance(node, dict):
        return {k: fill(v, subs) for k, v in node.items()}
    if isinstance(node, list):
        return [fill(v, subs) for v in node]
    if isinstance(node, str):
        if node in INT_KEYS:
            return int(subs[node])
        if node in FLOAT_KEYS:
            return float(subs[node])
        for k, v in subs.items():
            node = node.replace(k, str(v))
        return node
    return node


def api(path, payload=None, timeout=30):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt")
    ap.add_argument("--negative", default="blurry, low quality, watermark, text")
    ap.add_argument("--checkpoint", default="", help="ckpt filename as the server sees it")
    ap.add_argument("--template", default="", help="API-format workflow JSON with placeholders")
    ap.add_argument("--out", default=".", help="directory for the saved PNG")
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--cfg", type=float, default=5.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--timeout", type=int, default=600, help="generation timeout, seconds")
    args = ap.parse_args()

    if args.template:
        with open(args.template) as f:
            graph = json.load(f)
    else:
        graph = DEFAULT_TEMPLATE
        if not args.checkpoint:
            ckpts = api("/object_info/CheckpointLoaderSimple")[
                "CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
            if not ckpts:
                print("No checkpoints installed on the server", file=sys.stderr)
                return 1
            args.checkpoint = ckpts[0]

    subs = {"{PROMPT}": args.prompt, "{NEGATIVE}": args.negative,
            "{CHECKPOINT}": args.checkpoint, "{WIDTH}": args.width,
            "{HEIGHT}": args.height, "{STEPS}": args.steps,
            "{CFG}": args.cfg, "{SEED}": args.seed}
    graph = fill(graph, subs)

    prompt_id = api("/prompt", {"prompt": graph})["prompt_id"]
    print(f"queued {prompt_id}")

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        hist = api(f"/history/{prompt_id}")
        if prompt_id in hist:
            status = hist[prompt_id].get("status", {})
            if status.get("status_str") == "error":
                print(json.dumps(status, indent=2)[:2000], file=sys.stderr)
                return 1
            outputs = hist[prompt_id].get("outputs", {})
            images = [im for node in outputs.values() for im in node.get("images", [])]
            if images:
                im = images[0]
                url = (f"{BASE}/view?filename={urllib.request.quote(im['filename'])}"
                       f"&subfolder={urllib.request.quote(im.get('subfolder', ''))}"
                       f"&type={im.get('type', 'output')}")
                dest = f"{args.out.rstrip('/')}/{im['filename']}"
                with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as f:
                    f.write(r.read())
                print(f"saved {dest}")
                return 0
        time.sleep(2)

    print("timed out waiting for generation", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
