"""
UATU Vision Engine (Feature 1: Person Detection & Feature 2: Vehicle Detection)
================================================================================
Executes spatial object detection utilizing YOLO11 with CUDA GPU acceleration,
identifying persons (COCO class 0) and vehicles (COCO classes 2, 3, 5, 7) in real time.
"""

import logging
from pathlib import Path
import sys
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("workplace_intelligence.vision_engine")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] workplace_intelligence (vision_engine.py): %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Resolve local models path
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "yolo11n.pt"

# Class ID mappings for COCO dataset
PERSON_CLASS_ID = 0
VEHICLE_CLASS_IDS = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

# Aesthetics styling: BGR Color tokens (Emerald green for persons, Cyan for vehicles)
COLOR_PERSON = (16, 185, 129)   # Emerald Green
COLOR_VEHICLE = (255, 200, 0)   # Vivid Cyan/Aqua (BGR)
COLOR_BG_LABEL = (15, 23, 42)   # Deep Slate `#0f172a`

# Global YOLO11 instance
yolo_spatial_model: Optional[Any] = None
device_name: str = "cpu"

try:
    from ultralytics import YOLO
    import torch

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Loading YOLO11 spatial model from: {MODEL_PATH}")
    yolo_spatial_model = YOLO(str(MODEL_PATH))

    if torch.cuda.is_available():
        device_name = "cuda:0"
        yolo_spatial_model.to(device_name)
        logger.info(f"YOLO11 spatial engine accelerated on CUDA GPU: {torch.cuda.get_device_name(0)}")
    else:
        device_name = "cpu"
        logger.info("CUDA not detected. YOLO11 running on CPU fallback.")
except Exception as e:
    logger.warning(f"Could not initialize YOLO11 spatial engine: {e}")


def process_spatial_frame(frame: np.ndarray) -> Tuple[np.ndarray, Dict[str, int]]:
    """
    Evaluates an OpenCV BGR frame for Persons and Vehicles.
    Draws minimalist bounding boxes and telemetry labels.

    Args:
        frame: OpenCV image array (BGR format).

    Returns:
        tuple of (annotated_frame, {"persons": person_count, "vehicles": vehicle_count})
    """
    if frame is None or not isinstance(frame, np.ndarray):
        return frame, {"persons": 0, "vehicles": 0}

    annotated = frame.copy()
    counts = {"persons": 0, "vehicles": 0}

    if yolo_spatial_model is None:
        return annotated, counts

    try:
        results = yolo_spatial_model(annotated, verbose=False)
        for res in results:
            if res.boxes is None or len(res.boxes) == 0:
                continue

            for box in res.boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())

                if conf < 0.35:
                    continue

                is_person = cls_id == PERSON_CLASS_ID
                is_vehicle = cls_id in VEHICLE_CLASS_IDS

                if not (is_person or is_vehicle):
                    continue

                if is_person:
                    counts["persons"] += 1
                    label_text = f"PERSON {conf:.2f}"
                    box_color = COLOR_PERSON
                else:
                    counts["vehicles"] += 1
                    vehicle_name = VEHICLE_CLASS_IDS[cls_id].upper()
                    label_text = f"{vehicle_name} {conf:.2f}"
                    box_color = COLOR_VEHICLE

                # Extract bounding coordinates
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                # Clamp to frame dimensions
                h, w = annotated.shape[:2]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w - 1, x2), min(h - 1, y2)

                # Draw minimalist thin bounding box
                cv2.rectangle(annotated, (x1, y1), (x2, y2), box_color, 2, cv2.LINE_AA)

                # Small label with background tag
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.42
                thickness = 1
                (tw, th), baseline = cv2.getTextSize(label_text, font, font_scale, thickness)

                # Label tag placement
                label_y1 = max(0, y1 - th - 6)
                label_y2 = y1
                label_x2 = min(w - 1, x1 + tw + 6)

                cv2.rectangle(
                    annotated,
                    (x1, label_y1),
                    (label_x2, label_y2),
                    box_color,
                    -1,
                )
                cv2.putText(
                    annotated,
                    label_text,
                    (x1 + 3, label_y2 - 3),
                    font,
                    font_scale,
                    COLOR_BG_LABEL,
                    thickness,
                    cv2.LINE_AA,
                )

    except Exception as e:
        logger.warning(f"Error during spatial detection: {e}")

    return annotated, counts
