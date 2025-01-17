import bpy
import traceback

from ..image.renamePackedImage import renamePackedImage


class NyaaToolsRenamePackedImage(bpy.types.Operator):
    """Rename packed images to match their name in Blender"""

    bl_idname = "nyaa.rename_packed_images"
    bl_label = "Rename Packed Images"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            perform()
            return {"FINISHED"}

        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform():
    for image in bpy.data.images:
        renamePackedImage(image)
