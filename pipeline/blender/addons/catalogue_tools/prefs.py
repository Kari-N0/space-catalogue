"""Add-on preferences (ADDON.md §2): repo paths, WSL distro, job poll interval."""

import bpy

DEFAULT_REPO_WIN = r"\\wsl.localhost\Ubuntu-24.04\home\karin\dev\space-catalogue"


class CatalogueToolsPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    repo_windows: bpy.props.StringProperty(
        name="Dev repo (optional)",
        description="space-catalogue repo checkout — ONLY relevant on the dev "
                    "machine: prefers the repo's pipeline modules over the copy "
                    "bundled in this add-on and shows CLI-launched job status. "
                    "Ignored when the path doesn't exist; leave as-is elsewhere",
        default=DEFAULT_REPO_WIN,
    )
    poll_seconds: bpy.props.FloatProperty(
        name="Job poll interval (s)",
        default=3.0, min=1.0, max=30.0,
    )
    block_c_drive: bpy.props.BoolProperty(
        name="Block C: as output drive",
        description="refuse dataset output on C: (space-catalogue machine rule; "
                    "disable on computers where C: is the only drive)",
        default=True,
    )

    def draw(self, _context):
        col = self.layout.column()
        col.prop(self, "poll_seconds")
        col.prop(self, "block_c_drive")
        col.separator()
        col.label(text="Everything below is optional (space-catalogue dev machine only):")
        col.prop(self, "repo_windows")


class _DefaultPrefs:
    """Fallback for the live-dev loop: a manually register()-ed add-on has no
    entry in preferences.addons until it's enabled through the extension
    system. Same defaults as the real preferences."""
    repo_windows = DEFAULT_REPO_WIN
    poll_seconds = 3.0
    block_c_drive = True


def get_prefs():
    entry = bpy.context.preferences.addons.get(__package__)
    return entry.preferences if entry is not None else _DefaultPrefs()
