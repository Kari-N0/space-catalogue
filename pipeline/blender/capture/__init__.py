"""Splat capture system (CAPTURE.md) — vantage authoring, rig preview, dataset
export, and the training↔runtime envelope contract.

IMPORTANT: no bpy import at package level. frames.py and presets.py are pure
Python (usable from WSL CPython and pipeline/checks/check_capture.py); the
bpy-dependent modules (convention, validity, rig, preview, export_dataset,
export_envelope) import bpy themselves and only run inside Blender 5.1.
Everything here stays ML-free (M2/M2.5 rule: the Catalogue Tools add-on imports
pipeline.blender.* in-process; torch/gsplat live WSL-side only).
"""

CAPTURE_SCHEMA_VERSION = 1
