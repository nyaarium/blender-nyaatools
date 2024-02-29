import bpy


def renamer_restore(unrename_info):
    for info in unrename_info:
        which = info[0]
        if which == "object":
            obj = bpy.data.objects[info[1]]
            obj.name = info[2]
        else:
            data = bpy.data[info[0]][info[1]]
            data.name = info[2]
