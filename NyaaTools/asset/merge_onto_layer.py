"""
Layer merging for asset export.
"""

import bpy

from .prepare_mesh import prepare_mesh_for_export
from ..common.deselect_all import deselect_all
from ..common.selection_add import selection_add


def assert_uv_match(obj1, obj2):
    """Assert that two objects have matching UV layer counts."""
    if obj1 is None:
        raise Exception("assert_uv_match() :: Expected an object, got: None")
    if obj2 is None:
        raise Exception("assert_uv_match() :: Expected an object, got: None")

    if len(obj1.data.uv_layers) != len(obj2.data.uv_layers):
        raise Exception(
            f"Objects have mismatched UV sets: [{obj1.name}] [{obj2.name}]"
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

    # Join source_obj onto target
    deselect_all()
    selection_add(source_obj)
    selection_add(target)
    bpy.ops.object.join()
    deselect_all()
