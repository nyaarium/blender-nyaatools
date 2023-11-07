import bpy

from ..common.deselect_all import deselect_all
from ..common.selection_add import selection_add


def apply_modifiers(obj):
    if obj == None:
        raise BaseException("applyModifiers() :: Expected a mesh object, got: None")

    selection_add(obj)

    for modifier in obj.modifiers:
        if (
            modifier.name == "Armature"
            or modifier.name.startswith("MToon")
            or modifier.name.startswith("--")
        ):
            bpy.ops.object.modifier_remove(modifier=modifier.name)
        else:
            bpy.ops.object.modifier_apply(modifier=modifier.name)

    try:
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    except:
        None

    deselect_all()
