from .get_avatar_layers import get_avatar_layers
from ..common.set_prop import set_prop
from ..consts import PROP_AVATAR_LAYERS


def remove_from_avatar_layers(avatar_name, mesh):
    layers = get_avatar_layers(mesh)
    layers = [layer for layer in layers if layer[0] != avatar_name]

    # Map and join pairs with /
    layers = ["/".join(pair) for pair in layers]

    # Join strings with ,
    layers = ",".join(layers)

    set_prop(mesh, PROP_AVATAR_LAYERS, layers)
