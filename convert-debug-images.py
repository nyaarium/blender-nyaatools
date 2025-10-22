#!/usr/bin/env python3
"""
Convert raw binary debug files to PNG images using PIL.
Run this after the baker to convert .raw files to .png images.
"""

import os
import numpy as np
from PIL import Image
import glob

def convert_raw_to_png(raw_file_path):
    """Convert a single .raw file to .png"""
    try:
        with open(raw_file_path, 'rb') as f:
            # Read dimensions (2 int32 values)
            width = int.from_bytes(f.read(4), byteorder='little')
            height = int.from_bytes(f.read(4), byteorder='little')
            
            # Read pixel data
            if 'mask' in raw_file_path:
                # Grayscale mask data
                pixel_data = np.frombuffer(f.read(), dtype=np.uint8)
                pixel_data = pixel_data.reshape((height, width))
                
                # Convert to PIL Image
                img = Image.fromarray(pixel_data, mode='L')
                
            else:
                # RGBA data
                pixel_data = np.frombuffer(f.read(), dtype=np.uint8)
                pixel_data = pixel_data.reshape((height, width, 4))
                
                # Convert to PIL Image
                img = Image.fromarray(pixel_data, mode='RGBA')
            
            # Save as PNG
            png_path = raw_file_path.replace('.raw', '.png')
            img.save(png_path)
            print(f"✅ Converted: {os.path.basename(raw_file_path)} -> {os.path.basename(png_path)}")
            
    except Exception as e:
        print(f"❌ Failed to convert {raw_file_path}: {e}")

def main():
    """Convert all .raw files in debug_previews directory"""
    debug_dir = "/mnt/b/OneDrive/Desktop/textures/debug_previews"
    
    if not os.path.exists(debug_dir):
        print(f"❌ Debug directory not found: {debug_dir}")
        return
    
    raw_files = glob.glob(os.path.join(debug_dir, "*.raw"))
    
    if not raw_files:
        print("❌ No .raw files found in debug_previews directory")
        return
    
    print(f"🔍 Found {len(raw_files)} .raw files to convert")
    
    for raw_file in raw_files:
        convert_raw_to_png(raw_file)
    
    print("🎉 Conversion complete!")

if __name__ == "__main__":
    main()
