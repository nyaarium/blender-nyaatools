import bpy


def assert_uv_match(obj1, obj2):
    if (obj1 == None):
        raise BaseException("assertUVMatch() :: Expected an object, got: None")
    if (obj2 == None):
        raise BaseException("assertUVMatch() :: Expected an object, got: None")

    if (len(obj1.data.uv_layers) != len(obj2.data.uv_layers)):
        raise BaseException(
            "Objects have mismatched UV sets: [" + obj1.name + "] [" + obj2.name + "]")


def assert_exists(name):
    obj = bpy.context.scene.objects.get(name)
    obj.hide_set(False)
    obj.select_set(False)
