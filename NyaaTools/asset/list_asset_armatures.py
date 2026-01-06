import bpy


def list_asset_armatures():
    """List all asset armature names using PropertyGroup system."""
    armatures = []
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE" and obj.nyaa_asset.is_asset:
            if obj.name not in armatures:
                armatures.append(obj.name)
    return armatures
