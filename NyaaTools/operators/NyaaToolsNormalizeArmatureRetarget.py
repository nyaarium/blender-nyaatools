import traceback
import bpy
from bpy.props import StringProperty

from ..armature.normalize_armature_retarget import normalize_armature_retarget
from ..common.selection_get_armature import selection_get_armature


class NyaaToolsNormalizeArmatureRetarget(bpy.types.Operator):
    """Retarget the animation on this armature to match source armature. A new dopesheet animation will be created."""

    bl_idname = "nyaa.normalize_armature_retarget"
    bl_label = "Retarget Armature to Nyaa's Convention"
    bl_options = {"REGISTER", "UNDO"}

    new_animation_name: StringProperty(
        name="Animation Name", description="Name for the new retargeted animation"
    )

    def execute(self, context):
        try:
            if self.new_animation_name.strip() == "":
                self.report({"WARNING"}, "Please provide a name for the new animation.")
                return {"FINISHED"}

            perform_normalize_retarget(self.new_animation_name)
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_normalize_retarget(animation_name: str):
    target_armature, extra_armature = resolve_target_and_extra_armatures()

    if not target_armature:
        raise Exception("Please select a target armature")

    if not extra_armature:
        raise Exception("Please select an extra armature")

    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = target_armature

    # Retarget armature
    normalize_armature_retarget(target_armature, extra_armature, animation_name)

    bpy.ops.object.mode_set(mode="OBJECT")

    print("Done!")


def resolve_target_and_extra_armatures():
    target_armature = None
    extra_armature = None

    if len(bpy.context.selected_objects) < 2:
        raise Exception(
            "Please select exactly two armatures, with the main armature active."
        )

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
