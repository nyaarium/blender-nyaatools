"""
Mesh preparation for asset export.
"""

import bpy


def prepare_mesh_for_export(obj, armature=None):
    """
    Prepare a mesh for export by cleaning up.

    - Removes internal UV maps (prefixed with "--")
    - Optionally parents to armature with new Armature modifier
    """

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
