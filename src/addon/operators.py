import json
import os
import socket
import subprocess

import bpy


class HOLOGRAM_OT_Toggle(bpy.types.Operator):
    bl_idname = "hologram.toggle"
    bl_label = "Toggle Hologram View"

    _timer = None
    _process = None
    _sock = None

    def modal(self, context, event):
        props = context.scene.hologram_view_props

        if not props.is_active:
            return self.cancel(context)

        if event.type == "TIMER":
            try:
                # Non-blocking UDP receive
                data, _ = self._sock.recvfrom(1024)
                coords = json.loads(data.decode())  # [x, y, z] from nose bridge

                self.update_camera(context, coords)
            except (OSError, BlockingIOError):
                pass

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
        script_path = os.path.join(os.path.dirname(__file__), "..", "facetracking_reporter.py")
        self._process = subprocess.Popen([bpy.app.binary_path_python, script_path])

        # Socket setup
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("127.0.0.1", 5005))
        self._sock.setblocking(False)

        # UI State
        props.is_active = True

        # Start Modal
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)

        # Ensure we are in Camera View
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                area.spaces.active.region_3d.view_perspective = "CAMERA"

        return {"RUNNING_MODAL"}

    def cancel(self, context):
        if self._process:
            self._process.terminate()
        if self._sock:
            self._sock.close()
        context.window_manager.event_timer_remove(self._timer)
        return {"CANCELLED"}


classes = (HOLOGRAM_OT_Toggle,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
