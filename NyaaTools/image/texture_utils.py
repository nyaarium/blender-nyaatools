"""Channel packing utilities for combining texture maps into multi-channel images."""

import bpy
import numpy as np
import os
from typing import Optional, Tuple


def pack_rgba(
    rgb_image: Optional[bpy.types.Image],
    alpha_image: Optional[bpy.types.Image],
    default_rgb: Tuple[float, float, float] = (1.0, 1.0, 1.0),
    default_alpha: float = 1.0
) -> bpy.types.Image:
    """
    Pack RGB and Alpha channels into a single RGBA image.
    
    Args:
        rgb_image: Image containing RGB data (uses RGB channels)
        alpha_image: Image containing Alpha data (uses R channel as alpha)
        default_rgb: Default RGB color if no image provided
        default_alpha: Default alpha value if no image provided
    
    Returns:
        New RGBA image with packed channels
    """
    # Determine resolution (use RGB if available, otherwise alpha, otherwise default)
    if rgb_image:
        width, height = rgb_image.size[0], rgb_image.size[1]
    elif alpha_image:
        width, height = alpha_image.size[0], alpha_image.size[1]
    else:
        width, height = 8, 8
    
    # Create output image
    output = bpy.data.images.new(
        name="packed_rgba",
        width=width,
        height=height,
        alpha=True
    )
    
    # Create output array (H, W, 4)
    out_array = np.empty((height, width, 4), dtype=np.float32)
    
    # Determine if we should use batching for large images
    use_batching = _should_use_batching(width, height)
    
    # Extract RGB data
    if rgb_image:
        if (rgb_image.size[0], rgb_image.size[1]) != (width, height):
            # Need to resize - use NumPy version
            rgb_array = _image_to_np(rgb_image)
            rgb_array = _resize_np_nearest(rgb_array, width, height, use_batching)
        else:
            rgb_array = _image_to_np(rgb_image)
        
        # Copy RGB channels (first 3 channels)
        out_array[:, :, :3] = rgb_array[:, :, :3]
    else:
        # Use default RGB - broadcast to all pixels
        out_array[:, :, :3] = np.array(default_rgb, dtype=np.float32)
    
    # Extract Alpha data
    if alpha_image:
        if (alpha_image.size[0], alpha_image.size[1]) != (width, height):
            # Need to resize - use NumPy version
            alpha_array = _image_to_np(alpha_image)
            alpha_array = _resize_np_nearest(alpha_array, width, height, use_batching)
        else:
            alpha_array = _image_to_np(alpha_image)
        
        # Use R channel as alpha
        out_array[:, :, 3] = alpha_array[:, :, 0]
    else:
        # Use default alpha - broadcast to all pixels
        out_array[:, :, 3] = default_alpha
    
    # Write to output image
    _np_to_image_pixels(output, out_array)
    
    return output


def pack_pbr(
    metallic_image: Optional[bpy.types.Image],
    specular_image: Optional[bpy.types.Image],
    roughness_image: Optional[bpy.types.Image],
    default_metallic: float = 0.0,
    default_specular: float = 0.5,
    default_roughness: float = 0.5
) -> bpy.types.Image:
    """
    Pack Metallic (R), Specular (G), and Roughness (B) into a single RGB image.
    
    Args:
        metallic_image: Image containing metallic data (uses R channel)
        specular_image: Image containing specular data (uses R channel)
        roughness_image: Image containing roughness data (uses R channel)
        default_metallic: Default metallic value (0.0-1.0)
        default_specular: Default specular value (0.0-1.0)
        default_roughness: Default roughness value (0.0-1.0)
    
    Returns:
        New RGB image with packed PBR channels
    """
    # Determine resolution - use largest available texture
    images = [img for img in [metallic_image, specular_image, roughness_image] if img]
    
    if images:
        # Find largest resolution
        max_area = 0
        width, height = 8, 8
        for img in images:
            area = img.size[0] * img.size[1]
            if area > max_area:
                max_area = area
                width, height = img.size[0], img.size[1]
    else:
        # All channels are defaults - use minimal size
        width, height = 8, 8
    
    # Create output image
    output = bpy.data.images.new(
        name="packed_pbr",
        width=width,
        height=height,
        alpha=False
    )
    
    # Create output array (H, W, 4)
    out_array = np.empty((height, width, 4), dtype=np.float32)
    
    # Determine if we should use batching for large images
    use_batching = _should_use_batching(width, height)
    
    # Pack Metallic (R channel)
    if metallic_image:
        if (metallic_image.size[0], metallic_image.size[1]) != (width, height):
            metallic_array = _image_to_np(metallic_image)
            metallic_array = _resize_np_nearest(metallic_array, width, height, use_batching)
        else:
            metallic_array = _image_to_np(metallic_image)
        
        # Use R channel as metallic
        out_array[:, :, 0] = metallic_array[:, :, 0]
    else:
        # Use default metallic - broadcast to all pixels
        out_array[:, :, 0] = default_metallic
    
    # Pack Specular (G channel)
    if specular_image:
        if (specular_image.size[0], specular_image.size[1]) != (width, height):
            specular_array = _image_to_np(specular_image)
            specular_array = _resize_np_nearest(specular_array, width, height, use_batching)
        else:
            specular_array = _image_to_np(specular_image)
        
        # Use R channel as specular
        out_array[:, :, 1] = specular_array[:, :, 0]
    else:
        # Use default specular - broadcast to all pixels
        out_array[:, :, 1] = default_specular
    
    # Pack Roughness (B channel)
    if roughness_image:
        if (roughness_image.size[0], roughness_image.size[1]) != (width, height):
            roughness_array = _image_to_np(roughness_image)
            roughness_array = _resize_np_nearest(roughness_array, width, height, use_batching)
        else:
            roughness_array = _image_to_np(roughness_image)
        
        # Use R channel as roughness
        out_array[:, :, 2] = roughness_array[:, :, 0]
    else:
        # Use default roughness - broadcast to all pixels
        out_array[:, :, 2] = default_roughness
    
    # Alpha channel (unused but needed for pixel buffer)
    out_array[:, :, 3] = 1.0
    
    # Write to output image
    _np_to_image_pixels(output, out_array)
    
    return output


def save_image_as_png(image: bpy.types.Image, output_path: str) -> bool:
    """
    Save a Blender image to PNG file and clean up from memory.
    
    Args:
        image: The Blender image to save
        output_path: Path to save the PNG file
    
    Returns:
        True if successful, False otherwise
    """
    if not image:
        return False
    
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Save the image
        image.filepath_raw = output_path
        image.file_format = 'PNG'
        image.save()
        
        # Clean up the image from Blender's memory
        bpy.data.images.remove(image)
        
        return True
    except Exception as e:
        print(f"Failed to save image to {output_path}: {e}")
        if image and image.name in bpy.data.images:
            bpy.data.images.remove(image)
        return False


def _image_to_np(img: bpy.types.Image) -> np.ndarray:
    """
    Convert Blender image to NumPy array (H, W, 4).
    
    Args:
        img: Blender image to convert
    
    Returns:
        NumPy array with shape (height, width, 4) containing RGBA data
    """
    w, h = img.size
    arr = np.asarray(img.pixels, dtype=np.float32)
    c = 4  # Blender stores 4 channels even if alpha is off
    return arr.reshape(h, w, c)


def _np_to_image_pixels(img: bpy.types.Image, arr: np.ndarray) -> None:
    """
    Write NumPy array to Blender image pixels.
    
    Args:
        img: Blender image to write to
        arr: NumPy array with shape (H, W, 4) containing RGBA data
    """
    img.pixels[:] = arr.reshape(-1)
    img.update()


def _should_use_batching(width: int, height: int, threshold: int = 8192) -> bool:
    """
    Determine if batching should be used for large images.
    
    Args:
        width: Image width
        height: Image height
        threshold: Size threshold above which to use batching
    
    Returns:
        True if batching should be used
    """
    return width > threshold or height > threshold

# Dev Note:
# - We are mostly upscaling solid colors (8x8 -> 4K)
# - Speed is critical
# 
# Discuss if we should use bilinear or something else
def _resize_np_nearest(src: np.ndarray, tw: int, th: int, use_batching: bool = False, batch_size: int = 4096) -> np.ndarray:
    """
    Resize NumPy array using nearest-neighbor sampling.
    
    Args:
        src: Source array with shape (H, W, C)
        tw: Target width
        th: Target height
        use_batching: If True, process in chunks for very large images
        batch_size: Number of rows to process at once when batching
    
    Returns:
        Resized array with shape (th, tw, C)
    """
    sh, sw = src.shape[:2]
    x_idx = (np.linspace(0, sw - 1, tw)).astype(np.int32)
    y_idx = (np.linspace(0, sh - 1, th)).astype(np.int32)
    
    # For very large images, process in chunks to reduce memory usage
    if use_batching and th > batch_size:
        result = np.empty((th, tw, src.shape[2]), dtype=src.dtype)
        
        for start_row in range(0, th, batch_size):
            end_row = min(start_row + batch_size, th)
            batch_y_idx = y_idx[start_row:end_row]
            result[start_row:end_row] = src[batch_y_idx][:, x_idx]
        
        return result
    else:
        return src[y_idx][:, x_idx]
