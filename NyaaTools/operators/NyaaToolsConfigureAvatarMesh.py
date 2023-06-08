import traceback
import bpy
from bpy.props import StringProperty

from .perform_configure_avatar_mesh import perform_configure_avatar_mesh


class NyaaToolsConfigureAvatarMesh(bpy.types.Operator):
    """Configure the mesh of an avatar"""
    bl_idname = "nyaa.configure_avatar_mesh"
    bl_label = "Configure Mesh"
    bl_options = {"REGISTER", "UNDO"}

    avatar_layers: StringProperty(name="Avatar Layers", default="")

    def execute(self, context):
        try:
            perform_configure_avatar_mesh(
                avatar_layers=self.avatar_layers,
            )
            return {"FINISHED"}
        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
