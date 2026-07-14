"""Add-on preferences (ADDON.md §2): repo paths, WSL distro, job poll interval."""

import bpy

DEFAULT_REPO_WIN = r"\\wsl.localhost\Ubuntu-24.04\home\karin\dev\space-catalogue"


class CatalogueToolsPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    repo_windows: bpy.props.StringProperty(
        name="Repo (Windows path)",
        description="space-catalogue repo as Windows Blender sees it",
        default=DEFAULT_REPO_WIN,
    )
    wsl_distro: bpy.props.StringProperty(
        name="WSL distro",
        default="Ubuntu-24.04",
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
        col.prop(self, "repo_windows")
        col.prop(self, "wsl_distro")
        col.prop(self, "poll_seconds")
        col.prop(self, "block_c_drive")


class _DefaultPrefs:
    """Fallback for the live-dev loop: a manually register()-ed add-on has no
    entry in preferences.addons until it's enabled through the extension
    system. Same defaults as the real preferences."""
    repo_windows = DEFAULT_REPO_WIN
    wsl_distro = "Ubuntu-24.04"
    poll_seconds = 3.0


def get_prefs():
    entry = bpy.context.preferences.addons.get(__package__)
    return entry.preferences if entry is not None else _DefaultPrefs()
