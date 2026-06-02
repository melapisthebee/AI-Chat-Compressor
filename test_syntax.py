#!/usr/bin/env python3
"""Quick syntax and import validation script"""

print("Testing module imports...")

try:
    from engine.compression import CompressionEngine
    print("✓ compression.py imported successfully")
except Exception as e:
    print(f"✗ Failed to import compression.py: {e}")
    raise

try:
    from engine.parser import parse_lm_studio_file, get_parser_for_file
    print("✓ parser module imported successfully")
except Exception as e:
    print(f"✗ Failed to import parser module: {e}")
    raise

try:
    from gui.main_window import MainWindow
    print("✓ main_window.py imported successfully")
except Exception as e:
    print(f"✗ Failed to import main_window.py: {e}")
    raise

print("\n✅ All modules imported successfully!")
print("The compressor should launch without syntax errors.")
