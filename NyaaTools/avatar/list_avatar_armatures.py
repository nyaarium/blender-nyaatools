import bpy


def list_avatar_armatures():
    """List all avatar armature names using PropertyGroup system."""
    armatures = []
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE" and obj.nyaa_avatar.is_avatar:
            if obj.name not in armatures:
                armatures.append(obj.name)
    return armatures
