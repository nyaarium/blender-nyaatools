from ..consts import PROP_AVATAR_EXPORT_PATH, PROP_AVATAR_LAYERS, PROP_AVATAR_NAME


def set_prop(obj, key, value):
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

    if fallback_key != None:
        try:
            obj[fallback_key] = ""
            del obj[fallback_key]
        except:
            pass

    obj[key] = value
