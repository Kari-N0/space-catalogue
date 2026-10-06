#!/usr/bin/env python3
"""Remove scene-level custom properties ("extras") from .glb files.

Blender's glTF exporter writes every custom property into the file. Add-ons
keep their settings as custom properties of the scene, so they travel into
the export: the Concept 002 engine models each carried a 58 KB block of an
add-on's settings and an identifier in `scenes[0].extras` (found 2026-10-06).
Nothing on the site reads scene extras.

What this does, and nothing else: deletes the `extras` member of every scene
in the file's JSON part. Node extras (part titles, explode offsets, flow data)
are the project's own data and stay. The binary part (all geometry) is copied
byte for byte, and the rest of the JSON is written back exactly as it was:
the tool first checks that re-writing the untouched JSON reproduces the
original bytes, and refuses to change a file where it does not.

    python3 pipeline/pack/strip-glb-scene-extras.py [--check] file.glb [more.glb ...]

--check only reports (exit code 1 if any file still carries scene extras).
Run it on every freshly exported model before committing it.
"""
import hashlib
import json
import struct
import sys

JSON_CHUNK, BIN_CHUNK = 0x4E4F534A, 0x004E4942


def read_glb(data):
    magic, version, total = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or version != 2 or total != len(data):
        raise ValueError("not a glTF 2 binary file, or its length field is wrong")
    chunks, off = [], 12
    while off < len(data):
        length, kind = struct.unpack_from("<II", data, off)
        chunks.append((kind, data[off + 8:off + 8 + length]))
        off += 8 + length
    if not chunks or chunks[0][0] != JSON_CHUNK:
        raise ValueError("first chunk is not JSON")
    return chunks


def dump(doc):
    # the settings Blender's exporter writes with
    return json.dumps(doc, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def process(path, check_only):
    data = open(path, "rb").read()
    chunks = read_glb(data)
    raw = chunks[0][1]
    doc = json.loads(raw)
    found = {i: sorted(s["extras"]) if isinstance(s["extras"], dict) else ["(value)"]
             for i, s in enumerate(doc.get("scenes", [])) if "extras" in s}
    if not found:
        print(f"clean     {path}")
        return False
    if check_only:
        print(f"HAS EXTRAS {path}: scene extras {found}")
        return True
    if dump(doc) != raw.rstrip(b" "):
        raise ValueError(f"{path}: cannot rewrite this file's JSON byte for byte; left untouched")
    before = json.loads(raw)
    for scene in doc["scenes"]:
        scene.pop("extras", None)
    for scene in before["scenes"]:
        scene.pop("extras", None)
    assert doc == before
    new_json = dump(doc)
    new_json += b" " * (-len(new_json) % 4)
    out = bytearray(struct.pack("<II", len(new_json), JSON_CHUNK) + new_json)
    for kind, body in chunks[1:]:
        out += struct.pack("<II", len(body), kind) + body
    out = struct.pack("<4sII", b"glTF", 2, 12 + len(out)) + bytes(out)
    # prove it: same binary chunks, same JSON apart from the removed member
    again = read_glb(out)
    assert [c for c in again[1:]] == [c for c in chunks[1:]]
    assert json.loads(again[0][1]) == before
    open(path, "wb").write(out)
    print(f"stripped  {path}: scene extras {found} removed, "
          f"{len(data)} -> {len(out)} bytes, sha256 {hashlib.sha256(out).hexdigest()}")
    return True


def main(argv):
    check_only = "--check" in argv
    files = [a for a in argv if a != "--check"]
    if not files:
        print(__doc__)
        return 2
    hits = [process(p, check_only) for p in files]
    return 1 if (check_only and any(hits)) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
