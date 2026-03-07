import importlib
import sys
import bpy

# Define submodules for reloading
submodule_names = ["properties", "operators", "ui", "utils"]

def reload_modules():
    """Reloads submodules to support Blender's 'Reload Scripts' command."""
    for name in submodule_names:
        full_name = f"{__package__}.{name}"
        if full_name in sys.modules:
            importlib.reload(sys.modules[full_name])

# Perform reload before importing
if "bpy" in locals():
    reload_modules()

from . import operators, properties, ui, utils

utils.setup_logging()
utils.inject_venv_into_path()

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
