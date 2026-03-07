import os
import sys
import logging

logger = logging.getLogger(__name__)

ADDON_DIR = os.path.dirname(__file__)

VENV_NAME = ".venv"
VENV_DIR = os.path.normpath(os.path.join(ADDON_DIR, VENV_NAME))
VENV_SITE_PACKAGES = os.path.normpath(os.path.join(VENV_DIR, "Lib/site-packages"))

if sys.platform == "win32":
    VENV_PYTHON = os.path.join(VENV_DIR, "Scripts", "python.exe")
else:
    VENV_PYTHON = os.path.join(VENV_DIR, "bin", "python")


def inject_venv_into_path():
    """Inject the venv's site-packages into sys.path if it exists"""

    # Only inject if the venv actually exists (Development Mode)
    if os.path.exists(VENV_SITE_PACKAGES):
        if VENV_SITE_PACKAGES not in sys.path:
            sys.path.append(VENV_SITE_PACKAGES)
            logger.info(f"Added venv to sys.path: {VENV_SITE_PACKAGES}")

def get_python_executable():
    """Returns the path to the correct Python executable. Uses the venv's Python if it exists, otherwise falls back to sys.executable."""

    if os.path.exists(VENV_PYTHON):
        return VENV_PYTHON
    else:
        return sys.executable

def setup_logging():
    """Configures logging for the addon."""

    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)]
    )
