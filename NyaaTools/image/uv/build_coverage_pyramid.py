"""
Coverage Pyramid Builder

This module provides utilities for building coverage pyramids for texture analysis.
"""

import numpy as np



def build_coverage_pyramid(uv_face_map, image_array=None, max_levels=16):
    """
    Build coverage and image pyramids by downsampling both the UV face map and image.
    
    Args:
        uv_face_map: (H, W) UV face map where -1 means no coverage
        image_array: (H, W, C) image data to downsample alongside coverage
        max_levels: maximum number of pyramid levels to build
        
    Returns:
        tuple of (coverage_pyramid, image_pyramid) where:
        - coverage_pyramid: list of coverage maps at different mip levels
        - image_pyramid: list of downsampled images (None if image_array not provided)
    """
    # Calculate all level dimensions upfront
    H, W = uv_face_map.shape
    level_dims = []
    current_h, current_w = H, W
    
    for level in range(max_levels):
        level_dims.append((current_h, current_w))
        if current_h <= 1 or current_w <= 1:
            break
        current_h = current_h // 2
        current_w = current_w // 2
        if current_h == 0 or current_w == 0:
            break
    
    num_levels = len(level_dims)
    
    # Pre-allocate all pyramid arrays
    coverage_pyramid = []
    image_pyramid = [] if image_array is not None else None
    
    # Initialize with original data
    coverage = (uv_face_map >= 0).astype(np.float32)
    current_image = image_array.copy() if image_array is not None else None
    
    # Process each level
    for level in range(num_levels):
        h, w = level_dims[level]
        
        # Store current level
        coverage_pyramid.append(coverage)
        if image_pyramid is not None:
            image_pyramid.append(current_image)
        
        # Check if we can downsample further
        if level == num_levels - 1:
            break
        
        next_h, next_w = level_dims[level + 1]
        
        # Vectorized 2x2 downsampling using advanced numpy operations
        # Coverage: take maximum across 2x2 blocks
        coverage_trimmed = coverage[:next_h*2, :next_w*2]
        coverage = np.max(coverage_trimmed.reshape(next_h, 2, next_w, 2), axis=(1, 3))
        
        # Image: average across 2x2 blocks
        if current_image is not None:
            image_trimmed = current_image[:next_h*2, :next_w*2]
            channels = image_trimmed.shape[2]
            current_image = np.mean(image_trimmed.reshape(next_h, 2, next_w, 2, channels), axis=(1, 3))
    
    return coverage_pyramid, image_pyramid


