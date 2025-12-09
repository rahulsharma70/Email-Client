#!/bin/bash

# Script to create a beautiful .app bundle with icon for ANAGHA SOLUTION

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_NAME="ANAGHA SOLUTION"
APP_PATH="$HOME/Desktop/${APP_NAME}.app"

echo "Creating beautiful .app bundle with icon..."

# Remove existing app if it exists
rm -rf "$APP_PATH"

# Create app bundle structure
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

# Create Info.plist
cat > "$APP_PATH/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>ANAGHA_SOLUTION</string>
    <key>CFBundleIdentifier</key>
    <string>com.anagha.solution</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string>appicon</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.9</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# Create launcher script
cat > "$APP_PATH/Contents/MacOS/ANAGHA_SOLUTION" << 'LAUNCHER'
#!/bin/bash

# Get the directory where the dashboard folder is located
# Assuming the app is on Desktop and dashboard is also on Desktop
DASHBOARD_DIR="$HOME/Desktop/dashboard"

# Verify dashboard directory exists
if [ ! -d "$DASHBOARD_DIR" ]; then
    osascript -e 'display dialog "Error: Could not find dashboard folder at ~/Desktop/dashboard" buttons {"OK"} default button "OK"'
    exit 1
fi

# Open Terminal and start server
osascript << EOF
tell application "Terminal"
    activate
    do script "cd '$DASHBOARD_DIR' && if [ -d 'venv' ]; then source venv/bin/activate; fi && clear && echo '╔════════════════════════════════════════╗' && echo '║   ANAGHA SOLUTION - Web Server        ║' && echo '╚════════════════════════════════════════╝' && echo '' && echo '🚀 Starting server...' && echo '' && echo '📱 Access the application at:' && echo '   • http://localhost:5001' && echo '   • http://127.0.0.1:5001' && echo '' && echo '⏹️  Press Ctrl+C to stop the server' && echo '' && echo '════════════════════════════════════════' && echo '' && python3 web_app.py"
end tell
EOF
LAUNCHER

chmod +x "$APP_PATH/Contents/MacOS/ANAGHA_SOLUTION"

# Create icon using Python (if PIL/Pillow is available) or use system icon
python3 << 'ICON_SCRIPT'
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

app_path = Path.home() / "Desktop" / "ANAGHA SOLUTION.app" / "Contents" / "Resources"
app_path.mkdir(parents=True, exist_ok=True)

if HAS_PIL:
    # Create a beautiful icon
    size = 512
    img = Image.new('RGB', (size, size), color='#2C3E50')
    draw = ImageDraw.Draw(img)
    
    # Draw background gradient effect
    for i in range(size):
        color_val = int(44 + (i / size) * 20)  # Gradient from dark to slightly lighter
        draw.rectangle([(0, i), (size, i+1)], fill=(color_val, color_val+10, color_val+20))
    
    # Draw email icon representation
    # Draw envelope
    envelope_color = '#3498DB'
    margin = 80
    draw.rectangle([margin, margin, size-margin, size-margin], outline=envelope_color, width=15)
    draw.polygon([(margin, margin), (size//2, size//2-20), (size-margin, margin)], fill=envelope_color)
    
    # Draw text "AS" for ANAGHA SOLUTION
    try:
        # Try to use a system font
        font_size = 180
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except:
        try:
            font = ImageFont.truetype("/Library/Fonts/Arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
    
    text = "AS"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_x = (size - text_width) // 2
    text_y = (size - text_height) // 2 - 20
    draw.text((text_x, text_y), text, fill='white', font=font)
    
    # Save as PNG
    icon_path = app_path / "appicon.png"
    img.save(icon_path, "PNG")
    
    # Convert to .icns using sips (macOS built-in)
    icns_path = app_path / "appicon.icns"
    os.system(f'sips -s format icns "{icon_path}" --out "{icns_path}" 2>/dev/null')
    
    print("✓ Created custom icon with PIL")
else:
    # Fallback: Use system icon or create simple icon
    # Copy a system icon as fallback
    system_icon = "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericApplicationIcon.icns"
    if os.path.exists(system_icon):
        import shutil
        shutil.copy(system_icon, app_path / "appicon.icns")
        print("✓ Using system icon as fallback")
    else:
        # Create a simple text file that macOS can use
        print("⚠ Could not create custom icon. Using default.")
        # Create empty icns file - macOS will use default
        (app_path / "appicon.icns").touch()

ICON_SCRIPT

# Update Info.plist to point to the correct icon file
if [ -f "$APP_PATH/Contents/Resources/appicon.icns" ]; then
    echo "✓ Icon file created"
else
    # Try alternative: create icon using sips from a colored square
    python3 << 'ALT_ICON'
from PIL import Image
import os
app_path = os.path.join(os.path.expanduser("~"), "Desktop", "ANAGHA SOLUTION.app", "Contents", "Resources")
os.makedirs(app_path, exist_ok=True)

# Create simple colored icon
img = Image.new('RGB', (512, 512), color='#3498DB')
img.save(os.path.join(app_path, "appicon.png"), "PNG")
os.system(f'sips -s format icns "{os.path.join(app_path, "appicon.png")}" --out "{os.path.join(app_path, "appicon.icns")}" 2>/dev/null')
print("✓ Created simple icon")
ALT_ICON
fi

# Set icon using fileicon (if available) or use Rez/DeRez
if command -v fileicon &> /dev/null; then
    fileicon set "$APP_PATH" "$APP_PATH/Contents/Resources/appicon.icns" 2>/dev/null
elif [ -f "$APP_PATH/Contents/Resources/appicon.icns" ]; then
    # Use Python to set icon
    python3 << 'SETICON'
import subprocess
import os
app_path = os.path.expanduser("~/Desktop/ANAGHA SOLUTION.app")
icon_path = os.path.join(app_path, "Contents/Resources/appicon.icns")

if os.path.exists(icon_path):
    # Try to set icon using osascript and sips
    try:
        subprocess.run(['sips', '-i', icon_path], check=False, capture_output=True)
        print("✓ Icon set using sips")
    except:
        print("⚠ Could not set icon automatically. You may need to set it manually.")
SETICON
fi

echo ""
echo "✅ Beautiful .app bundle created at: $APP_PATH"
echo ""
echo "The app is now on your Desktop with a custom icon!"
echo "Double-click 'ANAGHA SOLUTION.app' to launch the software."
echo ""

