"""
Build script to create executable with PyInstaller
Run: python build_exe.py
"""

import subprocess
import sys
import os

def build_executable():
    """Build executable using PyInstaller"""
    print("Building ANAGHA SOLUTION executable...")
    print("=" * 50)
    
    # Install PyInstaller if needed
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        'main.py',
        '--name=ANAGHA_SOLUTION',
        '--onefile',
        '--windowed',
        '--hidden-import=tkinter',
        '--hidden-import=pandas',
        '--hidden-import=openpyxl',
        '--hidden-import=email',
        '--hidden-import=smtplib',
        '--hidden-import=sqlite3',
        '--collect-all=pandas',
        '--collect-all=openpyxl',
        '--clean',
    ]
    
    # Add database file if it exists
    if os.path.exists('anagha_solution.db'):
        if sys.platform == 'win32':
            cmd.append('--add-data=anagha_solution.db;.')
        else:
            cmd.append('--add-data=anagha_solution.db:.')
    
    print("Running PyInstaller...")
    subprocess.check_call(cmd)
    
    print("\n" + "=" * 50)
    print("Build complete!")
    print("Executable location: dist/ANAGHA_SOLUTION.exe (Windows) or dist/ANAGHA_SOLUTION (Linux/Mac)")

if __name__ == "__main__":
    build_executable()

