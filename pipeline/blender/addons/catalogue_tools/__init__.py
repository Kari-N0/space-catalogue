"""Catalogue Tools — Blender 5.1 add-on, module 1: splat capture (CAPTURE.md §8).

Thin UI over pipeline/blender/capture/ (ADDON.md §1 rules: no logic forks, no
ML imports, long jobs run WSL-side and are polled via jobs/*/status.json).

Dev loop: registered live over MCP; after code edits run
    import catalogue_tools; catalogue_tools.reload_and_reregister()
Production install: packaged as a Blender extension (blender_manifest.toml).
"""

import importlib

bl_info = {
    "name": "Catalogue Tools",
    "author": "space-catalogue",
    "version": (0, 1, 0),
    "blender": (5, 1, 0),
    "location": "3D Viewport ▸ Sidebar (N) ▸ Catalogue",
    "description": "Splat capture vantages: author, preview, execute (CAPTURE.md)",
    "category": "3D View",
}

from . import jobs, ops, panel, paths, prefs  # noqa: E402

import bpy  # noqa: E402

_ALL_CLASSES = (prefs.CatalogueToolsPreferences,) + panel.CLASSES + ops.CLASSES


def register():
    for cls in _ALL_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.catalogue_tools = bpy.props.PointerProperty(
        type=panel.CatalogueToolsState)
    jobs.start()


def unregister():
    jobs.stop()
    del bpy.types.WindowManager.catalogue_tools
    for cls in reversed(_ALL_CLASSES):
        bpy.utils.unregister_class(cls)


def reload_and_reregister():
    """Dev helper: unregister, reload all submodules, register again."""
    global _ALL_CLASSES
    try:
        unregister()
    except Exception:
        pass
    for mod in (paths, prefs, jobs, ops, panel):
        importlib.reload(mod)
    _ALL_CLASSES = (prefs.CatalogueToolsPreferences,) + panel.CLASSES + ops.CLASSES
    register()
    print("catalogue_tools reloaded + re-registered")
