import bpy

from ..avatar.apply_avatar_modifiers import apply_avatar_modifiers


# process UVs, and apply modifiers
def apply_avatar_mesh(obj, armature=None):
    apply_avatar_modifiers(obj)

    # Remove UV maps beginning with "--"
    for uv in obj.data.uv_layers:
        if uv.name.startswith("--"):
            obj.data.uv_layers.remove(uv)

    if armature != None:
        obj.modifiers.new(name="Armature", type="ARMATURE")
        obj.modifiers["Armature"].object = armature
        obj.parent = armature
    else:
        obj.parent = None
