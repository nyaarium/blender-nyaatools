"""
Mesh preparation for asset export.
"""

import bpy

from .apply_export_modifiers import apply_export_modifiers


def prepare_mesh_for_export(obj, armature=None):
    """
    Prepare a mesh for export by applying modifiers and cleaning up.

    - Applies export modifiers
    - Removes internal UV maps (prefixed with "--")
    - Optionally parents to armature with new Armature modifier
    """
    apply_export_modifiers(obj)

    # Remove UV maps beginning with "--"
    for uv in obj.data.uv_layers:
        if uv.name.startswith("--"):
            obj.data.uv_layers.remove(uv)

    if armature is not None:
        obj.modifiers.new(name="Armature", type="ARMATURE")
        obj.modifiers["Armature"].object = armature
        obj.parent = armature
    else:
        obj.parent = None
