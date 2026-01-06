import traceback
import bpy
from bpy.props import PointerProperty
from ..armature.merge_armatures import merge_armatures

is_armature = lambda self, object: object.type == "ARMATURE"


class NyaaToolsMergeArmatures(bpy.types.Operator):
    """
    Merge bones from another armature into the active armature
    """

    bl_idname = "nyaa.merge_armatures"
    bl_label = "Merge Armatures"
    bl_description = "Merges 2 armatures. The base armature will be either the configured Asset, or the selection active one."
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            perform_merge_armatures()

            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_merge_armatures():
    target_armature, extra_armature = resolve_target_and_extra_armatures()

    if not target_armature:
        raise Exception("Please select a target armature")

    if not extra_armature:
        raise Exception("Please select an extra armature")

    merge_armatures(
        target_armature,
        extra_armature,
        {
            # TODO: Supply a way to configure orphan adoption
            #       'Hair Root': 'Head',
            #       'Ribbon': 'Chest'
        },
    )


def resolve_target_and_extra_armatures():
    target_armature = None
    extra_armature = None

    # Check 1st and 2nd slot of selected objects using PropertyGroup
    obj1 = bpy.context.selected_objects[0]
    obj2 = bpy.context.selected_objects[1]
    is_1st_asset = obj1.type == "ARMATURE" and obj1.nyaa_asset.is_asset
    is_2nd_asset = obj2.type == "ARMATURE" and obj2.nyaa_asset.is_asset

    # If one is an Asset, use that as the target
    if is_1st_asset and not is_2nd_asset:
        target_armature = bpy.context.selected_objects[0]
        extra_armature = bpy.context.selected_objects[1]
    elif not is_1st_asset and is_2nd_asset:
        target_armature = bpy.context.selected_objects[1]
        extra_armature = bpy.context.selected_objects[0]
    else:
        # Active object is the target armature
        target_armature = bpy.context.active_object
        if target_armature == bpy.context.selected_objects[0]:
            extra_armature = bpy.context.selected_objects[1]
        elif target_armature == bpy.context.selected_objects[1]:
            extra_armature = bpy.context.selected_objects[0]
        else:
            raise Exception(
                "Please active select one of the armatures to be the base (ctrl + click)"
            )

    return target_armature, extra_armature
