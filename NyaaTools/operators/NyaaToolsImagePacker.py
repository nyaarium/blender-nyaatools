import bpy
import traceback


class NYAATOOLS_OT_ImagePacker(bpy.types.Operator):
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
                self.report({"ERROR"}, "❌ No images found in selected meshes")
                return {"CANCELLED"}

            if self.pack:
                packed_files = []
                for image in used_images:
                    if not image.packed_file and image.source == "FILE":
                        image.pack()
                        packed_files.append(image.name)

                if packed_files:
                    message = f"✅ Packed {len(packed_files)} images:\n"
                    message += "\n".join(packed_files)
                else:
                    message = "🆗 All images already packed"
                self.report({"ERROR"}, message)

            elif self.unpack:
                unpacked_files = []
                for image in used_images:
                    if image.packed_file:
                        image.unpack()
                        unpacked_files.append(image.name)

                if unpacked_files:
                    message = f"✅ Unpacked {len(unpacked_files)} images:\n"
                    message += "\n".join(unpacked_files)
                else:
                    message = "🆗 All images already unpacked"
                self.report({"ERROR"}, message)

            return {"FINISHED"}

        except Exception as error:
            print(traceback.format_exc())
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
