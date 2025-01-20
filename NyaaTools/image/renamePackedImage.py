import bpy
import os
from pathlib import Path

from ..common.file_stuff import deleteFile

from .nyaatoon import is_filename_nyaatoon_formatted, is_filename_color_encoded


def renamePackedImage(image: bpy.types.Image):
    """Rename a packed image to the nyaatoon name format."""

    if image.source == "FILE" and image.packed_file:
        supported = is_filename_nyaatoon_formatted(image.name)
        if not supported:
            return {"result": "notnyaatoon", "name": image.name}

        # Strip paths
        orig_name = image.filepath.replace("\\", "/").split("/")[-1]
        final_name = image.name.replace("\\", "/").split("/")[-1]

        # Skip if already in correct format
        if orig_name == final_name:
            return {"result": "unchanged", "name": image.name}

        # Save, rename, and repack
        return repackImage(image, image.name)

    elif image.source == "GENERATED":
        supported = is_filename_nyaatoon_formatted(image.name)
        if not supported:
            return {"result": "notnyaatoon", "name": image.name}

        # Save and repack
        return repackImage(image)

    return {"result": "notpacked", "name": image.name}


def repackImage(image: bpy.types.Image, new_name: str = None):
    """Save, reload, and repack an image. Optionally rename to new_name."""

    # Strip paths
    orig_name = image.filepath.replace("\\", "/").split("/")[-1]
    if len(orig_name) == 0:
        orig_name = image.name
    final_name = new_name if new_name else orig_name
    final_name = final_name.replace("\\", "/").split("/")[-1]

    # Set color space based on flags
    requires_color = is_filename_color_encoded(final_name)
    if requires_color:
        image.colorspace_settings.name = "sRGB"
    else:
        image.colorspace_settings.name = "Non-Color"

    # Get extension and configure format settings
    settings = bpy.context.scene.render.image_settings
    ext = final_name.split(".")[-1].lower()

    if ext == "exr":
        settings.file_format = "OPEN_EXR"
        settings.color_mode = "RGBA" if image.alpha_mode != "NONE" else "RGB"
        settings.color_depth = "32" if image.depth >= 32 else "16"
        settings.exr_codec = "ZIP"

    elif ext == "png":
        settings.file_format = "PNG"
        settings.color_mode = "RGBA" if image.alpha_mode != "NONE" else "RGB"
        settings.compression = 100
        # Handle float images properly
        if image.is_float:
            settings.color_depth = "16"
        else:
            settings.color_depth = "16" if image.depth > 8 else "8"

    elif ext in ["jpg", "jpeg"]:
        settings.file_format = "JPEG"
        settings.color_mode = "RGB"
        settings.color_depth = "8"
        settings.quality = 100

    elif ext == "tga":
        settings.file_format = "TARGA"
        settings.color_mode = "RGBA" if image.alpha_mode != "NONE" else "RGB"
        settings.color_depth = "8"

    else:
        print(f"Unsupported format: {ext}")
        return {"result": "error", "name": image.name}

    # Build paths
    path_final_name = Path("./textures") / final_name
    os_final_name_abs = str(path_final_name.resolve())
    bl_final_name = "//textures/" + final_name

    # Delete if target already exists
    deleteFile(os_final_name_abs)

    # Create textures directory if it doesn't exist
    os.makedirs("textures", exist_ok=True)

    # Save the image
    image.save_render(filepath=os_final_name_abs)

    # Update the image's filepath and reload it
    image.source = "FILE"
    image.filepath = bl_final_name
    image.reload()

    # Pack the image
    image.pack()

    # Clean up temporary file
    deleteFile(os_final_name_abs)

    return {"result": "renamed", "name": image.name}
