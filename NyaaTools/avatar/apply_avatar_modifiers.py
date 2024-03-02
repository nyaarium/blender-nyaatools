import bpy

from ..avatar.list_avatar_armatures import list_avatar_armatures
from .._external.przemir.helper import applyModifierForObjectWithShapeKeys
from ..common.deselect_all import deselect_all
from ..common.selection_add import selection_add


def apply_avatar_modifiers(obj):
    if obj == None:
        raise BaseException("applyModifiers() :: Expected a mesh object, got: None")

    selection_add(obj)

    avatar_names = list_avatar_armatures()

    for modifier in obj.modifiers:
        if (
            modifier.name.startswith("--")
        ):
            # Anything with a name starting with "--" is for internal use only and should be removed

            bpy.ops.object.modifier_remove(modifier=modifier.name)
        elif modifier.name.startswith("MToon"):
            # MToon is a special case where the outline modifier should be removed

            bpy.ops.object.modifier_remove(modifier=modifier.name)
        elif modifier.type == "ARMATURE":
            # Remove armature modifiers that target any avatars. These are purely for blender viewing and will be reconfigured by the tool
            # Otherwise apply it

            if modifier.object == None:
                bpy.ops.object.modifier_remove(modifier=modifier.name)
                continue

            armature = modifier.object

            if armature.name in avatar_names:
                bpy.ops.object.modifier_remove(modifier=modifier.name)
            else:
                applyModifierForObjectWithShapeKeys(
                    bpy.context,
                    [modifier.name],
                    False
                )
        else:
            applyModifierForObjectWithShapeKeys(
                bpy.context,
                [modifier.name],
                False
            )

    try:
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    except:
        None

    deselect_all()
