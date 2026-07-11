"""relink_nodegroup.py — replace a node group with the version from a library blend.

Janitor tool (ASSETS.md loop): assets carry appended COPIES of kit node groups;
when the kit fixes a generator, this swaps the stale copy for the new one
without touching anything else in the file.

    pipeline/blender/blender-win.sh -b <asset.blend> --python pipeline/blender/relink_nodegroup.py -- \
        --group GN_regolith_berm --lib <gn_kit_v003.blend> --save <asset_vNNN.blend>

Importable: relink(group_name, lib_blend) -> None
"""

import argparse
import os
import sys

import bpy


def relink(group_name: str, lib_blend: str) -> None:
    old = bpy.data.node_groups.get(group_name)
    if old is None:
        raise KeyError(f"{group_name} not present in this file")
    old.name = f"{group_name}__stale"
    bpy.ops.wm.append(directory=os.path.join(lib_blend, "NodeTree") + os.sep, filename=group_name)
    new = bpy.data.node_groups[group_name]
    old.user_remap(new)
    bpy.data.node_groups.remove(old)
    print(f"RELINKED: {group_name} <- {os.path.basename(lib_blend)}")


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--group", required=True)
    ap.add_argument("--lib", required=True)
    ap.add_argument("--save", required=True)
    args = ap.parse_args(argv)
    relink(args.group, args.lib)
    bpy.ops.wm.save_as_mainfile(filepath=args.save)
    print(f"SAVED: {args.save}")


if __name__ == "__main__":
    main()
