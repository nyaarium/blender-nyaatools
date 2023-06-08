import bpy

from ..common.get_prop import get_prop
from ..consts import PROP_AVATAR_NAME


def list_avatar_armatures():
    armatures = []
    for obj in bpy.data.objects:
        if (obj.type == "ARMATURE"):
            key = get_prop(obj, PROP_AVATAR_NAME)
            if (key != None and key not in armatures):
                armatures.append(obj.name)
    return armatures
