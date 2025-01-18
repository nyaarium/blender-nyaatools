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
            self.report({"ERROR"}, result)
            return {"FINISHED"}

        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform():
    bad_names = []

    for image in bpy.data.images:
        if image.name == "Render Result":
            continue

        if not is_filename_nyaatoon_formatted(image.name):
            bad_names.append(image.name)

    if bad_names:
        return "🔍 Images that will skip repacking:\n" + "\n".join(bad_names)

    return "✅ All images follow nyaatoon naming convention."
