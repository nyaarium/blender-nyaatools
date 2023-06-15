from .get_avatar_layers import get_avatar_layers
from ..common.set_prop import set_prop
from ..consts import PROP_AVATAR_LAYERS


def add_to_avatar_layer(avatar_name, layer_name, mesh):
    if (avatar_name.find("/") != -1 or avatar_name.find(",") != -1):
        raise BaseException("Avatar name cannot contain '/' or ','")
    if (layer_name.find("/") != -1 or layer_name.find(",") != -1):
        raise BaseException("Layer name cannot contain '/' or ','")

    layers = get_avatar_layers(mesh)

    for i in range(len(layers)):
        if (layers[i][0] == avatar_name):
            layers.pop(i)
            break

    layers.append([avatar_name, layer_name])

    # Map and join pairs with /
    layers = ["/".join(pair) for pair in layers]

    # Join strings with ,
    layers = ",".join(layers)

    set_prop(mesh, PROP_AVATAR_LAYERS, layers)
