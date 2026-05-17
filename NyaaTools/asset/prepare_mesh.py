"""
Mesh preparation for asset export.
"""

import bpy


def prepare_mesh_for_export(obj, armature=None):
    """
    Prepare a mesh for export by cleaning up.

    - Removes internal UV maps (prefixed with "--")
    - Optionally parents to armature, rewiring existing Armature modifier
      (or creating one if none exists)
    """

    # Remove UV maps beginning with "--"
    for uv in obj.data.uv_layers:
        if uv.name.startswith("--"):
            obj.data.uv_layers.remove(uv)

    if armature is not None:
        arm_mod = next((m for m in obj.modifiers if m.type == "ARMATURE"), None)
        if arm_mod is None:
            arm_mod = obj.modifiers.new(name="Armature", type="ARMATURE")
        arm_mod.object = armature
        obj.parent = armature
    else:
        obj.parent = None
