import json
import logging
import os
import socket
import subprocess
import time

import bpy

from . import utils

logger = logging.getLogger(__name__)

class HOLOGRAM_OT_Toggle(bpy.types.Operator):
    bl_idname = "hologram.toggle"
    bl_label = "Toggle Hologram View"

    _timer = None
    _process = None
    _sock = None
    _is_booting = True
    _start_time = 0

    def modal(self, context, event):
        props = context.scene.hologram_view_props

        if not props.is_active:
            return self.cancel(context)

        if event.type == "TIMER":
            try:
                # Non-blocking UDP receive
                data, _ = self._sock.recvfrom(1024)

                # If we received data, we are no longer booting
                if self._is_booting:
                    self._is_booting = False
                    self.report({'INFO'}, f"Headtracking active (bootup took {time.time() - self._start_time:.1f}s)")

                coords = json.loads(data.decode())  # [x, y, z] from nose bridge

                # coords is now a list of lists [[x, y, z], ...] from facetracking_reporter.py
                # For Phase 1, we only use the first detected face
                if coords and len(coords) > 0:
                    self.update_camera(context, coords[0])
            except (OSError, BlockingIOError):
                # If we haven't received data yet and it's taking too long, let the user know
                if self._is_booting:
                    elapsed = time.time() - self._start_time
                    if int(elapsed * 10) % 20 == 0: # Report every 2 seconds
                        self.report({'INFO'}, f"Holographic View: Waiting for headtracking process boot... ({int(elapsed)}s)")
                pass
            except json.JSONDecodeError:
                logger.error("Failed to decode tracking data")

        return {"PASS_THROUGH"}

    def update_camera(self, context, coords):
        # Coordinates from MediaPipe are 0-1 (normalized)
        # Shift them to -0.5 to 0.5 for centering
        hx, hy, hz = (coords[0] - 0.5), (coords[1] - 0.5), coords[2]

        cam = context.scene.camera
        if not cam or cam.type != "CAMERA":
            return

        s = context.scene.hologram_view_props.smoothing

        # 1. Update Camera Position (Parallax)
        # Using simple multipliers for Phase 1
        target_x = hx * context.scene.hologram_view_props.sensitivity
        target_y = -hy * context.scene.hologram_view_props.sensitivity

        cam.location.x = (cam.location.x * s) + (target_x * (1 - s))
        cam.location.y = (cam.location.y * s) + (target_y * (1 - s))

        # 2. Off-Axis Shift (The "Magic")
        # Shift is inversely proportional to position to keep the screen frame fixed
        # Math: $$shift\_x = -X_{head} / (2 \cdot Z_{head} \cdot \tan(FOV_x / 2))$$
        cam.data.shift_x = -hx * 2.0
        cam.data.shift_y = hy * 2.0

    def execute(self, context):
        props = context.scene.hologram_view_props

        if props.is_active:
            # Shutdown
            props.is_active = False
            return {"FINISHED"}

        # Start sidecar process
        script_path = os.path.join(os.path.dirname(__file__), "sidecar", "facetracking_reporter.py")
        python_exe = utils.get_python_executable()

        if not python_exe:
            self.report({'ERROR'}, "Could not find a valid Python executable for the sidecar")
            return {'CANCELLED'}

        command = [python_exe, script_path]
        logger.debug(f"Starting sidecar process with command: {' '.join(command)}")

        try:
            # We use a try block to catch issues like missing scripts or executable permission errors
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            # Brief check to see if it crashed immediately
            time_to_wait = 0.5
            try:
                self._process.wait(timeout=time_to_wait)
                # If we reach here, the process exited early
                stdout, stderr = self._process.communicate()
                logger.error(f"Sidecar exited immediately with code {self._process.returncode}")
                logger.error(f"Stderr: {stderr}")
                self.report({'ERROR'}, "Headtracking process failed to start. Check logs.")
                return {'CANCELLED'}
            except subprocess.TimeoutExpired:
                # This is actually what we want - it means the process is still running
                pass

        except Exception as e:
            logger.error(f"Failed to launch sidecar process: {e}")
            self.report({'ERROR'}, "Headtracking process failed to start. Check logs.")
            return {'CANCELLED'}

        # Socket setup
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.bind(("127.0.0.1", 5005))
            self._sock.setblocking(False)
        except Exception as e:
            logger.error(f"Failed to setup UDP socket: {e}")
            if self._process:
                self._process.terminate()
            self.report({'ERROR'}, f"Headtracking socket setup failed: {str(e)}")
            return {'CANCELLED'}

        # UI State
        props.is_active = True
        self._is_booting = True
        self._start_time = time.time()

        # Start Modal
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)

        # Ensure we are in Camera View
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"

        self.report({'INFO'}, "Holographic View: Starting headtracking process...")
        return {"RUNNING_MODAL"}

    def cancel(self, context):
        if self._process:
            self.report({'INFO'}, "Terminating headtracking process...")
            self._process.terminate()
            self._process = None
        if self._sock:
            self._sock.close()
            self._sock = None
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

        context.scene.hologram_view_props.is_active = False
        return {"CANCELLED"}

classes = (HOLOGRAM_OT_Toggle,)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
