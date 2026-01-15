"""
Layer merging for asset export.
"""

import bpy

from .prepare_mesh import prepare_mesh_for_export
from ..common.deselect_all import deselect_all
from ..common.selection_add import selection_add


def merge_onto_layer(layer_name, source_obj, armature=None):
    """
    Merge a mesh onto a layer target.

    Args:
        layer_name: Name of the layer (target object should have this name)
        source_obj: Mesh to merge onto the layer
        armature: Optional armature to parent to
    """
    prepare_mesh_for_export(source_obj, armature)

    # Update view layer to ensure objects are accessible
    bpy.context.view_layer.update()

    # Get target from scene
    target = bpy.context.scene.objects.get(layer_name)
    if target is None:
        # Target doesn't exist - source IS the layer foundation
        return

    if target == source_obj:
        # Source is the target (first mesh in layer) - nothing to merge
        return

    # Basic safety checks
    if not target.data.uv_layers:
        raise Exception(f"Target object '{target.name}' has no UV layers")
    if not source_obj.data.uv_layers:
        raise Exception(f"Source object '{source_obj.name}' has no UV layers")

    # Rename first UV layers to "UVMap" before joining (if not already)
    for obj in [target, source_obj]:
        if obj.data.uv_layers:
            first_uv = obj.data.uv_layers[0]
            if first_uv.name != "UVMap":
                first_uv.name = "UVMap"

    # Join source_obj onto target
    deselect_all()
    selection_add(source_obj)
    selection_add(target)
    bpy.ops.object.join()
    deselect_all()
