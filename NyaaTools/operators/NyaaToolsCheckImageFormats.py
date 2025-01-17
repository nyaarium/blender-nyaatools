import bpy
import traceback

from ..image.nyaatoon import is_filename_nyaatoon_formatted


class NyaaToolsCheckImageFormats(bpy.types.Operator):
    """Check if all images follow the nyaatoon naming convention"""

    bl_idname = "nyaa.check_image_formats"
    bl_label = "Check Image Formats"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            result = perform()
            if "ok" in result:
                self.report({"INFO"}, result["ok"])
                return {"FINISHED"}
            else:
                self.report({"ERROR"}, result["error"])
                return {"CANCELLED"}

        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform():
    results_error = []

    for image in bpy.data.images:
        if not is_filename_nyaatoon_formatted(image.name):
            results_error.append(f"Invalid format: {image.name}")

    if results_error:
        return {"error": "\n".join(results_error)}

    return {"ok": "All images follow nyaatoon naming convention."}
