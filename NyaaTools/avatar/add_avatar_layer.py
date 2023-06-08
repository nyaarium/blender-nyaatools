from ..avatar.get_avatar_layers import get_avatar_layers
from ..common.set_prop import set_prop
from ..consts import PROP_AVATAR_LAYERS


def add_avatar_layer(mesh, avatar_name, layer_name):
    if (avatar_name.find("/") != -1 or avatar_name.find(",") != -1):
        raise BaseException("Avatar name cannot contain '/' or ','")
    if (layer_name.find("/") != -1 or layer_name.find(",") != -1):
        raise BaseException("Layer name cannot contain '/' or ','")

    layers = get_avatar_layers(mesh)
    layers.push([avatar_name, layer_name])

    # Map and join pairs with /
    layers = ["/".join(pair) for pair in layers]

    # Join strings with ,
    layers = ",".join(layers)

    set_prop(mesh, PROP_AVATAR_LAYERS, layers)
