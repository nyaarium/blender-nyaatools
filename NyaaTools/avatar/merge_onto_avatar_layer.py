import bpy

from ..avatar.apply_avatar_mesh import apply_avatar_mesh
from ..avatar.asserts import assert_uv_match
from ..common.deselect_all import deselect_all
from ..common.selection_add import selection_add


def merge_onto_avatar_layer(layer_name, source_obj, armature=None):
    apply_avatar_mesh(source_obj, armature)
    
    # Create target if it doesn't exist
    target = bpy.context.scene.objects[layer_name]
    if target:
        # Ensure UV Maps match
        assert_uv_match(target, source_obj)

        # Join source_obj onto target
        deselect_all()
        selection_add(source_obj)
        selection_add(target)
        bpy.ops.object.join()
        deselect_all()
