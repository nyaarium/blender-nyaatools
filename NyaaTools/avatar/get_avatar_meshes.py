import bpy

from ..consts import PROP_AVATAR_LAYERS
from ..common.get_prop import get_prop


def get_avatar_meshes(avatar):
    meshes = []
    for obj in bpy.data.objects:
        if (obj.type == "MESH"):
            key = get_prop(obj, PROP_AVATAR_LAYERS)
            if (key != None):
                keySplit = key.split(",")
                for path in keySplit:
                    pathStart = path.strip()[:len(avatar) + 1]
                    if (pathStart == avatar + "/"):
                        meshes.append(obj.name)
    return meshes
