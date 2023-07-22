import bpy

from ..avatar.asserts import assert_uv_match
from ..common.deselect_all import deselect_all
from ..common.selection_add import selection_add
from ..mesh.apply_modifiers import apply_modifiers


def merge_onto_avatar_layer(targetName, sourceName, armature=None):
    def clone_to_export(obj):
        if obj == None:
            raise BaseException("cloneToExport() :: Expected a mesh object, got: None")

        copied = obj.copy()
        if obj.type == "MESH":
            copied.data = copied.data.copy()
        bpy.data.collections["__Export Temp__"].objects.link(copied)
        return copied

    source = bpy.context.scene.objects.get(sourceName)

    # Create target if it doesn't exist
    target = bpy.context.scene.objects.get(targetName)
    if target != None:
        # Clone source to be merged onto the target
        source = clone_to_export(source)
        apply_modifiers(source)

        # print("    [ merge layer ] Copied  " + source.name + "  to merge on  " + targetName)

        # Ensure UV Maps match
        assert_uv_match(target, source)

        # Merge source onto target
        deselect_all()
        selection_add(source)
        selection_add(target)

        # Join
        bpy.ops.object.join()
    else:
        # Clone source to be renamed as the new target
        source = clone_to_export(source)
        source.name = targetName
        source.data.name = targetName
        apply_modifiers(source)

        # print("    [ new layer ] Copied  " + source.name + "  as  " + targetName)

        if armature != None:
            source.modifiers.new(name="Armature", type="ARMATURE")
            source.modifiers["Armature"].object = armature
            source.parent = armature
        else:
            source.parent = None
