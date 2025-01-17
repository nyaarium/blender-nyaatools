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
            result = perform()
            self.report({"INFO"}, result)
            return {"FINISHED"}

        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform():
    results_ok = []
    results_error = []

    wm = bpy.context.window_manager
    wm.progress_begin(0, len(bpy.data.images))

    for i, image in enumerate(bpy.data.images):
        result = renamePackedImage(image)
        wm.progress_update(i)
        if "ok" in result:
            match result["ok"]:
                case "Image already in nyaatoon name format.":
                    pass
                case "Image is not packed.":
                    pass
                case _:
                    results_ok.append(result["ok"])
        else:
            results_error.append(result["error"])

    wm.progress_end()

    count = len(results_ok)
    results_ok = "\n".join(results_ok)
    results_error = "\n".join(results_error)

    print("")
    print("")
    print(results_ok)
    print("")
    print(results_error)
    print("")

    if results_error:
        return (
            f"{count} images renamed and repacked.\n\nSome images could not be renamed.\n"
            + results_error
        )

    return f"{count} images renamed and repacked."
