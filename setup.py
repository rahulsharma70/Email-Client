"""
Setup script for ANAGHA SOLUTION
Creates executable with embedded Python and dependencies
"""

import os
import sys
import subprocess

def install_dependencies():
    """Install required dependencies"""
    print("Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("Dependencies installed successfully!")

def create_executable():
    """Create executable using PyInstaller"""
    try:
        # Install PyInstaller if not already installed
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        
        print("Creating executable...")
        subprocess.check_call([
            sys.executable, "-m", "PyInstaller",
            "main.py",
            "--name=ANAGHA_SOLUTION",
            "--onefile",
            "--windowed",
            "--hidden-import=tkinter",
            "--hidden-import=pandas",
            "--hidden-import=openpyxl",
            "--hidden-import=email",
            "--hidden-import=smtplib",
            "--collect-all=pandas",
            "--collect-all=openpyxl",
        ])
        print("Executable created successfully in dist/ folder!")
    except Exception as e:
        print(f"Error creating executable: {e}")
        print("You can still run the application using: python main.py")

if __name__ == "__main__":
    print("ANAGHA SOLUTION - Setup")
    print("=" * 50)
    
    choice = input("Choose option:\n1. Install dependencies only\n2. Create executable\n3. Both\nEnter choice (1/2/3): ")
    
    if choice in ['1', '3']:
        install_dependencies()
    
    if choice in ['2', '3']:
        create_executable()
    
    print("\nSetup complete!")

