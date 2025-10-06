"""Channel packing utilities for combining texture maps into multi-channel images."""

import bpy
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
    
    # Get pixel data
    num_pixels = width * height
    pixels = [0.0] * (num_pixels * 4)
    
    # Extract RGB data
    if rgb_image:
        if (rgb_image.size[0], rgb_image.size[1]) != (width, height):
            # Need to resize - create a copy at target resolution
            rgb_image = _resize_image(rgb_image, width, height)
        
        rgb_pixels = list(rgb_image.pixels)
        for i in range(num_pixels):
            pixels[i * 4 + 0] = rgb_pixels[i * 4 + 0]  # R
            pixels[i * 4 + 1] = rgb_pixels[i * 4 + 1]  # G
            pixels[i * 4 + 2] = rgb_pixels[i * 4 + 2]  # B
    else:
        # Use default RGB
        for i in range(num_pixels):
            pixels[i * 4 + 0] = default_rgb[0]
            pixels[i * 4 + 1] = default_rgb[1]
            pixels[i * 4 + 2] = default_rgb[2]
    
    # Extract Alpha data
    if alpha_image:
        if (alpha_image.size[0], alpha_image.size[1]) != (width, height):
            # Need to resize
            alpha_image = _resize_image(alpha_image, width, height)
        
        alpha_pixels = list(alpha_image.pixels)
        for i in range(num_pixels):
            pixels[i * 4 + 3] = alpha_pixels[i * 4 + 0]  # Use R channel as alpha
    else:
        # Use default alpha
        for i in range(num_pixels):
            pixels[i * 4 + 3] = default_alpha
    
    # Apply pixels to output
    output.pixels[:] = pixels
    output.update()
    
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
    
    # Get pixel data
    num_pixels = width * height
    pixels = [0.0] * (num_pixels * 4)
    
    # Pack Metallic (R channel)
    if metallic_image:
        if (metallic_image.size[0], metallic_image.size[1]) != (width, height):
            metallic_image = _resize_image(metallic_image, width, height)
        metallic_pixels = list(metallic_image.pixels)
        for i in range(num_pixels):
            pixels[i * 4 + 0] = metallic_pixels[i * 4 + 0]  # Use R channel
    else:
        for i in range(num_pixels):
            pixels[i * 4 + 0] = default_metallic
    
    # Pack Specular (G channel)
    if specular_image:
        if (specular_image.size[0], specular_image.size[1]) != (width, height):
            specular_image = _resize_image(specular_image, width, height)
        specular_pixels = list(specular_image.pixels)
        for i in range(num_pixels):
            pixels[i * 4 + 1] = specular_pixels[i * 4 + 0]  # Use R channel
    else:
        for i in range(num_pixels):
            pixels[i * 4 + 1] = default_specular
    
    # Pack Roughness (B channel)
    if roughness_image:
        if (roughness_image.size[0], roughness_image.size[1]) != (width, height):
            roughness_image = _resize_image(roughness_image, width, height)
        roughness_pixels = list(roughness_image.pixels)
        for i in range(num_pixels):
            pixels[i * 4 + 2] = roughness_pixels[i * 4 + 0]  # Use R channel
    else:
        for i in range(num_pixels):
            pixels[i * 4 + 2] = default_roughness
    
    # Alpha channel (unused but needed for pixel buffer)
    for i in range(num_pixels):
        pixels[i * 4 + 3] = 1.0
    
    # Apply pixels to output
    output.pixels[:] = pixels
    output.update()
    
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


def _resize_image(source: bpy.types.Image, target_width: int, target_height: int) -> bpy.types.Image:
    """
    Resize an image to target dimensions (creates a copy).
    
    Args:
        source: Source image to resize
        target_width: Target width
        target_height: Target height
    
    Returns:
        New resized image
    """
    # Create new image at target resolution
    resized = bpy.data.images.new(
        name=f"{source.name}_resized",
        width=target_width,
        height=target_height,
        alpha=True
    )
    
    # Simple nearest-neighbor sampling
    source_pixels = list(source.pixels)
    resized_pixels = [0.0] * (target_width * target_height * 4)
    
    src_width, src_height = source.size[0], source.size[1]
    
    for y in range(target_height):
        for x in range(target_width):
            # Map target coordinates to source coordinates
            src_x = int((x / target_width) * src_width)
            src_y = int((y / target_height) * src_height)
            
            # Clamp to valid range
            src_x = max(0, min(src_x, src_width - 1))
            src_y = max(0, min(src_y, src_height - 1))
            
            src_idx = (src_y * src_width + src_x) * 4
            dst_idx = (y * target_width + x) * 4
            
            resized_pixels[dst_idx:dst_idx+4] = source_pixels[src_idx:src_idx+4]
    
    resized.pixels[:] = resized_pixels
    resized.update()
    
    return resized
