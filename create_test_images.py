#!/usr/bin/env python3
"""Create simple test images for the grounding experiment."""

import os
from PIL import Image, ImageDraw

def create_test_image(color, text, filename):
    """Create a simple test image with background color and text."""
    # Create image
    img = Image.new('RGB', (400, 300), color=color)
    draw = ImageDraw.Draw(img)

    # Add text
    try:
        # Try to use a default font
        font = None
        # Draw text in center
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        position = ((400 - text_width) // 2, (300 - text_height) // 2)
        draw.text(position, text, fill=(255, 255, 255) if sum([c*0.3 for c in color]) < 128 else (0, 0, 0))
    except:
        # If font issues, just draw a simple shape
        pass

    # Save image
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    img.save(filename)
    print(f"Created {filename}")

def main():
    # Define our test categories and their colors
    categories = {
        'warehouse': {'relevant': (105, 105, 105), 'irrelevant': (255, 255, 255)},  # Dim gray vs white
        'golden_hour_street': {'relevant': (255, 165, 0), 'irrelevant': (0, 0, 255)},  # Orange vs blue
        'fluorescent_office': {'relevant': (192, 192, 192), 'irrelevant': (0, 100, 0)},  # Silver vs dark green
        'neon_alley': {'relevant': (255, 20, 147), 'irrelevant': (0, 255, 255)},  # Deep pink vs cyan
        'forest_clearing': {'relevant': (34, 139, 34), 'irrelevant': (139, 69, 19)},  # Forest green vs saddle brown
        'hospital_corridor': {'relevant': (192, 192, 192), 'irrelevant': (255, 255, 0)},  # Silver vs yellow
        'subway_car': {'relevant': (64, 64, 64), 'irrelevant': (255, 165, 0)},  # Dark gray vs orange
        'rooftop_sunset': {'relevant': (255, 69, 0), 'irrelevant': (0, 191, 255)}  # Orange red vs deep sky blue
    }

    # Create images for each category
    for category, colors in categories.items():
        # Create relevant image
        create_test_image(
            colors['relevant'],
            f'{category.replace("_", " ").title()}\nRelevant Image',
            f'data/images/grounding/{category}/relevant.jpg'
        )

        # Create irrelevant image
        create_test_image(
            colors['irrelevant'],
            f'{category.replace("_", " ").title()}\nIrrelevant Image',
            f'data/images/grounding/{category}/irrelevant.jpg'
        )

if __name__ == '__main__':
    # Install pillow if needed
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Installing Pillow...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
        from PIL import Image, ImageDraw

    main()