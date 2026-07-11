#!/usr/bin/env python
"""contact_sheet.py — assemble labeled sun-study frames into one contact sheet.

Runs in the `terrain` conda env:
    ~/miniconda3/envs/terrain/bin/python pipeline/terrain/contact_sheet.py \
        --dir /mnt/d/renders/lunar-base/audition/site01 \
        --label "Connecting Ridge (Site 001)" --out .../site01_contact.png

Identical layout for every site (D2 audition methodology): 6x4 grid of the 24
azimuth frames, each tile labeled with its azimuth, a header bar with the site
name and render settings.

Importable API: contact_sheet(frame_dir, label, out_path, cols=6) -> str
"""

from __future__ import annotations

import argparse
import glob
import os

from PIL import Image, ImageDraw, ImageFont

TILE_W = 640
HEADER_H = 60
LABEL_H = 24
PAD = 4


def _font(size: int):
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def contact_sheet(frame_dir: str, label: str, out_path: str, cols: int = 6) -> str:
    frames = sorted(glob.glob(os.path.join(frame_dir, "az_*.png")))
    if not frames:
        raise FileNotFoundError(f"no az_*.png frames in {frame_dir}")
    rows = (len(frames) + cols - 1) // cols

    first = Image.open(frames[0])
    tile_h = round(TILE_W * first.height / first.width)
    sheet = Image.new(
        "RGB",
        (cols * TILE_W + (cols + 1) * PAD,
         HEADER_H + rows * (tile_h + LABEL_H + PAD) + PAD),
        (16, 16, 16),
    )
    draw = ImageDraw.Draw(sheet)
    draw.text((PAD * 3, 14), f"{label}  —  sun study, elevation +1.5°, {len(frames)} azimuths (tile frame), AgX @ −4.5 EV",
              fill=(230, 230, 230), font=_font(24))

    for i, path in enumerate(frames):
        r, c = divmod(i, cols)
        x = PAD + c * (TILE_W + PAD)
        y = HEADER_H + r * (tile_h + LABEL_H + PAD)
        img = Image.open(path).convert("RGB").resize((TILE_W, tile_h), Image.LANCZOS)
        sheet.paste(img, (x, y))
        az = os.path.basename(path)[3:6]
        draw.text((x + 4, y + tile_h + 3), f"az {int(az):03d}°", fill=(200, 200, 200), font=_font(16))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    sheet.save(out_path)
    print(f"CONTACT SHEET: {out_path} ({len(frames)} frames, {sheet.width}x{sheet.height})")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dir", required=True, help="directory with az_*.png frames")
    ap.add_argument("--label", required=True, help="header label (site name)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cols", type=int, default=6)
    args = ap.parse_args()
    contact_sheet(args.dir, args.label, args.out, args.cols)


if __name__ == "__main__":
    main()
