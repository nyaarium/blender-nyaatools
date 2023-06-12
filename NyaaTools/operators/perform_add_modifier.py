import bpy

from ..avatar.get_avatar_armature import get_avatar_armature
from ..common.get_prop import get_prop
from ..consts import PROP_AVATAR_LAYERS


def perform_add_modifier(which_modifier):
    def move_modifier_to_top(modifier):
        for i in range(len(modifier.id_data.modifiers)):
            if modifier == modifier.id_data.modifiers[0]:
                break
            bpy.ops.object.modifier_move_up(modifier=modifier.name)

    def search_for_avatar_armature(mesh):
        key = get_prop(mesh, PROP_AVATAR_LAYERS)
        if (key != None):
            keySplit = key.split(",") if key != "" else []
            for path in keySplit:
                pathParts = path.split("/") if path != "" else []
                targetAvatarName = pathParts[0].strip()
                return get_avatar_armature(targetAvatarName)
        return None

    # Only returns an armature if there is only 1 armature in the scene
    def search_for_only_armature():
        ret = None
        for obj in bpy.data.objects:
            if obj.type == "ARMATURE":
                if ret != None:
                    return None
                ret = obj
        return ret

    meshes = bpy.context.selected_objects

    if len(meshes) == 0:
        raise Exception("Please select at least 1 mesh object!")

    bpy.ops.object.mode_set(mode="OBJECT")

    if which_modifier == "Armature":
        for mesh in meshes:
            if mesh.type != "MESH":
                continue
            name = "Armature"
            mod = mesh.modifiers.get(name)
            if (mod):
                mesh.modifiers.remove(mod)
            mod = mesh.modifiers.new(name, "ARMATURE")
            move_modifier_to_top(mod)
            mod.show_expanded = False
            mod.show_on_cage = True
            mod.show_in_editmode = True
            mod.show_viewport = True
            mod.show_render = True
            mod.use_deform_preserve_volume = True
            mod.object = search_for_avatar_armature(mesh)
            if mod.object == None:
                mod.object = search_for_only_armature()

    elif which_modifier == "DataTransfer":
        for mesh in meshes:
            if mesh.type != "MESH":
                continue
            name = "DataTransfer"
            mod = mesh.modifiers.get(name)
            if (mod):
                mesh.modifiers.remove(mod)
            mod = mesh.modifiers.new(name, "DATA_TRANSFER")
            move_modifier_to_top(mod)
            mod.show_expanded = False
            mod.show_on_cage = True
            mod.show_in_editmode = True
            mod.use_vert_data = True
            mod.data_types_verts = {"VGROUP_WEIGHTS"}
            mod.vert_mapping = "POLYINTERP_NEAREST"

    elif which_modifier == "Decimate":
        for mesh in meshes:
            if mesh.type != "MESH":
                continue
            name = "Final - Decimate"
            mod = mesh.modifiers.get(name)
            if (mod):
                mesh.modifiers.remove(mod)
            mod = mesh.modifiers.new(name, "DECIMATE")
            mod.show_expanded = False
            mod.show_render = False
            mod.decimate_type = "COLLAPSE"
            mod.ratio = 0.75
            mod.delimit = {"NORMAL", "MATERIAL", "SEAM", "SHARP", "UV"}
            mod.use_dissolve_boundaries = True

            name = "Final - Triangulate"
            mod = mesh.modifiers.get(name)
            if (mod):
                mesh.modifiers.remove(mod)
            mod = mesh.modifiers.new(name, "TRIANGULATE")
            mod.show_expanded = False
            mod.show_in_editmode = False
            mod.show_render = False
            mod.min_vertices = 5

    else:
        raise Exception("Unknown modifier: " + which_modifier)
