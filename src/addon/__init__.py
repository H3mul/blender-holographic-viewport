import importlib
import os
import sys

import bpy

from . import operators, properties, ui

# Get the directory where this __init__.py is located
addon_dir = os.path.dirname(__file__)
venv_path = os.path.normpath(os.path.join(addon_dir, "../../.venv/Lib/site-packages"))

# Only inject if the venv actually exists (Development Mode)
if os.path.exists(venv_path):
    if venv_path not in sys.path:
        sys.path.append(venv_path)
        print(f"Holographic Viewport: Added venv to sys.path: {venv_path}")

# Define submodules for reloading
submodule_names = ["properties", "operators", "ui"]


def reload_modules():
    """Reloads submodules to support Blender's 'Reload Scripts' command."""
    for name in submodule_names:
        full_name = f"{__package__}.{name}"
        if full_name in sys.modules:
            importlib.reload(sys.modules[full_name])


# Perform reload before importing
if "bpy" in locals():
    reload_modules()


def register():
    # Register properties first as they are needed by UI/Operators
    properties.register()
    operators.register()
    ui.register()


def unregister():
    # Unregister in reverse order to avoid dependency issues
    ui.unregister()
    operators.unregister()
    properties.unregister()


if __name__ == "__main__":
    register()
