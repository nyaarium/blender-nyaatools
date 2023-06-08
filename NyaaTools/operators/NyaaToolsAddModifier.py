import traceback
import bpy
from bpy.props import StringProperty

from .perform_add_modifier import perform_add_modifier


class NyaaToolsAddModifier(bpy.types.Operator):
    """Adds a modifier to the selected objects"""
    bl_idname = "nyaa.add_modifier"
    bl_label = "Add Modifier"
    bl_options = {"REGISTER", "UNDO"}

    # Armature
    # DataTransfer
    # Decimate
    which: StringProperty(name="Which Modifier", default="")

    def execute(self, context):
        try:
            perform_add_modifier(self.which)
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
