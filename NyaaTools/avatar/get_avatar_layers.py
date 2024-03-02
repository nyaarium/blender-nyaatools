from ..common.get_prop import get_prop
from ..consts import PROP_AVATAR_LAYERS


# Returns a list of avatar layers as pairs: [path_avatar_name, path_layer_name]
# If avatar_name is given, only returns layers for that avatar (as pairs above)
def get_avatar_layers(mesh, avatar_name = None):
    ret = []
    layers = get_prop(mesh, PROP_AVATAR_LAYERS)
    if (layers != None):
        split = layers.split(",") if layers != "" else []
        for path in split:
            path_parts = path.split("/") if path != "" else []
            path_avatar_name = path_parts[0]
            path_layer_name = path_parts[1]
            if avatar_name == None or avatar_name == path_avatar_name:
                ret.append([path_avatar_name, path_layer_name])
    return ret
