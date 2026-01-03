import bpy

from ..avatar.apply_avatar_mesh import apply_avatar_mesh
from ..avatar.asserts import assert_uv_match
from ..common.deselect_all import deselect_all
from ..common.selection_add import selection_add


def merge_onto_avatar_layer(layer_name, source_obj, armature=None):
    """
    Merge a mesh onto a layer target.

    Args:
        layer_name: Name of the layer (target object should have this name)
        source_obj: Mesh to merge onto the layer
        armature: Optional armature to parent to
    """
    apply_avatar_mesh(source_obj, armature)

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
