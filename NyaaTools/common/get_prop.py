from ..consts import PROP_AVATAR_EXPORT_PATH, PROP_AVATAR_LAYERS, PROP_AVATAR_NAME


def get_prop(obj, key):
    if obj == None:
        raise Exception("Expected an object")

    # v0 -> v1 Migration
    fallback_key = None
    if (key == PROP_AVATAR_NAME):
        fallback_key = "avatar"
    elif (key == PROP_AVATAR_LAYERS):
        fallback_key = "targetAvatars"
    elif (key == PROP_AVATAR_EXPORT_PATH):
        fallback_key = "exportPath"

    if (key in obj.keys()):
        return obj[key]
    elif (fallback_key != None and fallback_key in obj.keys()):
        return obj[fallback_key]

    return None
