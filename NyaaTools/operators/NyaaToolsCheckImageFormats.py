import bpy
import traceback

from ..image.dtp_format import is_filename_dtp_formatted


class NYAATOOLS_OT_CheckImageFormats(bpy.types.Operator):
    """Check if images in selected meshes follow Nyaarium's DTP naming convention"""

    bl_idname = "nyaa.check_image_formats"
    bl_label = "Check Names"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            result = perform(context)

            message = ""

            if 0 < len(result["valid"]):
                message += f"✅ {len(result['valid'])} valid images\n\n"

            if 0 < len(result["mismatched"]):
                message += f"⚠️ {len(result['mismatched'])} need renaming:\n"
                message += "\n".join(result["mismatched"]) + "\n\n"

            if 0 < len(result["not_dtp_formatted"]):
                message += f"❌ {len(result['not_dtp_formatted'])} not DTP formatted:\n"
                message += "\n".join(result["not_dtp_formatted"]) + "\n\n"

            if 0 < len(result["error"]):
                message += f"❌ {len(result['error'])} errors:\n"
                message += "\n".join(result["error"])

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
            "valid": [],
            "mismatched": [],
            "not_dtp_formatted": [],
            "error": ["No images found in selected meshes"],
        }

    results_valid = []
    results_mismatched = []
    results_not_dtp_formatted = []

    wm = bpy.context.window_manager
    wm.progress_begin(0, len(used_images))

    for i, image in enumerate(used_images):
        wm.progress_update(i)

        if image.name == "Render Result":
            continue

        if not is_filename_dtp_formatted(image.name):
            results_not_dtp_formatted.append(image.name)
            continue

        # Check if image name matches packed file path
        if image.source == "FILE" and image.packed_file:
            # Strip paths
            orig_name = image.filepath.replace("\\", "/").split("/")[-1]
            final_name = image.name.replace("\\", "/").split("/")[-1]

            if orig_name != final_name:
                results_mismatched.append(f"{orig_name} → {final_name}")
            else:
                results_valid.append(image.name)
        else:
            results_valid.append(image.name)

    wm.progress_end()

    return {
        "valid": results_valid,
        "mismatched": results_mismatched,
        "not_dtp_formatted": results_not_dtp_formatted,
        "error": [],
    }
