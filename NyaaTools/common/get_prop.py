def get_prop(obj, key):
    if obj == None:
        return None

    if (key in obj.keys()):
        return obj[key]
    return None
