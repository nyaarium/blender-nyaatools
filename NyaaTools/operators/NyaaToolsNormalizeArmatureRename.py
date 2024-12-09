import traceback
import bpy
from bpy.props import BoolProperty, StringProperty


from ..armature.normalize_armature_rename_bones import normalize_armature_rename_bones
from ..common.selection_get_armature import selection_get_armature


class NyaaToolsNormalizeArmatureRename(bpy.types.Operator):
    """Renames bones in armatures to Nyaa's preferred naming convention"""

    bl_idname = "nyaa.normalize_armature_rename"
    bl_label = "Rename Bones to Nyaa's Convention"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            armature = selection_get_armature()
            perform_normalize_rename(armature)
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform_normalize_rename(armature):
    if armature == None or armature.type != "ARMATURE":
        raise Exception("Expected an armature")

    ######################
    ##  Begin progress  ##

    # Make armature active
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = armature

    # Rename bones
    normalize_armature_rename_bones(armature, False)

    bpy.ops.object.mode_set(mode="OBJECT")


    print("Done!")
