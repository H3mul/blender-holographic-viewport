import argparse
import json
import logging
import os
import socket
import sys
import time

import cv2
import mediapipe as mp
from cv2_enumerate_cameras import enumerate_cameras
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

logger = logging.getLogger(__name__)

# Configure logging
def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)]
    )

def list_video_devices():
    """Lists available video devices using cv2_enumerate_cameras."""

    logger.info("\nAvailable Video Devices:")
    logger.info("-" * 50)
    devices = enumerate_cameras()
    for device in devices:
        logger.info(f"Index: {device.index}")
        logger.info(f"  Name: {device.name}")
        logger.info(f"  Path: {device.path}")
        logger.info(f"  Backend: {device.backend}")
        logger.info("-" * 50)

def main():
    # Calculate default model path relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_model_path = os.path.join(script_dir, "face_landmarker.task")

    parser = argparse.ArgumentParser(description="Holographic Viewport Facetracking Reporter")
    parser.add_argument(
        "--video-device",
        type=int,
        default=-1,
        help="Index of the video device (webcam) to use (selects the first available device by default)",
    )
    parser.add_argument("--list-video-devices", action="store_true", help="List all available video devices and exit")
    parser.add_argument("--debug-viewer", action="store_true", help="Display a debug window with the processed image")
    parser.add_argument(
        "--model-path",
        type=str,
        default=default_model_path,
        help=f"Path to the MediaPipe face landmarker model file (default: {default_model_path})",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug-level logging")
    parser.add_argument(
        "--address", type=str, default="127.0.0.1", help="Target IP address for UDP tracking data (default: 127.0.0.1)"
    )
    parser.add_argument("--port", type=int, default=5005, help="Target UDP port for tracking data (default: 5005)")
    parser.add_argument(
        "--interval",
        type=int,
        default=-1,
        help="Interval for capturing frames in milliseconds (default: -1, as fast as possible)",
    )
    parser.add_argument("--max-faces", type=int, default=3, help="Maximum number of faces to track (default: 3)")
    args = parser.parse_args()

    # Setup logging based on verbose flag
    setup_logging(args.verbose)

    # Handle device listing
    if args.list_video_devices:
        list_video_devices()
        return

    # Initialize UDP Socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Initialize MediaPipe Tasks Face Landmarker
    try:
        if not os.path.exists(args.model_path):
            raise FileNotFoundError(f"Model file not found at: {args.model_path}")

        base_options = python.BaseOptions(model_asset_path=args.model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=args.max_faces,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        landmarker = vision.FaceLandmarker.create_from_options(options)
    except Exception as e:
        logger.error(f"Failed to initialize Face Landmarker: {e}")
        logger.error(
            "Ensure you have downloaded 'face_landmarker.task' and placed it in the same directory as this script."
        )
        return

    if args.video_device == -1:
        logger.debug("No video device specified. Selecting the first available device.")
        cameras = enumerate_cameras()
        args.video_device = cameras[0].index if cameras else 0

    logger.info(f"Starting facetracking reporter. Sending data to: {args.address}:{args.port}")
    logger.info(f"Using Video Device: {args.video_device}")
    logger.info(f"Using Model: {args.model_path}")
    logger.info(f"Max faces to track: {args.max_faces}")
    if args.interval > 0:
        logger.info(f"Capture interval: {args.interval}ms")

    cap = cv2.VideoCapture(args.video_device)

    if not cap.isOpened():
        logger.error(f"Could not open webcam with index {args.video_device}.")
        return

    last_capture_time = 0

    try:
        while cap.isOpened():
            current_time = time.time()
            elapsed_ms = (current_time - last_capture_time) * 1000

            if args.interval > 0 and elapsed_ms < args.interval:
                # Wait for the remaining time or check for exit key
                wait_time = max(1, int(args.interval - elapsed_ms))
                if cv2.waitKey(wait_time) & 0xFF == 27:
                    logger.info("Exit signal received.")
                    break
                continue

            success, frame = cap.read()
            if not success:
                continue

            last_capture_time = current_time

            # MediaPipe Tasks expects RGB images
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # Calculate timestamp in ms for VIDEO mode
            timestamp_ms = int(current_time * 1000)

            # Perform inference
            results = landmarker.detect_for_video(mp_image, timestamp_ms)

            if results.face_landmarks:
                tracking_data = []

                for idx, face_landmarks in enumerate(results.face_landmarks):
                    # Landmark 168 is the bridge of the nose in the face mesh
                    nose_bridge = face_landmarks[168]

                    # Values are normalized [0.0, 1.0]
                    coords = [nose_bridge.x, nose_bridge.y, nose_bridge.z]
                    tracking_data.append(coords)

                    logger.debug(f"Face {idx}: x={nose_bridge.x:.4f}, y={nose_bridge.y:.4f}, z={nose_bridge.z:.4f}")

                    # Draw landmarks if debug viewer is active
                    if args.debug_viewer:
                        # Draw dots for landmarks
                        for lm in face_landmarks:
                            x = int(lm.x * frame.shape[1])
                            y = int(lm.y * frame.shape[0])
                            cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)
                        # Draw index at nose bridge
                        nx = int(nose_bridge.x * frame.shape[1])
                        ny = int(nose_bridge.y * frame.shape[0])
                        cv2.putText(frame, str(idx), (nx, ny), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

                # Send all detected faces to Blender as a list of lists
                message = json.dumps(tracking_data)
                sock.sendto(message.encode(), (args.address, args.port))
            else:
                logger.debug("No faces detected.")

            if args.debug_viewer:
                cv2.imshow("Face Tracking Debug View", frame)

            # Check for Esc key (27) to exit (if not handled by wait logic)
            if cv2.waitKey(1) & 0xFF == 27:
                logger.info("Exit signal received.")
                break
    finally:
        logger.info("Shutting down.")
        landmarker.close()
        cap.release()
        sock.close()
        if args.debug_viewer:
            cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
