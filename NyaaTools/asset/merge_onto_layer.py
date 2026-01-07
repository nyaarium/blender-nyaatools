"""
Layer merging for asset export.
"""

import bpy

from .prepare_mesh import prepare_mesh_for_export
from ..common.deselect_all import deselect_all
from ..common.selection_add import selection_add


def assert_uv_match(obj1, obj2):
    """
    Assert that two objects have compatible UV layers for merging.
    
    Only checks that:
    - Both objects have at least one UV layer
    - The first UV layer names match (we'll rename to UVMap anyway)
    - Neither object has a UVMap in a non-first slot (error if found)
    """
    if obj1 is None:
        raise Exception("assert_uv_match() :: Expected an object, got: None")
    if obj2 is None:
        raise Exception("assert_uv_match() :: Expected an object, got: None")

    # Check that both have at least one UV layer
    if not obj1.data.uv_layers:
        raise Exception(f"Object '{obj1.name}' has no UV layers")
    if not obj2.data.uv_layers:
        raise Exception(f"Object '{obj2.name}' has no UV layers")

    # Check for UVMap conflicts (UVMap must be in first slot)
    for obj in [obj1, obj2]:
        for idx, uv_layer in enumerate(obj.data.uv_layers):
            if uv_layer.name == "UVMap" and idx != 0:
                raise Exception(
                    f"Object '{obj.name}' has a UVMap in slot {idx + 1}, but it must be in slot 1. "
                    f"Please rename or reorder UV layers so the first UV layer is named 'UVMap'."
                )

    # Check that first UV layer names match
    first_uv1 = obj1.data.uv_layers[0].name
    first_uv2 = obj2.data.uv_layers[0].name
    if first_uv1 != first_uv2:
        raise Exception(
            f"Objects have mismatched first UV layer names: [{obj1.name}] has '{first_uv1}', "
            f"[{obj2.name}] has '{first_uv2}'. First UV layers must match."
        )


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

    # Ensure UV Maps match
    assert_uv_match(target, source_obj)

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
