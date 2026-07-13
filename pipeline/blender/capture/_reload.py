"""Dev helper: reload the capture package inside a long-lived Blender session.

The MCP workflow edits modules on the WSL side while Windows Blender keeps the
imported copies cached for the life of the process. After editing, run:

    from pipeline.blender.capture import _reload; _reload.reload_all()
"""

import importlib


def reload_all():
    importlib.invalidate_caches()
    from pipeline.blender.capture import (  # noqa: F401
        convention, export_dataset, export_envelope, frames, presets, preview,
        rig, validity,
    )
    # dependency order: leaves first
    for mod in (frames, presets, validity, convention, rig, preview,
                export_envelope, export_dataset):
        importlib.reload(mod)
    print("capture package reloaded")
