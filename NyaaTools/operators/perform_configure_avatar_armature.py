import bpy

from ..common.set_prop import set_prop
from ..consts import PROP_AVATAR_EXPORT_PATH, PROP_AVATAR_NAME


def perform_configure_avatar_armature(avatar, export_path):
    armature = bpy.context.active_object

    if armature == None:
        raise Exception("Please select an armature object first! Got: None")

    if armature.type != "ARMATURE":
        raise Exception(
            "Please select an armature object first! Got: " + armature.type)

    set_prop(armature, PROP_AVATAR_NAME, avatar)
    set_prop(armature, PROP_AVATAR_EXPORT_PATH, export_path)
