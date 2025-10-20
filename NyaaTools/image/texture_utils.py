"""Channel packing utilities for combining texture maps into multi-channel images."""

import bpy
import numpy as np
import os
import time
from typing import Optional, Tuple

from .uv.analyze_mip_stats import analyze_mip_stats


# pack_rgba() and pack_pbr() functions removed - replaced by bake_packed_texture() in texture_baker.py


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


def resize_image_to_size(image: bpy.types.Image, target_width: int, target_height: int) -> bpy.types.Image:
    """
    Resize a Blender image to the specified dimensions using nearest-neighbor sampling.
    
    Args:
        image: Source Blender image
        target_width: Target width in pixels
        target_height: Target height in pixels
    
    Returns:
        New resized Blender image
    """
    # Convert to numpy array
    src_array = _image_to_np(image)
    
    # Resize using nearest-neighbor
    resized_array = _resize_np_nearest(src_array, target_width, target_height)
    
    # Create new image
    resized_image = bpy.data.images.new(
        name=f"resized_{image.name}",
        width=target_width,
        height=target_height,
        alpha=image.channels == 4
    )
    
    # Write resized data to new image
    _np_to_image_pixels(resized_image, resized_array)
    
    return resized_image
