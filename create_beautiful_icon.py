#!/usr/bin/env python3
"""
Create a beautiful icon for ANAGHA SOLUTION app
"""

import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("PIL/Pillow not available. Installing...")
    os.system("pip3 install Pillow --quiet 2>/dev/null")
    try:
        from PIL import Image, ImageDraw, ImageFont
        HAS_PIL = True
    except:
        HAS_PIL = False

def create_icon():
    """Create a beautiful icon for the app"""
    app_path = Path.home() / "Desktop" / "ANAGHA SOLUTION.app" / "Contents" / "Resources"
    app_path.mkdir(parents=True, exist_ok=True)
    
    if not HAS_PIL:
        print("⚠ Cannot create custom icon without PIL. Using system icon.")
        return False
    
    # Icon dimensions
    size = 1024  # High resolution for Retina displays
    
    # Create image with gradient background
    img = Image.new('RGB', (size, size), color='#1a237e')  # Deep blue
    draw = ImageDraw.Draw(img)
    
    # Create gradient background
    for y in range(size):
        # Gradient from dark blue to lighter blue
        r = int(26 + (y / size) * 30)
        g = int(35 + (y / size) * 40)
        b = int(126 + (y / size) * 50)
        draw.rectangle([(0, y), (size, y+1)], fill=(r, g, b))
    
    # Draw circular background for icon
    center = size // 2
    radius = size // 2 - 50
    circle_color = '#2196F3'  # Bright blue
    draw.ellipse([center-radius, center-radius, center+radius, center+radius], 
                 fill=circle_color, outline='#1976D2', width=20)
    
    # Draw inner circle for depth
    inner_radius = radius - 40
    draw.ellipse([center-inner_radius, center-inner_radius, center+inner_radius, center+inner_radius], 
                 fill='#42A5F5', outline='#2196F3', width=15)
    
    # Draw email envelope icon
    envelope_size = size // 3
    envelope_x = center - envelope_size // 2
    envelope_y = center - envelope_size // 2 - 30
    
    # Envelope body
    envelope_points = [
        (envelope_x, envelope_y + envelope_size // 3),
        (envelope_x + envelope_size, envelope_y + envelope_size // 3),
        (envelope_x + envelope_size, envelope_y + envelope_size),
        (envelope_x, envelope_y + envelope_size)
    ]
    draw.polygon(envelope_points, fill='white', outline='#E3F2FD', width=8)
    
    # Envelope flap (top triangle)
    flap_points = [
        (envelope_x, envelope_y + envelope_size // 3),
        (center, envelope_y),
        (envelope_x + envelope_size, envelope_y + envelope_size // 3)
    ]
    draw.polygon(flap_points, fill='#E3F2FD', outline='white', width=6)
    
    # Draw "@" symbol or "AS" text
    try:
        # Try to use system fonts
        font_size = 200
        fonts_to_try = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/HelveticaNeue.ttc"
        ]
        font = None
        for font_path in fonts_to_try:
            try:
                if font_path.endswith('.ttc'):
                    font = ImageFont.truetype(font_path, font_size, index=0)
                else:
                    font = ImageFont.truetype(font_path, font_size)
                break
            except:
                continue
        
        if font is None:
            font = ImageFont.load_default()
        
        # Draw "AS" text
        text = "AS"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = center - text_width // 2
        text_y = center + envelope_size // 2 + 20
        
        # Draw text with shadow for depth
        shadow_offset = 5
        draw.text((text_x + shadow_offset, text_y + shadow_offset), text, 
                 fill='#1565C0', font=font)
        draw.text((text_x, text_y), text, fill='white', font=font)
        
    except Exception as e:
        print(f"Could not draw text: {e}")
    
    # Save as PNG first
    png_path = app_path / "appicon.png"
    img.save(png_path, "PNG", quality=95)
    
    # Convert to .icns using sips (macOS built-in tool)
    icns_path = app_path / "appicon.icns"
    os.system(f'sips -s format icns "{png_path}" --out "{icns_path}" 2>/dev/null')
    
    if icns_path.exists():
        print("✓ Beautiful custom icon created successfully!")
        return True
    else:
        print("⚠ Could not create .icns file, but PNG is available")
        return False

if __name__ == "__main__":
    success = create_icon()
    if success:
        print("\n✅ Icon created! The app should now show a beautiful custom icon.")
        print("   If the icon doesn't update immediately, try:")
        print("   1. Right-click the app > Get Info")
        print("   2. Drag the icon from the Resources folder to the app icon in Get Info")
    else:
        print("\n⚠ Using system default icon")

