import bpy

from ..common.get_prop import get_prop
from ..consts import PROP_AVATAR_NAME


def get_avatar_armature(avatar_name):
    for obj in bpy.data.objects:
        if (obj.type == "ARMATURE"):
            key = get_prop(obj, PROP_AVATAR_NAME)
            if (key != None):
                if (key == avatar_name):
                    return obj
    return None
