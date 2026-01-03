import bpy
import traceback

from ..image.renamePackedImage import renamePackedImage


class NyaaToolsRenamePackedImage(bpy.types.Operator):
    """Rename packed images to match their name in Blender"""

    bl_idname = "nyaa.rename_packed_images"
    bl_label = "Rename Packed"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            message_unchanged = ""
            message_renamed = ""
            message_notpacked = ""
            message_not_dtp_formatted = ""
            message_error = ""

            result = perform(context)

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

            if 0 < len(result["not_dtp_formatted"]):
                message_not_dtp_formatted += (
                    f"❌ {len(result['not_dtp_formatted'])} images not DTP formatted:\n"
                )
                message_not_dtp_formatted += (
                    "\n".join(result["not_dtp_formatted"]) + "\n\n"
                )

            if 0 < len(result["error"]):
                message_error += f"❌ {len(result['error'])} images could not be renamed. Double check:\n"
                message_error += "\n".join(result["error"])

            message = (
                message_renamed
                + message_unchanged
                + message_notpacked
                + message_not_dtp_formatted
                + message_error
            )

            self.report({"ERROR"}, message)
            return {"FINISHED"}

        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


def perform(context):
    # Get all images used by selected meshes
    used_images = set()
    for obj in context.selected_objects:
        if obj.type != "MESH":
            continue

        for mat_slot in obj.material_slots:
            if not mat_slot.material:
                continue

            # Look through all node trees
            for node in mat_slot.material.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    used_images.add(node.image)

    if len(used_images) == 0:
        return {
            "unchanged": [],
            "renamed": [],
            "notpacked": [],
            "not_dtp_formatted": [],
            "error": ["No images found in selected meshes"],
        }

    results_unchanged = []
    results_renamed = []
    results_notpacked = []
    results_not_dtp_formatted = []
    results_error = []

    wm = bpy.context.window_manager
    wm.progress_begin(0, len(used_images))

    for i, image in enumerate(used_images):
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
            case "not_dtp_formatted":
                results_not_dtp_formatted.append(result["name"])
            case "error":
                results_error.append(result["name"])

    wm.progress_end()

    return {
        "unchanged": results_unchanged,
        "renamed": results_renamed,
        "notpacked": results_notpacked,
        "not_dtp_formatted": results_not_dtp_formatted,
        "error": results_error,
    }
