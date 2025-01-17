import bpy
import os

from .nyaatoon import is_filename_nyaatoon_formatted, is_filename_color_encoded


def renamePackedImage(image: bpy.types.Image):
    if image.packed_file:
        # Extract the original filename from the image's filepath
        original_filename = os.path.basename(image.filepath)
        temp_path = bpy.path.abspath(f"//{original_filename}")

        # Construct the new filepath using the image's name
        new_name = image.name
        new_path = bpy.path.abspath(f"//{new_name}")

        # Skip if the paths are already the same
        if temp_path == new_path:
            return

        supported = is_filename_nyaatoon_formatted(image.name)
        if not supported:
            print(image.name, "not in nyaatoon name format")
            return

        # Save the image to the original filename
        image.save_render(temp_path)

        # Delete if already exists
        if os.path.exists(new_path):
            os.remove(new_path)

        # Rename old name to new name file
        os.rename(temp_path, new_path)

        # Update the image's filepath and reload it
        image.filepath = new_path
        image.reload()

        # Pack the image
        image.pack()

        # Make relative
        image.filepath = bpy.path.relpath(image.filepath)

        # Clean up
        os.remove(new_path)

    elif image.source == "GENERATED":
        supported = is_filename_nyaatoon_formatted(image.name)
        if not supported:
            print(image.name, "not in nyaatoon name format")
            return

        # Get extension
        ext = image.name.split(".")[-1].lower()
        print(ext)

        requires_color = is_filename_color_encoded(image.name)
        print(requires_color)

        # Set color space based on flags
        if requires_color:
            image.colorspace_settings.name = "sRGB"
        else:
            image.colorspace_settings.name = "Non-Color"

        # Handle different formats
        if ext == "exr":
            bpy.context.scene.render.image_settings.file_format = "OPEN_EXR"
        elif ext == "tga":
            bpy.context.scene.render.image_settings.file_format = "TARGA"
        elif ext == "png":
            bpy.context.scene.render.image_settings.file_format = "PNG"
            bpy.context.scene.render.image_settings.compression = 100
        elif ext in ["jpg", "jpeg"]:
            bpy.context.scene.render.image_settings.file_format = "JPG"
            bpy.context.scene.render.image_settings.quality = 100
        else:
            print(f"Unsupported format: {ext}")
            return

        # Save the image
        image.save_render(bpy.path.abspath(f"//{image.name}"))

        # Replace the Blender image with the new image
        image.filepath = bpy.path.abspath(f"//{image.name}")
        image.source = "FILE"  # Change from GENERATED to FILE
        image.reload()

        # Pack the saved image
        image.pack()

        # Make relative
        image.filepath = bpy.path.relpath(image.filepath)

        # Clean up the temporary file
        os.remove(bpy.path.abspath(f"//{image.name}"))

        print(f"Saved and repacked {image.name}.")
