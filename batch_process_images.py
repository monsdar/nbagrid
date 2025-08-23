#!/usr/bin/env python3
"""
Batch Image Processor for NBA Grid Entity Images

This script processes all images in the staticfiles/entity_images directory:
1. Crops images taller than 1200px to 1200px height (keeping top portion)
2. Reduces all images to 25% of their original size (skips images <=300px in height or width)

Requirements: pip install Pillow
"""

import os
import sys
from pathlib import Path
from PIL import Image
import argparse

def process_image(image_path, output_dir, crop_height=1200, scale_factor=0.25, min_size=300):
    """
    Process a single image according to specifications.
    
    Args:
        image_path: Path to input image
        output_dir: Directory to save processed image
        crop_height: Maximum height before cropping (default: 1200)
        scale_factor: Scale factor for final size (default: 0.25)
        min_size: Minimum dimension (height or width) before scaling (default: 300)
    """
    try:
        # Open image
        with Image.open(image_path) as img:
            original_width, original_height = img.size
            print(f"Processing: {image_path.name} ({original_width}x{original_height})")
            
            # Step 1: Crop if height > 1200px (keep top portion)
            if original_height > crop_height:
                # Calculate crop box: (left, top, right, bottom)
                # Keep top portion, crop from bottom
                crop_box = (0, 0, original_width, crop_height)
                img = img.crop(crop_box)
                print(f"  Cropped to height: {crop_height}px")
            
            # Step 2: Scale to 25% only if dimensions are larger than min_size
            current_width, current_height = img.size
            if current_width > min_size or current_height > min_size:
                new_width = int(current_width * scale_factor)
                new_height = int(current_height * scale_factor)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"  Scaled to: {new_width}x{new_height}")
            else:
                print(f"  Skipped scaling (dimensions <= {min_size}px)")
            
            # Save processed image
            output_path = output_dir / image_path.name
            img.save(output_path, optimize=True, quality=95)
            
            # Calculate file size reduction
            original_size = image_path.stat().st_size
            new_size = output_path.stat().st_size
            reduction = ((original_size - new_size) / original_size) * 100
            
            print(f"  File size: {original_size / 1024:.1f}KB -> {new_size / 1024:.1f}KB ({reduction:.1f}% reduction)")
            print()
            
            return True
            
    except Exception as e:
        print(f"Error processing {image_path.name}: {e}")
        return False

def batch_process_images(input_dir, output_dir, crop_height=1200, scale_factor=0.25, min_size=300):
    """
    Process all images in the input directory.
    
    Args:
        input_dir: Directory containing images to process
        output_dir: Directory to save processed images
        crop_height: Maximum height before cropping
        scale_factor: Scale factor for final size
        min_size: Minimum dimension (height or width) before scaling
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    # Create output directory if it doesn't exist
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Supported image formats
    image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp'}
    
    # Find all image files
    image_files = [f for f in input_path.iterdir() 
                   if f.is_file() and f.suffix.lower() in image_extensions]
    
    if not image_files:
        print(f"No image files found in {input_dir}")
        return
    
    print(f"Found {len(image_files)} images to process")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Crop height: {crop_height}px")
    print(f"Scale factor: {scale_factor * 100}%")
    print(f"Minimum size threshold: {min_size}px")
    print("-" * 50)
    
    # Process each image
    successful = 0
    failed = 0
    
    for image_file in image_files:
        if process_image(image_file, output_path, crop_height, scale_factor, min_size):
            successful += 1
        else:
            failed += 1
    
    print("-" * 50)
    print(f"Processing complete!")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total: {len(image_files)}")

def main():
    parser = argparse.ArgumentParser(description='Batch process NBA Grid entity images')
    parser.add_argument('--input', '-i', 
                       default='staticfiles/entity_images',
                       help='Input directory containing images (default: staticfiles/entity_images)')
    parser.add_argument('--output', '-o',
                       default='staticfiles/entity_images_processed',
                       help='Output directory for processed images (default: staticfiles/entity_images_processed)')
    parser.add_argument('--crop-height', '-c',
                       type=int, default=1200,
                       help='Maximum height before cropping (default: 1200)')
    parser.add_argument('--scale-factor', '-s',
                       type=float, default=0.25,
                       help='Scale factor for final size (default: 0.25)')
    parser.add_argument('--min-size', '-m',
                       type=int, default=300,
                       help='Minimum dimension (height or width) before scaling (default: 300)')
    parser.add_argument('--preview', '-p',
                       action='store_true',
                       help='Preview what would be processed without actually processing')
    
    args = parser.parse_args()
    
    # Check if input directory exists
    if not os.path.exists(args.input):
        print(f"Error: Input directory '{args.input}' does not exist")
        sys.exit(1)
    
    if args.preview:
        print("PREVIEW MODE - No files will be modified")
        print(f"Input: {args.input}")
        print(f"Output: {args.output}")
        print(f"Crop height: {args.crop_height}px")
        print(f"Scale factor: {args.scale_factor * 100}%")
        print(f"Minimum size threshold: {args.min_size}px")
        
        input_path = Path(args.input)
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp'}
        image_files = [f for f in input_path.iterdir() 
                      if f.is_file() and f.suffix.lower() in image_extensions]
        
        print(f"\nWould process {len(image_files)} images:")
        for img in image_files[:10]:  # Show first 10
            print(f"  {img.name}")
        if len(image_files) > 10:
            print(f"  ... and {len(image_files) - 10} more")
        return
    
    # Process images
    batch_process_images(args.input, args.output, args.crop_height, args.scale_factor, args.min_size)

if __name__ == "__main__":
    main()
