"""
Iterative mipmap analysis using numpy arrays.

This module provides the main entry point for analyzing mipmap safety
and color uniformity using an iterative, numpy-based approach.
"""

import numpy as np
import json
import os
import time

from .build_coverage_pyramid import build_coverage_pyramid
from ..save_numpy_image import save_numpy_as_image, save_numpy_as_raw


# Max color difference for entire texture to be considered uniform
UNIFORMITY_THRESHOLD = 0.008  # (~2 color levels in 0-255)

# Max detail loss allowed for 2x2 blocks when downsampling to 1 block
DEGRADATION_THRESHOLD = 0.05
DEBUG_THRESHOLD_HEATMAP = False  # Generate magnitude heatmap visualizations


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

    # Create UV face map
    uv_face_map = rasterize_uv_faces(obj, W, H)
    if uv_face_map is None:
        return None

    coverage_start_time = time.time()

    # Get image array
    image_array = np.array(image.pixels, dtype=np.float32).reshape((H, W, 4))

    # Flip vertically to view better in the console
    # image_array = np.flipud(image_array)

    # Build coverage and image pyramids
    coverage_pyramid, image_pyramid = build_coverage_pyramid(uv_face_map, image_array)
    pyramid_end_time = time.time()
    pyramid_duration = round(
        (pyramid_end_time - coverage_start_time), 3
    )  # Convert to seconds

    # DEBUG: Extract UV data and original material image pixels
    # debug_extract_for_testing(obj, image)

    # DEBUG: ASCII art dump of pyramid levels
    target_level = None
    max_levels = len(coverage_pyramid)
    for level in range(max_levels):
        h, w = coverage_pyramid[level].shape
        if w <= 32 and h <= 32:  # Find a level that's 64x64 or smaller
            target_level = level
            break

    if target_level is not None:
        coverage_data = coverage_pyramid[target_level]
        h, w = coverage_data.shape
        print(f"📊 Coverage Level {target_level} ({w}x{h}):")

        # ASCII coverage map (flipped vertically to match UV coordinates)
        for y in range(h - 1, -1, -1):  # Start from top, go to bottom
            row = ""
            for x in range(w):
                val = coverage_data[y, x]
                if val > 0.5:
                    row += "█"  # White/covered
                else:
                    row += "░"  # Black/uncovered
            print(f"  {row}")
    else:
        print("  No suitable level found for ASCII dump")

    print(f"         ⏱️ Build coverage and image pyramids: {pyramid_duration} seconds")

    # Initialize all level results (for safety mipmapping)
    all_results = {}
    for level in range(max_levels):
        h, w = coverage_pyramid[level].shape

        all_results[level] = {
            "safe_ratio": np.zeros((h, w), dtype=np.float32),
            "total_blocks": np.zeros((h, w), dtype=np.int32),
            "channel_stats": np.zeros(
                (h, w, 8), dtype=np.float32
            ),  # [min_r, min_g, min_b, min_a, max_r, max_g, max_b, max_a]
        }

    # Check texture uniformness
    is_uniform, avg_color = check_texture_uniformness(image_array, uv_face_map >= 0)

    # Process mipmapping for safety analysis only
    mipmap_start_time = time.time()
    for level in range(0, max_levels):
        analyze_mipmap_safety(level, image_pyramid, coverage_pyramid, all_results)

    # Aggregate final results
    result = aggregate_safety_results(all_results, max_levels, W, H)
    mipmap_end_time = time.time()

    mipmap_duration = round(
        (mipmap_end_time - mipmap_start_time), 3
    )  # Convert to seconds
    print(f"        ⏱️ Safety analysis: {mipmap_duration} seconds")

    # Add direct uniformness results
    result["is_uniform_color"] = is_uniform
    result["avg_color"] = [round(c, 4) for c in avg_color]

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
    if not obj.data or obj.type != "MESH":
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
            pixel_coords = np.array(uv_coords, dtype=np.float32) * np.array(
                [W, H], dtype=np.float32
            )

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
                y_coords, x_coords = np.mgrid[min_y : max_y + 1, min_x : max_x + 1]
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

    📐 Image pyramid dimensions:
    Level 0: 4096x4096 (assuming we started at a 4K image)
    Level 1: 2048x2048
    Level 2: 1024x1024
    Level 3: 512x512
    Level 4: 256x256
    Level 5: 128x128
    Level 6: 64x64
    Level 7: 32x32
    Level 8: 16x16
    Level 9: 8x8
    Level 10: 4x4
    Level 11: 2x2
    """
    h, w = coverage_pyramid[level].shape
    current_image = image_pyramid[level]

    # Ensure we have enough image data for 2x2 blocks
    img_h, img_w = current_image.shape[:2]
    if img_h < 2 or img_w < 2:
        # Not enough data for 2x2 blocks, mark all as safe
        coverage_for_blocks = (
            coverage_pyramid[level + 1]
            if level + 1 < len(coverage_pyramid)
            else coverage_pyramid[level]
        )
        coverage_mask = coverage_for_blocks > 0
        all_results[level]["safe_ratio"][coverage_mask] = 1.0
        all_results[level]["total_blocks"][coverage_mask] = 1.0
        # Set channel stats to zero (no degradation)
        all_results[level]["channel_stats"][coverage_mask] = 0.0
        return

    # Vectorized 2x2 block extraction
    # Extract all 2x2 blocks at once using numpy slicing
    # Use actual image dimensions, not coverage dimensions
    actual_h = min(h, img_h // 2)
    actual_w = min(w, img_w // 2)

    # Shape: (img_h, img_w, 4) -> (actual_h, 2, actual_w, 2, 4) -> (actual_h, actual_w, 2, 2, 4)
    image_subset = current_image[: actual_h * 2, : actual_w * 2]

    blocks = image_subset.reshape(actual_h, 2, actual_w, 2, 4).transpose(0, 2, 1, 3, 4)

    # Flatten each 2x2 block to (4, 4) - 4 pixels, 4 channels
    blocks_flat = blocks.reshape(actual_h, actual_w, 4, 4)  # (y, x, pixels, channels)

    # Use the NEXT level's coverage, which is already downsampled to match our block resolution
    # When we analyze 2x2 blocks from level N, we're creating level N+1 resolution
    coverage_for_blocks = (
        coverage_pyramid[level + 1]
        if level + 1 < len(coverage_pyramid)
        else coverage_pyramid[level]
    )
    coverage_mask = coverage_for_blocks[:actual_h, :actual_w] > 0

    # Calculate min/max for ALL blocks
    block_mins = np.min(blocks_flat, axis=2)  # (y, x, channels)
    block_maxs = np.max(blocks_flat, axis=2)  # (y, x, channels)

    # Calculate degradation per channel
    channel_degradations = block_maxs - block_mins

    # Calculate magnitude based on cumulative detail loss
    if level > 0:  # Skip original level - no detail loss to measure
        previous_level = all_results[level - 1]
        if "magnitude" in previous_level:
            # Get previous level's cumulative magnitude

            previous_magnitude = previous_level["magnitude"]

            # Downsample previous_magnitude to match current level's shape
            # Use max to preserve worst-case detail loss
            prev_h, prev_w = previous_magnitude.shape
            if prev_h >= 2 and prev_w >= 2:
                # Take 2x2 blocks and get max of each block
                target_h = prev_h // 2
                target_w = prev_w // 2
                prev_reshaped = previous_magnitude[
                    : target_h * 2, : target_w * 2
                ].reshape(target_h, 2, target_w, 2)
                downsampled_magnitude = np.max(
                    prev_reshaped, axis=(1, 3)
                )  # (target_h, target_w)
            else:
                # Too small to downsample, use as-is or zero
                downsampled_magnitude = np.zeros((actual_h, actual_w), dtype=np.float32)
        else:
            # Fallback to zero if previous level doesn't have magnitude
            downsampled_magnitude = np.zeros((actual_h, actual_w), dtype=np.float32)

        # Current level's local variation (proxy for detail loss)
        current_magnitude = np.sum(channel_degradations, axis=2)

        # Cumulative detail loss: previous + current (additive stacking)
        magnitude = downsampled_magnitude + current_magnitude
    else:
        # Original level - no detail loss, magnitude = 0
        magnitude = np.zeros((actual_h, actual_w), dtype=np.float32)

    if DEBUG_THRESHOLD_HEATMAP:
        # Blue channel shows normalized magnitude when under threshold
        # Red channel shows when threshold is exceeded
        threshold_heatmap = np.zeros((actual_h, actual_w, 4), dtype=np.float32)

        # Normalize magnitude to threshold (0-1 scale)
        normalized_magnitude = np.clip(magnitude / DEGRADATION_THRESHOLD, 0, 1)

        # Blue channel: normalized magnitude when under threshold
        under_threshold = magnitude < DEGRADATION_THRESHOLD
        threshold_heatmap[under_threshold, 2] = normalized_magnitude[
            under_threshold
        ]  # Blue = normalized magnitude
        threshold_heatmap[under_threshold, 3] = 1.0  # Alpha = opaque for covered

        # Red channel: 1.0 when threshold is exceeded
        over_threshold = magnitude >= DEGRADATION_THRESHOLD
        threshold_heatmap[over_threshold, 0] = 1.0  # Red = threshold exceeded
        threshold_heatmap[over_threshold, 3] = 1.0  # Alpha = opaque for covered

        # Only show covered blocks
        threshold_heatmap[~coverage_mask] = 0.0  # Uncovered areas = transparent

        # Save using our utility function
        heatmap_flat = threshold_heatmap.reshape(actual_h, actual_w, 4)
        save_numpy_as_image(
            f"threshold-{level}",
            (actual_w, actual_h),
            heatmap_flat,
            "debug",
            mode="RGBA",
        )

    # Check safety using magnitude (total detail loss from original)
    block_safe = magnitude < DEGRADATION_THRESHOLD  # (actual_h, actual_w)

    # Coverage masking (coverage_mask already calculated above)
    safe_mask = block_safe & coverage_mask

    # Direct assignment without double indexing
    all_results[level]["safe_ratio"][:actual_h, :actual_w] = safe_mask.astype(
        np.float32
    )
    all_results[level]["total_blocks"][:actual_h, :actual_w] = coverage_mask.astype(
        np.float32
    )

    # Store cumulative magnitude instead of min/max arrays
    all_results[level]["magnitude"] = magnitude


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

    covered_pixels = image_array[
        coverage_mask
    ]  # (N, C) where N = number of covered pixels

    # Calculate average color of all covered pixels
    avg_color = np.mean(covered_pixels, axis=0)

    # Check if all pixels are within threshold of average
    color_diffs = np.abs(covered_pixels - avg_color)  # (N, C)
    max_diff = np.max(color_diffs)  # Maximum difference across all pixels and channels
    is_uniform = max_diff < UNIFORMITY_THRESHOLD

    return is_uniform, avg_color


def aggregate_safety_results(all_results, max_levels, W, H):
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
        h, w = level_results["safe_ratio"].shape

        # Calculate safe ratio for this level
        coverage_mask = level_results["total_blocks"] > 0
        if np.any(coverage_mask):
            # Use cumulative magnitude for safety analysis
            magnitude = level_results["magnitude"]
            # Ensure shapes match
            if magnitude.shape == coverage_mask.shape:
                covered_magnitude = magnitude[coverage_mask]
            else:
                # Fallback to safe_ratio if shapes don't match
                covered_magnitude = level_results["safe_ratio"][coverage_mask]

            # Calculate magnitude statistics
            max_magnitude = np.max(covered_magnitude)
            avg_magnitude = np.mean(covered_magnitude)

            # Safety based on cumulative detail loss: ALL blocks must be safe
            is_safe = np.all(level_results["safe_ratio"][coverage_mask] >= 1.0)

            # Store magnitude statistics for debugging
            magnitude_stats = {
                "max_magnitude": max_magnitude,
                "avg_magnitude": avg_magnitude,
            }
        else:
            # No blocks = 0% safe
            is_safe = False

        mip_block_results.append(
            {
                "level": level,
                "resolution": (w, h),
                "safe": is_safe,
                "magnitude_stats": (
                    magnitude_stats if "magnitude_stats" in locals() else None
                ),
            }
        )

    # Find minimum safe resolution (LAST safe level - smallest resolution)
    # Start with original resolution as default
    original_resolution = (W, H)
    min_safe_resolution = original_resolution

    # Find the LAST safe level (smallest resolution that's safe)
    for result in reversed(mip_block_results):
        if result["safe"]:
            min_safe_resolution = result["resolution"]
            break

    # Apply 8x8 minimum floor for game engine compatibility
    min_safe_resolution = (
        max(8, min_safe_resolution[0]),
        max(8, min_safe_resolution[1]),
    )

    result = {
        "min_safe_resolution": min_safe_resolution,
    }

    return result


def debug_extract_for_testing(obj, image):
    """
    Extract UV data and original material image pixels, then save to hardcoded path.
    Uses the actual obj and image parameters passed to analyze_mip_stats.
    """

    def debug_print(*msgs):
        print("        ", *msgs)
        return

    try:
        # Hardcoded path
        export_dir = r"B:\OneDrive\Desktop\textures"

        if not obj or obj.type != "MESH":
            debug_print("⚠️ Invalid object passed to debug extraction")
            return

        if not image:
            debug_print("⚠️ No image passed to debug extraction")
            return

        image_name = image.name
        debug_print(f"🔍 DEBUG: Extracting test data for image: {image_name}")

        # Initialize result structure
        debug_data = {"uv_faces": [], "image_pixels": [], "image_dimensions": []}

        # Extract UV triangle data
        if obj.data and obj.data.uv_layers:
            mesh = obj.data
            uv_layer = mesh.uv_layers[0]

            for face_idx, face in enumerate(mesh.polygons):
                # Collect UVs for this face
                uv_coords = []
                for loop_idx in face.loop_indices:
                    uv_coord = uv_layer.data[loop_idx].uv
                    uv_coords.append([float(uv_coord.x), float(uv_coord.y)])

                if len(uv_coords) >= 3:
                    # Store UV coordinates as list of [u, v] pairs
                    debug_data["uv_faces"].append(uv_coords)

            debug_print(f"  📐 Extracted {len(debug_data['uv_faces'])} UV faces")
        else:
            debug_print(f"  ⚠️ No UV data found for object {obj.name}")

        # Extract image pixel data from the passed image
        if image.pixels:
            W, H = image.size
            debug_data["image_dimensions"] = [int(W), int(H)]

            # Convert pixels to flat list format
            pixels = np.array(image.pixels, dtype=np.float32).reshape((H, W, -1))

            # Flip vertically to view better in the console
            # pixels = np.flipud(pixels)

            # Convert RGBA arrays to packed integers for maximum compression
            # Convert float [0,1] to uint8 [0,255] then pack into single integer
            pixels_uint8 = (pixels * 255).astype(np.uint8)
            pixels_flat = pixels_uint8.reshape(-1, pixels.shape[2])

            # Pack each pixel into a single integer (RGBA = 32-bit)
            packed_pixels = []
            for pixel in pixels_flat:
                if len(pixel) == 4:  # RGBA
                    # Pack as: R << 24 | G << 16 | B << 8 | A
                    packed = (
                        (pixel[0] << 24) | (pixel[1] << 16) | (pixel[2] << 8) | pixel[3]
                    )
                elif len(pixel) == 3:  # RGB
                    # Pack as: R << 24 | G << 16 | B << 8 | 255 (full alpha)
                    packed = (pixel[0] << 24) | (pixel[1] << 16) | (pixel[2] << 8) | 255
                else:
                    # Single channel, duplicate for RGB
                    packed = (pixel[0] << 24) | (pixel[0] << 16) | (pixel[0] << 8) | 255
                packed_pixels.append(int(packed))

            debug_data["image_pixels"] = packed_pixels

            debug_print(f"  🖼️ Extracted {W}x{H} image with {pixels.shape[2]} channels")

            # Save raw numpy data for debugging
            try:
                raw_filename = f"{image_name}.raw"
                debug_previews_dir = os.path.join(export_dir, "debug_previews")
                os.makedirs(debug_previews_dir, exist_ok=True)
                save_numpy_as_raw(
                    image_name,
                    (image.size[0], image.size[1]),
                    pixels,
                    debug_previews_dir,
                )
                debug_print(f"  💾 Raw numpy data saved: {raw_filename}")
            except Exception as e:
                debug_print(f"  ⚠️ Failed to save raw numpy data: {e}")
        else:
            debug_print(f"  ⚠️ Image {image.name} has no pixel data")

        # Save debug data if we have valid data
        if debug_data.get("uv_faces") and debug_data.get("image_pixels"):
            try:
                # Create filename using image name
                filename = f"{image_name}.test-image.json"
                filepath = os.path.join(export_dir, filename)

                # Save debug data
                with open(filepath, "w") as f:
                    json.dump(debug_data, f, indent=2)

                debug_print(f"  💾 Debug data saved: {filename}")
                debug_print(f"     📐 UV faces: {len(debug_data['uv_faces'])}")
                debug_print(
                    f"     🖼️ Image: {debug_data['image_dimensions'][0]}x{debug_data['image_dimensions'][1]}"
                )
                debug_print(f"     📊 Pixels: {len(debug_data['image_pixels'])}")

            except Exception as e:
                debug_print(f"  ❌ Failed to save debug data: {e}")
        else:
            debug_print(f"  ⚠️ No valid debug data to save for image: {image_name}")

    except Exception as e:
        debug_print(f"❌ DEBUG extraction failed: {e}")


def save_debug_preview(mask, minmax_array, level, export_dir, prefix="debug"):
    """Save debug preview data as raw binary files for external conversion"""
    try:
        # Create debug directory
        debug_dir = os.path.join(export_dir, "debug_previews")
        os.makedirs(debug_dir, exist_ok=True)

        # Save coverage mask as raw binary
        # Format: 2 int32 (width, height), then uint8 values (0 or 255)
        mask_binary = (mask * 255).astype(np.uint8)
        mask_path = os.path.join(debug_dir, f"{prefix}_mask_l{level}.raw")

        with open(mask_path, "wb") as f:
            # Write dimensions as int32
            f.write(np.array([mask.shape[1], mask.shape[0]], dtype=np.int32).tobytes())
            # Write mask data as uint8
            f.write(mask_binary.tobytes())

        print(
            f"        DEBUG Save: mask shape {mask.shape}, min/max: {np.min(mask):.6f}, {np.max(mask):.6f}"
        )

        # Save min/max visualization as raw binary
        if (
            minmax_array.shape[2] >= 8
        ):  # min_r, min_g, min_b, min_a, max_r, max_g, max_b, max_a
            # Use max values for RGB channels
            max_rgb = minmax_array[:, :, 4:7]  # max_r, max_g, max_b
            max_rgb_uint8 = (max_rgb * 255).astype(np.uint8)

            minmax_path = os.path.join(debug_dir, f"{prefix}_minmax_l{level}.raw")

            with open(minmax_path, "wb") as f:
                # Write dimensions as int32
                f.write(
                    np.array(
                        [minmax_array.shape[1], minmax_array.shape[0]], dtype=np.int32
                    ).tobytes()
                )
                # Write RGBA data as uint8 (R, G, B, A)
                rgba_data = np.zeros(
                    (minmax_array.shape[0], minmax_array.shape[1], 4), dtype=np.uint8
                )
                rgba_data[:, :, :3] = max_rgb_uint8
                rgba_data[:, :, 3] = 255  # Full alpha
                f.write(rgba_data.tobytes())

            print(
                f"        DEBUG Save: minmax shape {minmax_array.shape}, max_rgb min/max: {np.min(max_rgb):.6f}, {np.max(max_rgb):.6f}"
            )

        print(
            f"      📸 Debug raw data saved: {prefix}_mask_l{level}.raw, {prefix}_minmax_l{level}.raw"
        )

    except Exception as e:
        print(f"      ⚠️ Failed to save debug preview: {e}")
