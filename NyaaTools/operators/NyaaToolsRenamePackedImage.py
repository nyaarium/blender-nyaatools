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
            message_unchanged = ""
            message_renamed = ""
            message_notpacked = ""
            message_notnyaatoon = ""
            message_error = ""

            result = perform()

            if 0 < len(result["renamed"]):
                message_renamed += (
                    f"✅ {len(result['renamed'])} renamed and repacked:\n"
                )
                message_renamed += "\n".join(result["renamed"]) + "\n\n"

            if 0 < len(result["unchanged"]):
                message_unchanged += (
                    f"🆗 {len(result['unchanged'])} unchanged images:\n"
                )
                message_unchanged += "\n".join(result["unchanged"]) + "\n\n"

            if 0 < len(result["notpacked"]):
                message_notpacked += (
                    f"❌ {len(result['notpacked'])} images not packed:\n"
                )
                message_notpacked += "\n".join(result["notpacked"]) + "\n\n"

            if 0 < len(result["notnyaatoon"]):
                message_notnyaatoon += (
                    f"❌ {len(result['notnyaatoon'])} images not nyaatoon formatted:\n"
                )
                message_notnyaatoon += "\n".join(result["notnyaatoon"]) + "\n\n"

            if 0 < len(result["error"]):
                message_error += f"❌ {len(result['error'])} images could not be renamed. Double check:\n"
                message_error += "\n".join(result["error"])

            message = (
                message_renamed
                + message_unchanged
                + message_notpacked
                + message_notnyaatoon
                + message_error
            )

            self.report({"ERROR"}, message)
            return {"FINISHED"}

        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform():
    results_unchanged = []
    results_renamed = []
    results_notpacked = []
    results_notnyaatoon = []
    results_error = []

    wm = bpy.context.window_manager
    wm.progress_begin(0, len(bpy.data.images))

    for i, image in enumerate(bpy.data.images):
        wm.progress_update(i)

        if image.name == "Render Result":
            continue

        result = renamePackedImage(image)

        match result["result"]:
            case "unchanged":
                results_unchanged.append(result["name"])
            case "renamed":
                results_renamed.append(result["name"])
            case "notpacked":
                results_notpacked.append(result["name"])
            case "notnyaatoon":
                results_notnyaatoon.append(result["name"])
            case "error":
                results_error.append(result["name"])

    wm.progress_end()

    return {
        "unchanged": results_unchanged,
        "renamed": results_renamed,
        "notpacked": results_notpacked,
        "notnyaatoon": results_notnyaatoon,
        "error": results_error,
    }
