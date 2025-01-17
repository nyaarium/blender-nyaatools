import bpy
import os

from .nyaatoon import is_filename_nyaatoon_formatted, is_filename_color_encoded


def renamePackedImage(image: bpy.types.Image):
    if image.source == "FILE" and image.packed_file:
        # Extract the original filename from the image's filepath
        original_filename = os.path.basename(image.filepath)
        temp_path = bpy.path.abspath(f"//{original_filename}")

        # Construct the new filepath using the image's name
        new_name = image.name
        new_path = bpy.path.abspath(f"//{new_name}")

        # Skip if the paths are already the same
        if temp_path == new_path:
            return {"ok": "Image already in nyaatoon name format."}

        supported = is_filename_nyaatoon_formatted(image.name)
        if not supported:
            return {"error": "Image not in nyaatoon name format: " + image.name}

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

        return {"ok": "Renamed and repacked: " + image.name}

    elif image.source == "GENERATED":
        supported = is_filename_nyaatoon_formatted(image.name)
        if not supported:
            return {"error": "Image not in nyaatoon name format: " + image.name}

        # Get extension
        ext = image.name.split(".")[-1].lower()

        requires_color = is_filename_color_encoded(image.name)

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
            return {"error": "Unsupported format: " + ext}

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

        return {"ok": "Saved generated image and repacked: " + image.name}

    return {"ok": "Image is not packed."}
