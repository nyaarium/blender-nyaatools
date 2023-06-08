from ..common.get_prop import get_prop
from ..consts import PROP_AVATAR_LAYERS


def get_avatar_layers(mesh):
    ret = []
    layers = get_prop(mesh, PROP_AVATAR_LAYERS)
    if (layers != None):
        split = layers.split(",")
        for path in split:
            path_parts = path.split("/")
            path_avatar_name = path_parts[0]
            path_layer_name = path_parts[1]
            ret.push([path_avatar_name, path_layer_name])
    return ret
