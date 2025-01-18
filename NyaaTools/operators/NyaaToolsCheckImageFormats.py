import bpy
import traceback

from ..image.nyaatoon import is_filename_nyaatoon_formatted


class NyaaToolsCheckImageFormats(bpy.types.Operator):
    """Check if images in selected meshes follow the Nyaatoon naming convention"""

    bl_idname = "nyaa.check_image_formats"
    bl_label = "Check Names"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            result = perform(context)
            self.report({"ERROR"}, result)
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
        return "❌ No images found in selected meshes"

    bad_names = []

    for image in used_images:
        if image.name == "Render Result":
            continue

        if not is_filename_nyaatoon_formatted(image.name):
            bad_names.append(image.name)

    if bad_names:
        return "🔍 Images in selected meshes that will skip repacking:\n" + "\n".join(
            bad_names
        )

    return "✅ All images in selected meshes follow Nyaatoon naming convention."
