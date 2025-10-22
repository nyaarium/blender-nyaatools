"""
Streamlined functions to save numpy arrays as images using raw binary + PIL conversion.
Bypasses Blender's garbage image system entirely.
"""

import os
import numpy as np

def save_numpy_as_image(name, dimensions, data, output_dir, mode='auto'):
    """
    Save a numpy array as an image using raw binary + PIL conversion.
    
    Args:
        name: Base filename (without extension)
        dimensions: (width, height) tuple
        data: numpy array of image data
        output_dir: Directory to save files
        mode: PIL mode ('L' for grayscale, 'RGB', 'RGBA', or 'auto' to detect)
    
    Returns:
        Path to saved PNG file
    """
    try:
        # Dynamic import to avoid module-level dependency
        from PIL import Image
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        width, height = dimensions
        
        # Auto-detect mode based on data shape
        if mode == 'auto':
            if len(data.shape) == 2:
                mode = 'L'  # Grayscale
            elif len(data.shape) == 3 and data.shape[2] == 3:
                mode = 'RGB'
            elif len(data.shape) == 3 and data.shape[2] == 4:
                mode = 'RGBA'
            else:
                raise ValueError(f"Cannot auto-detect mode for data shape: {data.shape}")
        
        # Convert data to uint8 if needed
        if data.dtype != np.uint8:
            if np.max(data) <= 1.0:
                # Assume data is in range [0.0, 1.0]
                data_uint8 = (data * 255).astype(np.uint8)
            else:
                # Assume data is already in range [0, 255]
                data_uint8 = data.astype(np.uint8)
        else:
            data_uint8 = data
        
        # Reshape data to match dimensions
        if mode == 'L':
            data_reshaped = data_uint8.reshape((height, width))
        else:
            data_reshaped = data_uint8.reshape((height, width, -1))
        
        # Create PIL Image
        img = Image.fromarray(data_reshaped, mode=mode)
        
        # Save as PNG
        png_path = os.path.join(output_dir, f"{name}.png")
        img.save(png_path)
        
        print(f"✅ Saved: {name}.png ({width}x{height}, {mode})")
        return png_path
        
    except Exception as e:
        print(f"❌ Failed to save {name}: {e}")
        return None

def save_numpy_as_raw(name, dimensions, data, output_dir):
    """
    Save numpy array as raw binary file (for debugging or later conversion).
    
    Args:
        name: Base filename (without extension)
        dimensions: (width, height) tuple
        data: numpy array of image data
        output_dir: Directory to save files
    
    Returns:
        Path to saved .raw file
    """
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        width, height = dimensions
        
        # Convert data to uint8 if needed
        if data.dtype != np.uint8:
            if np.max(data) <= 1.0:
                # Assume data is in range [0.0, 1.0]
                data_uint8 = (data * 255).astype(np.uint8)
            else:
                # Assume data is already in range [0, 255]
                data_uint8 = data.astype(np.uint8)
        else:
            data_uint8 = data
        
        # Save as raw binary
        raw_path = os.path.join(output_dir, f"{name}.raw")
        
        with open(raw_path, 'wb') as f:
            # Write dimensions as int32
            f.write(np.array([width, height], dtype=np.int32).tobytes())
            # Write pixel data
            f.write(data_uint8.tobytes())
        
        print(f"✅ Saved raw: {name}.raw ({width}x{height})")
        return raw_path
        
    except Exception as e:
        print(f"❌ Failed to save raw {name}: {e}")
        return None
