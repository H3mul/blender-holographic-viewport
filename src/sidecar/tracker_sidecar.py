import cv2
from cv2_enumerate_cameras import enumerate_cameras

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import socket
import json
import logging
import sys
import argparse
import time
import os

# Configure logging
def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

logger = logging.getLogger(__name__)

# UDP Setup
UDP_IP = "127.0.0.1"
UDP_PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def list_video_devices():
    """Lists available video devices using cv2_enumerate_cameras."""

    print("\nAvailable Video Devices:")
    print("-" * 50)
    devices = enumerate_cameras()
    for device in devices:
        print(f"Index: {device.index}")
        print(f"  Name: {device.name}")
        print(f"  Path: {device.path}")
        print(f"  Backend: {device.backend}")
        print("-" * 50)

def main():
    # Calculate default model path relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_model_path = os.path.join(script_dir, "face_landmarker.task")

    parser = argparse.ArgumentParser(description="Holographic Viewport Tracker Sidecar")
    parser.add_argument(
        "--video-device",
        type=int,
        default=-1,
        help="Index of the video device (webcam) to use (selects the first available device by default)"
    )
    parser.add_argument(
        "--list-video-devices",
        action="store_true",
        help="List all available video devices and exit"
    )
    parser.add_argument(
        "--debug-viewer",
        action="store_true",
        help="Display a debug window with the processed image"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=default_model_path,
        help=f"Path to the MediaPipe face landmarker model file (default: {default_model_path})"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug-level logging"
    )
    args = parser.parse_args()

    # Setup logging based on verbose flag
    setup_logging(args.verbose)

    # Handle device listing
    if args.list_video_devices:
        list_video_devices()
        return

    # Initialize MediaPipe Tasks Face Landmarker
    try:
        if not os.path.exists(args.model_path):
            raise FileNotFoundError(f"Model file not found at: {args.model_path}")

        base_options = python.BaseOptions(model_asset_path=args.model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False
        )
        landmarker = vision.FaceLandmarker.create_from_options(options)
    except Exception as e:
        logger.error(f"Failed to initialize Face Landmarker: {e}")
        logger.error("Ensure you have downloaded 'face_landmarker.task' and placed it in the same directory as this script.")
        return

    if args.video_device == -1:
        logger.debug("No video device specified. Selecting the first available device.")
        args.video_device = enumerate_cameras()[0].index if enumerate_cameras() else 0

    logger.info(f"Starting tracker sidecar. Target: {UDP_IP}:{UDP_PORT}")
    logger.info(f"Using Video Device: {args.video_device}")
    logger.info(f"Using Model: {args.model_path}")

    cap = cv2.VideoCapture(args.video_device)

    if not cap.isOpened():
        logger.error(f"Could not open webcam with index {args.video_device}.")
        return

    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            continue

        # MediaPipe Tasks expects RGB images
        frame = cv2.flip(frame, 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # Calculate timestamp in ms for VIDEO mode
        timestamp_ms = int(time.time() * 1000)

        # Perform inference
        results = landmarker.detect_for_video(mp_image, timestamp_ms)

        if results.face_landmarks:
            # FaceLandmarker returns a list of lists of landmarks
            face_landmarks = results.face_landmarks[0]

            # Landmark 168 is the bridge of the nose in the face mesh
            nose_bridge = face_landmarks[168]

            # Pack as list: [x, y, z]
            # Values are normalized [0.0, 1.0]
            data = [nose_bridge.x, nose_bridge.y, nose_bridge.z]

            # Serialize and log
            message = json.dumps(data)
            logger.debug(f"Tracking: x={nose_bridge.x:.4f}, y={nose_bridge.y:.4f}, z={nose_bridge.z:.4f}")

            # Send to Blender
            sock.sendto(message.encode(), (UDP_IP, UDP_PORT))

            # Draw landmarks if debug viewer is active
            if args.debug_viewer:
                # Manual circle drawing for simple visualization
                for lm in face_landmarks:
                    x = int(lm.x * frame.shape[1])
                    y = int(lm.y * frame.shape[0])
                    cv2.circle(frame, (x, y), 1, (0, 255, 0), -1)
        else:
            logger.debug("No face detected.")

        if args.debug_viewer:
            cv2.imshow('Holographic Viewport Debug', frame)

        # Check for Esc key (27) to exit
        if cv2.waitKey(5) & 0xFF == 27:
            logger.info("Exit signal received.")
            break

    logger.info("Shutting down tracker sidecar.")
    landmarker.close()
    cap.release()
    if args.debug_viewer:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
