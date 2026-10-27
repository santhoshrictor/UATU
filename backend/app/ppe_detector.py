"""
Feature: Personal Protective Equipment (PPE) Detection Module.
Detects hard hats, safety vests, masks, and compliance violations:
- Classes: hardhat, safety_vest, mask, no_hardhat, no_vest, no_mask.
- Visual overlays with color-coded compliance status.
- Integration with SpatialTracker and alert manager for real-time compliance tracking.
"""
import os
import logging
from typing import Tuple, List, Dict, Any, Optional
import cv2
import numpy as np

logger = logging.getLogger(__name__)

COLOR_COMPLIANT = (0, 220, 100)      # Vivid Green
COLOR_VIOLATION = (0, 69, 255)       # Bright Orange-Red (Missing PPE)
COLOR_WARNING = (0, 165, 255)         # Amber
COLOR_EQUIPMENT = (255, 191, 0)       # Cyan/Deep Sky Blue

# Standard normalization dictionary
CLASS_MAP = {
    0: ("hardhat", True, "Hardhat"),
    1: ("mask", True, "Mask"),
    2: ("no_hardhat", False, "Missing Hardhat"),
    3: ("no_mask", False, "Missing Mask"),
    4: ("no_vest", False, "Missing Safety Vest"),
    5: ("person", True, "Person"),
    6: ("safety_cone", True, "Safety Cone"),
    7: ("safety_vest", True, "Safety Vest"),
    8: ("machinery", True, "Machinery"),
    9: ("vehicle", True, "Vehicle"),
}


class PPEDetector:
    def __init__(
        self,
        model=None,
        model_path: Optional[str] = None,
        conf_threshold: float = 0.30,
        temporal_buffer_frames: int = 3,
        **kwargs,
    ):
        self.conf_threshold = conf_threshold
        self.temporal_buffer_frames = temporal_buffer_frames
        self.violation_consecutive_frames = 0
        self.last_violation_detail: Optional[str] = None

        if model is not None:
            self.model = model
            logger.info("PPEDetector initialized with injected model instance.")
        else:
            if model_path is None:
                # Prefer yolov8n-ppe.pt, then ppe.pt in backend/models
                base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))
                p1 = os.path.join(base_dir, "yolov8n-ppe.pt")
                p2 = os.path.join(base_dir, "ppe.pt")
                model_path = p1 if os.path.exists(p1) else p2

            if os.path.exists(model_path):
                try:
                    from ultralytics import YOLO
                    self.model = YOLO(model_path)
                    logger.info(f"Loaded certified YOLO PPE model from: {model_path} (conf={self.conf_threshold})")
                except Exception as e:
                    logger.error(f"Error loading PPE model from {model_path}: {e}")
                    self.model = None
            else:
                logger.warning(f"PPE detection model not found at {model_path}.")
                self.model = None

    def detect(
        self,
        frame: np.ndarray,
        person_boxes: Optional[List[List[int]]] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any], List[Dict[str, Any]]]:
        """
        Runs PPE detection on the input frame.
        Returns:
            annotated_frame (np.ndarray): Frame with bounding boxes & compliance badges.
            summary (dict): Compliance statistics (rates, violation counts, active tags).
            detections (list): Detailed list of detected PPE entities.
        """
        default_summary = {
            "total_detected": 0,
            "compliant_count": 0,
            "violation_count": 0,
            "compliance_rate": 100.0,
            "has_violation": False,
            "violations": [],
            "items": [],
        }

        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return frame, default_summary, []

        if self.model is None:
            return frame, default_summary, []

        annotated_frame = frame.copy()
        raw_detections: List[Dict[str, Any]] = []

        try:
            results = self.model(annotated_frame, conf=self.conf_threshold, verbose=False)
            names_map = getattr(self.model, "names", {})

            if results and len(results) > 0 and results[0].boxes is not None:
                for box in results[0].boxes:
                    # Confidence
                    try:
                        conf_val = float(box.conf[0]) if hasattr(box.conf, "__len__") else float(box.conf)
                    except Exception:
                        conf_val = 0.0

                    if conf_val < self.conf_threshold:
                        continue

                    # Class ID
                    try:
                        cls_id = int(box.cls[0]) if hasattr(box.cls, "__len__") else int(box.cls)
                    except Exception:
                        cls_id = 0

                    raw_name = names_map.get(cls_id, str(cls_id)).lower()

                    # Coordinate bounding box [x1, y1, x2, y2]
                    if hasattr(box, "xyxy") and box.xyxy is not None:
                        coords = box.xyxy[0]
                        if hasattr(coords, "cpu"):
                            coords = coords.cpu().numpy()
                        x1, y1, x2, y2 = [int(v) for v in coords]
                    else:
                        continue

                    # Normalized mapping
                    normalized_class, is_compliant, display_label = self._map_class(cls_id, raw_name)

                    # Filter out non-PPE general items like person/vehicle unless useful
                    if normalized_class in ["person", "machinery", "vehicle", "safety_cone"]:
                        continue

                    raw_detections.append({
                        "class_id": cls_id,
                        "class_name": normalized_class,
                        "display_name": display_label,
                        "is_compliant": is_compliant,
                        "confidence": conf_val,
                        "box": [x1, y1, x2, y2],
                    })

        except Exception as e:
            logger.error(f"Error during PPE ML inference: {e}")
            return frame, default_summary, []

        # Analyze summary
        compliant_items = [d for d in raw_detections if d["is_compliant"]]
        violation_items = [d for d in raw_detections if not d["is_compliant"]]

        violation_tags = list(set([d["display_name"] for d in violation_items]))
        total_eval = len(compliant_items) + len(violation_items)

        compliance_rate = 100.0
        if total_eval > 0:
            compliance_rate = round((len(compliant_items) / float(total_eval)) * 100.0, 1)

        has_violation = len(violation_items) > 0

        # Temporal persistence for violations to prevent single-frame flickering
        if has_violation:
            self.violation_consecutive_frames += 1
            self.last_violation_detail = ", ".join(violation_tags)
        else:
            self.violation_consecutive_frames = max(0, self.violation_consecutive_frames - 1)
            if self.violation_consecutive_frames == 0:
                self.last_violation_detail = None

        confirmed_violation = self.violation_consecutive_frames >= self.temporal_buffer_frames

        summary = {
            "total_detected": len(raw_detections),
            "compliant_count": len(compliant_items),
            "violation_count": len(violation_items),
            "compliance_rate": compliance_rate,
            "has_violation": confirmed_violation or (has_violation and self.temporal_buffer_frames <= 1),
            "violations": violation_tags,
            "items": raw_detections,
        }

        # Annotate visual bounding boxes
        for det in raw_detections:
            x1, y1, x2, y2 = det["box"]
            is_comp = det["is_compliant"]
            label_text = f"{det['display_name'].upper()} {det['confidence']:.0%}"
            box_color = COLOR_COMPLIANT if is_comp else COLOR_VIOLATION

            # Box outline
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 2)

            # Label tag header
            (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            tag_y1 = max(0, y1 - 18)
            cv2.rectangle(annotated_frame, (x1, tag_y1), (x1 + tw + 6, y1), box_color, -1)
            cv2.putText(
                annotated_frame,
                label_text,
                (x1 + 3, max(12, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        # Top corner telemetry badge for PPE status
        if total_eval > 0:
            h, w = annotated_frame.shape[:2]
            badge_str = f"PPE COMPLIANCE: {compliance_rate:.0f}%"
            badge_col = COLOR_COMPLIANT if compliance_rate >= 80.0 else COLOR_VIOLATION
            if has_violation:
                badge_str = f"PPE VIOLATION: {', '.join(violation_tags).upper()}"
                badge_col = COLOR_VIOLATION

            (bw, bh), _ = cv2.getTextSize(badge_str, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            bx1 = w - bw - 24
            by1 = 12
            cv2.rectangle(annotated_frame, (bx1, by1), (w - 10, by1 + bh + 14), (10, 15, 25), -1)
            cv2.rectangle(annotated_frame, (bx1, by1), (w - 10, by1 + bh + 14), badge_col, 1)
            cv2.putText(
                annotated_frame,
                badge_str,
                (bx1 + 8, by1 + bh + 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                badge_col,
                2,
                cv2.LINE_AA,
            )

        return annotated_frame, summary, raw_detections

    def _map_class(self, cls_id: int, raw_name: str) -> Tuple[str, bool, str]:
        """Normalize class index/name into standard category, compliance boolean, and label."""
        if cls_id in CLASS_MAP:
            return CLASS_MAP[cls_id]

        raw = raw_name.lower().replace("-", "_").replace(" ", "_")
        if "no_hardhat" in raw or "no_helmet" in raw:
            return ("no_hardhat", False, "Missing Hardhat")
        elif "no_vest" in raw:
            return ("no_vest", False, "Missing Safety Vest")
        elif "no_mask" in raw:
            return ("no_mask", False, "Missing Mask")
        elif "hardhat" in raw or "helmet" in raw:
            return ("hardhat", True, "Hardhat")
        elif "vest" in raw:
            return ("safety_vest", True, "Safety Vest")
        elif "mask" in raw:
            return ("mask", True, "Mask")
        else:
            return (raw, True, raw.capitalize())
