import bpy


def find_meshes_affected_by_armature_modifier(armature):
    ret = []
    for obj in bpy.data.objects:
        # Must be a mesh
        if obj.type != "MESH":
            continue

        mesh = obj

        # Must be using this armature in the "Armature" modifier
        # KNOWN ISSUE: If the mesh uses this armature in 2 armature modifiers, something not good will happen
        using_armature = False
        which_modifier = None
        for mod in mesh.modifiers:
            if mod.type == "ARMATURE":
                if mod.object == armature:
                    using_armature = True
                    which_modifier = mod
                    break
        if not using_armature:
            continue

        # Add to affected_meshes pair: [ mesh, modifier ]
        ret.append([mesh, which_modifier])

    return ret
