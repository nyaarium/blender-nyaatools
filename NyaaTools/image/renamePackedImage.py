import bpy
import os


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
