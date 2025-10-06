import bpy


def renamer_restore(unrename_info):
    def get_obj_data(t, name):
        if t == "mesh":
            return bpy.data.meshes[name]
        elif t == "armature":
            return bpy.data.armatures[name]
        elif t == "material":
            return bpy.data.materials[name]
        else:
            return None
    
    for info in unrename_info:
        which = info[0]
        if which == "object":
            obj = bpy.data.objects[info[1]]
            obj.name = info[2]
        else:
            data = get_obj_data(which, info[1])
            data.name = info[2]
