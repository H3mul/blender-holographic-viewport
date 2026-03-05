import bpy
import importlib
import sys

# Define submodules for reloading
submodule_names = [
]

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
    pass

def unregister():
    # Unregister in reverse order to avoid dependency issues
    pass

if __name__ == "__main__":
    register()
