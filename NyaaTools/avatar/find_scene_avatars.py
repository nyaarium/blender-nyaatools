import bpy

from ..common.get_prop import get_prop
from ..consts import PROP_AVATAR_LAYERS
from .get_avatar_layers import get_avatar_layers


def find_scene_avatars(filter_to_avatar_name = None):
    result = {}

    for obj in bpy.context.scene.objects:
        obj_layers = get_avatar_layers(obj)

        for avatar_name, layer_name in obj_layers:
            if avatar_name not in result:
                result[avatar_name] = {}

            if layer_name not in result[avatar_name]:
                result[avatar_name][layer_name] = {}

            result[avatar_name][layer_name][obj.name] = obj

    if filter_to_avatar_name:
        if filter_to_avatar_name in result:
            return result[filter_to_avatar_name]
        else:
            return None
    else:
        return result
