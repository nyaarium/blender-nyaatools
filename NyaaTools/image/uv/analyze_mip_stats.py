"""
Iterative mipmap analysis using numpy arrays.

This module provides the main entry point for analyzing mipmap safety
and color uniformity using an iterative, numpy-based approach.
"""

import numpy as np
import time

from .build_coverage_pyramid import build_coverage_pyramid


# Max color difference for entire texture to be considered uniform
UNIFORMITY_THRESHOLD = 0.005 # (~1.3 color levels in 0-255)

# Max detail loss allowed for 2x2 blocks when downsampling to 1 block
DEGRADATION_THRESHOLD = 0.005 # (~1.3 color levels in 0-255)

# Minimum ratio of safe blocks required for a level to be considered safe
SAFETY_THRESHOLD = 0.95


def analyze_mip_stats(obj, image):
    """
    Analyze mipmap safety and color uniformity for a Blender object and image.
    
    Args:
        obj: Blender object with UV data
        image: Blender image
        
    Returns:
        Final output structure with mipmap safety results
    """
    # Get image dimensions
    W, H = image.size
    
    # Create UV face map (placeholder - needs implementation)
    start_time = time.time()
    uv_face_map = rasterize_uv_faces(obj, W, H)
    if uv_face_map is None:
        return None
    
    # Get image array
    start_time = time.time()
    image_array = np.array(image.pixels, dtype=np.float32).reshape((H, W, 4))
    
    # Build coverage and image pyramids
    start_time = time.time()
    coverage_pyramid, image_pyramid = build_coverage_pyramid(uv_face_map, image_array)
    max_levels = len(coverage_pyramid)
    
    # Initialize all level results (for safety mipmapping)
    all_results = {}
    for level in range(max_levels):
        h, w = coverage_pyramid[level].shape
        
        all_results[level] = {
            'safe_ratio': np.zeros((h, w), dtype=np.float32),
            'total_blocks': np.zeros((h, w), dtype=np.int32),
            'avg_threshold': np.zeros((h, w), dtype=np.float32)
        }
    
    # Check texture uniformness
    start_time = time.time()
    is_uniform, avg_color = check_texture_uniformness(image_array, uv_face_map >= 0)
    
    # Process mipmapping for safety analysis only
    start_time = time.time()
    for level in range(max_levels - 1, -1, -1):
        analyze_mipmap_safety(level, image_pyramid, coverage_pyramid, all_results)

    
    # Aggregate final results
    start_time = time.time()
    result = aggregate_safety_results(all_results, max_levels)
    
    # Add direct uniformness results
    result['is_uniform_color'] = is_uniform
    result['avg_color'] = [round(c, 4) for c in avg_color]
    
    return result


def rasterize_uv_faces(obj, W, H):
    """
    Create UV face map from Blender object.
    
    Args:
        obj: Blender object
        W, H: Image dimensions
        
    Returns:
        UV face map or None if no UV data
    """

    # Check if object has mesh data
    if not obj.data or obj.type != 'MESH':
        return None
    
    mesh = obj.data
    
    # Check if mesh has UV layers
    if not mesh.uv_layers:
        return None
    
    # Get the first UV layer
    uv_layer = mesh.uv_layers[0]
    
    # Initialize face ID map
    uv_face_map = np.full((H, W), -1, dtype=np.int32)
    
    # Rasterize each face (vectorized bounding-box fill to match original behavior)
    for face_idx, face in enumerate(mesh.polygons):
        # Collect UVs for this face
        uv_coords = []
        for loop_idx in face.loop_indices:
            uv_coord = uv_layer.data[loop_idx].uv
            uv_coords.append([uv_coord.x, uv_coord.y])

        if len(uv_coords) >= 3:
            # Convert UV coordinates to pixel coordinates
            pixel_coords = np.array(uv_coords, dtype=np.float32) * np.array([W, H], dtype=np.float32)

            # Use first triangle's bounding box (matches previous logic)
            triangle_coords = pixel_coords[:3]

            # Bounding box
            min_x = int(np.floor(np.min(triangle_coords[:, 0])))
            max_x = int(np.ceil(np.max(triangle_coords[:, 0])))
            min_y = int(np.floor(np.min(triangle_coords[:, 1])))
            max_y = int(np.ceil(np.max(triangle_coords[:, 1])))

            # Clamp to image bounds
            if min_x > W - 1 or min_y > H - 1 or max_x < 0 or max_y < 0:
                continue
            min_x = max(0, min_x)
            max_x = min(W - 1, max_x)
            min_y = max(0, min_y)
            max_y = min(H - 1, max_y)

            # Vectorized fill of the bounding box (no per-pixel Python loops)
            if max_x >= min_x and max_y >= min_y:
                y_coords, x_coords = np.mgrid[min_y:max_y + 1, min_x:max_x + 1]
                uv_face_map[y_coords, x_coords] = face_idx
    
    return uv_face_map


def point_in_triangle(px, py, triangle_coords):
    """Check if point (px, py) is inside triangle defined by triangle_coords."""
    # Barycentric coordinate method
    x1, y1 = triangle_coords[0]
    x2, y2 = triangle_coords[1] 
    x3, y3 = triangle_coords[2]
    
    # Calculate barycentric coordinates
    denom = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    if abs(denom) < 1e-10:
        return False
        
    a = ((y2 - y3) * (px - x3) + (x3 - x2) * (py - y3)) / denom
    b = ((y3 - y1) * (px - x3) + (x1 - x3) * (py - y3)) / denom
    c = 1 - a - b
    
    return a >= 0 and b >= 0 and c >= 0


def analyze_mipmap_safety(level, image_pyramid, coverage_pyramid, all_results):
    """
    Process safety mipmapping for a single level using numpy operations.
    
    Args:
        level: Current mip level
        image_pyramid: Downsampled image data for each level
        coverage_pyramid: Coverage maps for each level
        all_results: Results storage for all levels
    """
    h, w = coverage_pyramid[level].shape
    coverage = coverage_pyramid[level]
    current_image = image_pyramid[level]
    
    # Ensure we have enough image data for 2x2 blocks
    img_h, img_w = current_image.shape[:2]
    if img_h < 2 or img_w < 2:
        # Not enough data for 2x2 blocks, mark all as safe
        coverage_mask = coverage > 0
        all_results[level]['safe_ratio'][coverage_mask] = 1.0
        all_results[level]['total_blocks'][coverage_mask] = 1.0
        all_results[level]['avg_threshold'][coverage_mask] = 0.0
        return
    
    # Vectorized 2x2 block extraction
    # Extract all 2x2 blocks at once using numpy slicing
    # Use actual image dimensions, not coverage dimensions
    actual_h = min(h, img_h // 2)
    actual_w = min(w, img_w // 2)
    
    # Shape: (img_h, img_w, 4) -> (actual_h, 2, actual_w, 2, 4) -> (actual_h, actual_w, 2, 2, 4)
    blocks = current_image[:actual_h*2, :actual_w*2].reshape(actual_h, 2, actual_w, 2, 4).transpose(0, 2, 1, 3, 4)
    
    # Vectorized degradation calculation
    # Flatten each 2x2 block to (4, 4) - 4 pixels, 4 channels
    blocks_flat = blocks.reshape(actual_h, actual_w, 4, 4)  # (y, x, pixel, channel)
    
    # Calculate block averages for all blocks at once
    block_averages = np.mean(blocks_flat, axis=2)  # (actual_h, actual_w, 4)
    
    # Calculate degradation for all blocks at once
    # Mean absolute difference between each pixel and its block average
    degradations = np.mean(np.abs(blocks_flat - block_averages[:, :, np.newaxis, :]), axis=(2, 3))
    
    # Vectorized coverage masking and result storage
    # Only process the actual blocks we extracted
    coverage_subset = coverage[:actual_h, :actual_w]
    coverage_mask = coverage_subset > 0
    safe_mask = (degradations < DEGRADATION_THRESHOLD) & coverage_mask
    
    # Store all results at once using vectorized operations
    all_results[level]['safe_ratio'][:actual_h, :actual_w][coverage_mask] = safe_mask[coverage_mask].astype(np.float32)
    all_results[level]['total_blocks'][:actual_h, :actual_w][coverage_mask] = 1.0
    all_results[level]['avg_threshold'][:actual_h, :actual_w][coverage_mask] = degradations[coverage_mask]


def check_texture_uniformness(image_array, coverage_map):
    """
    Check if entire texture is uniform color within coverage map.
    
    Args:
        image_array: (H, W, C) image data
        coverage_map: (H, W) coverage map where >0 means covered
        
    Returns:
        tuple of (is_uniform, avg_color) where:
        - is_uniform: True if all covered pixels are similar color
        - avg_color: Average color of all covered pixels
    """
    # Get all covered pixels
    coverage_mask = coverage_map > 0
    if not np.any(coverage_mask):
        return True, np.array([0.0, 0.0, 0.0, 0.0])  # No coverage = uniform
    
    covered_pixels = image_array[coverage_mask]  # (N, C) where N = number of covered pixels
    
    # Calculate average color of all covered pixels
    avg_color = np.mean(covered_pixels, axis=0)
    
    # Check if all pixels are within threshold of average
    color_diffs = np.abs(covered_pixels - avg_color)  # (N, C)
    max_diff = np.max(color_diffs)  # Maximum difference across all pixels and channels
    is_uniform = max_diff < UNIFORMITY_THRESHOLD
    
    return is_uniform, avg_color


def aggregate_safety_results(all_results, max_levels):
    """
    Aggregate results from all levels into final output structure.
    
    Args:
        all_results: Results from all levels
        max_levels: Number of levels processed
        
    Returns:
        Final output structure
    """
    
    # Calculate mip block results
    mip_block_results = []
    for level in range(max_levels - 1):
        level_results = all_results[level]
        h, w = level_results['safe_ratio'].shape
        
        # Calculate safe ratio for this level
        coverage_mask = level_results['total_blocks'] > 0
        if np.any(coverage_mask):
            safe_ratio = np.mean(level_results['safe_ratio'][coverage_mask])
            avg_threshold = np.mean(level_results['avg_threshold'][coverage_mask])
            is_safe = safe_ratio >= SAFETY_THRESHOLD
        else:
            safe_ratio = 1.0
            avg_threshold = 0.0
            is_safe = True

        mip_block_results.append({
            'level': level,
            'resolution': (w, h),
            'safe': is_safe,
            'threshold': avg_threshold
        })
    
    # Find minimum safe resolution (last safe level)
    min_safe_resolution = (1, 1)
    for result in reversed(mip_block_results):  # Start from highest resolution
        if result['safe']:
            min_safe_resolution = result['resolution']
            # Selected safe resolution determined
            break
    
    # Apply 8x8 minimum floor for game engine compatibility
    original_resolution = min_safe_resolution
    min_safe_resolution = (max(8, min_safe_resolution[0]), max(8, min_safe_resolution[1]))
    if original_resolution != min_safe_resolution:
        # Applied 8x8 minimum floor for compatibility
        pass
    
    # Format results nicely
    result = {
        'min_safe_resolution': min_safe_resolution,
        # 'mip_block_results': []
    }
    
    # Format mip block results
    # for mip_result in mip_block_results:
    #     result['mip_block_results'].append({
    #         'level': mip_result['level'],
    #         'resolution': f"{mip_result['resolution'][0]}x{mip_result['resolution'][1]}",
    #         'safe': mip_result['safe'],
    #         'threshold': round(mip_result['threshold'], 6)
    #     })
    
    return result
