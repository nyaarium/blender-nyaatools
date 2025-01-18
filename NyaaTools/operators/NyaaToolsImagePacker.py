import bpy
import traceback


class NyaaToolsImagePacker(bpy.types.Operator):
    """Pack or unpack images used by selected meshes"""

    bl_idname = "nyaa.image_packer"
    bl_label = "Pack/Unpack Images"
    bl_options = {"REGISTER", "UNDO"}

    pack: bpy.props.BoolProperty(
        name="Pack",
        description="Pack images",
        default=True,
    )

    unpack: bpy.props.BoolProperty(
        name="Unpack",
        description="Unpack images",
        default=False,
    )

    def execute(self, context):
        try:
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
                self.report({"WARNING"}, "No images found in selected meshes")
                return {"CANCELLED"}

            if self.pack:
                count = 0
                for image in used_images:
                    if not image.packed_file and image.source == "FILE":
                        image.pack()
                        count += 1
                self.report({"INFO"}, f"✅ Packed {count} images from selected meshes")

            elif self.unpack:
                count = 0
                for image in used_images:
                    if image.packed_file:
                        image.unpack()
                        count += 1
                self.report(
                    {"INFO"}, f"✅ Unpacked {count} images from selected meshes"
                )

            return {"FINISHED"}

        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
