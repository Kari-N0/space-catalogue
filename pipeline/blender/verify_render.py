"""Phase 8a VERIFY (SETUP.md): tiny Cycles GPU render on Windows Blender.

Renders the default scene at 64x64 with OptiX to D:\\renders\\_verify\\.
Prints the enabled compute devices so the log can record whether OptiX ran.
"""

import bpy

prefs = bpy.context.preferences.addons["cycles"].preferences
prefs.compute_device_type = "OPTIX"
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == "OPTIX"
    print(f"DEVICE {d.type} {d.name} use={d.use}")

sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "GPU"
sc.cycles.samples = 8
sc.render.resolution_x = 64
sc.render.resolution_y = 64
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = r"D:\renders\_verify\blender_win_64"

bpy.ops.render.render(write_still=True)
print("RENDER DONE")
