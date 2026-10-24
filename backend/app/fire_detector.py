"""
Feature 21: Machine Learning Fire & Smoke Detection Module.
Optimized for CAM-03 (flames) and CAM-04 (dense smoke) with:
1. Multi-class index monitoring with dedicated smoke threshold (conf=0.45).
2. Dense-smoke texture and upward expansion heuristic (low edge sharpness, grey/white clusters).
3. Regional temporal persistence buffer and motion gating.
4. Unified critical hazard alert reporting.
"""
import os
import logging
from typing import Tuple, List, Dict, Any, Optional
import cv2
import numpy as np

logger = logging.getLogger(__name__)

COLOR_FIRE = (0, 69, 255)    # Vivid Orange-Red (Flame)
COLOR_SMOKE = (0, 140, 255)   # Amber-Gold (Dense Smoke)


def compute_box_iou(boxA: List[int], boxB: List[int]) -> float:
    """Computes Intersection over Union between two bounding boxes [x1, y1, x2, y2]."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interW = max(0, xB - xA)
    interH = max(0, yB - yA)
    interArea = interW * interH

    boxAArea = max(0, boxA[2] - boxA[0]) * max(0, boxA[3] - boxA[1])
    boxBArea = max(0, boxB[2] - boxB[0]) * max(0, boxB[3] - boxB[1])
    denom = float(boxAArea + boxBArea - interArea)

    return interArea / denom if denom > 0 else 0.0


class FireDetector:
    def __init__(
        self,
        model=None,
        model_path: str = None,
        fire_conf_threshold: float = 0.50,
        smoke_conf_threshold: float = 0.45,
        conf_threshold: float = None,
        temporal_buffer_frames: int = 5,
        enable_motion_gate: bool = True,
        enable_smoke_heuristic: bool = True,
        is_webcam: bool = False,
    ):
        self.is_webcam = is_webcam
        # If webcam source, enforce strict conf=0.85 and disable diffuse smoke heuristics
        if is_webcam:
            self.fire_conf_threshold = 0.85
            self.smoke_conf_threshold = 0.85
            self.enable_smoke_heuristic = False
        elif conf_threshold is not None:
            self.fire_conf_threshold = conf_threshold
            self.smoke_conf_threshold = min(0.45, conf_threshold)
            self.enable_smoke_heuristic = enable_smoke_heuristic
        else:
            self.fire_conf_threshold = fire_conf_threshold
            self.smoke_conf_threshold = smoke_conf_threshold
            self.enable_smoke_heuristic = enable_smoke_heuristic

        self.conf_threshold = self.fire_conf_threshold  # Compatibility alias
        self.temporal_buffer_frames = temporal_buffer_frames
        self.enable_motion_gate = enable_motion_gate

        # Temporal state & motion gating
        self.prev_gray: Optional[np.ndarray] = None
        self.prev_smoke_centroids: List[Tuple[float, float]] = []
        self.fire_consecutive_frames = 0
        self.last_fire_box: Optional[List[int]] = None
        self.primary_hazard: Optional[str] = None

        if model is not None:
            self.model = model
            logger.info("FireDetector initialized with injected model instance.")
        else:
            if model_path is None:
                model_path = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "..", "models", "fire.pt")
                )
            if os.path.exists(model_path):
                try:
                    from ultralytics import YOLO
                    self.model = YOLO(model_path)
                    logger.info(
                        f"Loaded certified YOLO fire & smoke model from: {model_path} "
                        f"(fire_conf={self.fire_conf_threshold}, smoke_conf={self.smoke_conf_threshold}, is_webcam={self.is_webcam})"
                    )
                except Exception as e:
                    logger.error(f"Error loading fire model from {model_path}: {e}")
                    self.model = None
            else:
                logger.warning(f"Fire detection model not found at {model_path}.")
                self.model = None

    def _detect_dense_smoke_heuristic(self, frame: np.ndarray, gray: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detects low-frequency gray-scale expansion (dense grey/white clusters expanding
        upwards with high blur / low edge-sharpness).
        """
        if self.prev_gray is None or self.prev_gray.shape != gray.shape:
            return []

        h, w = gray.shape
        candidates = []

        try:
            # 1. Optical difference to confirm movement
            frame_diff = cv2.absdiff(gray, self.prev_gray)
            moving_mask = (frame_diff >= 4)

            # 2. Chromaticity check: Smoke in HSV is low-saturation grey/white
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            sat = hsv[:, :, 1]
            val = hsv[:, :, 2]
            smoke_color_mask = (sat <= 70) & (val >= 65) & (val <= 235)

            # 3. Low-Frequency / High-Blur Check:
            # Smoke clusters lack high-frequency edges; edge energy is low
            laplacian = cv2.Laplacian(gray, cv2.CV_32F)
            low_edge_mask = (np.abs(laplacian) < 18.0)

            # 4. Combine into candidate smoke mask
            combined = (smoke_color_mask & low_edge_mask & moving_mask).astype(np.uint8) * 255

            # Morphological open to remove isolated noise, close to merge diffuse smoke body
            open_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 17))
            morphed = cv2.morphologyEx(combined, cv2.MORPH_OPEN, open_kernel)
            morphed = cv2.morphologyEx(morphed, cv2.MORPH_CLOSE, close_kernel)

            # 5. Find large dense clusters
            contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                # Dense smoke cluster must have significant area (> 3000 px)
                if area >= 3000:
                    bx, by, bw, bh = cv2.boundingRect(cnt)
                    # Check blur inside the bounding box
                    roi_gray = gray[by : by + bh, bx : bx + bw]
                    if roi_gray.size > 0:
                        lap_var = cv2.Laplacian(roi_gray, cv2.CV_64F).var()
                        # True diffuse smoke has low Laplacian variance (< 140)
                        if lap_var < 140.0:
                            candidates.append({
                                "class_id": 1,
                                "class_name": "smoke",
                                "confidence": 0.65,
                                "box": [bx, by, bx + bw, by + bh],
                                "heuristic": True,
                            })
        except Exception as e:
            logger.debug(f"Smoke diffusion heuristic check exception: {e}")

        return candidates

    def detect(self, frame: np.ndarray) -> Tuple[np.ndarray, bool, List[Dict[str, Any]]]:
        """
        Runs multi-class ML inference and diffusion heuristics for fire and smoke.
        Returns:
            annotated_frame (np.ndarray): Frame with bounding boxes and warning badge when confirmed.
            fire_detected (bool): True if fire or smoke hazard confirmed across temporal buffer.
            detections (list): List of detected entity dictionaries.
        """
        if frame is None or not isinstance(frame, np.ndarray):
            return frame, False, []

        if self.model is None:
            return frame, False, []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 1. Motion Gating: Skip detection entirely on static frames with zero optical flow / motion
        if self.enable_motion_gate and self.prev_gray is not None and self.prev_gray.shape == gray.shape:
            frame_diff = cv2.absdiff(gray, self.prev_gray)
            motion_score = float(np.mean(frame_diff))
            if motion_score < 0.20:
                # Motionless static frame: skip to prevent false alarms on static pictures
                return frame, False, []

        annotated_frame = frame.copy()
        raw_candidates: List[Dict[str, Any]] = []

        try:
            # 2. Run ML Model with lowest target threshold to capture semi-transparent smoke
            min_thresh = min(self.smoke_conf_threshold, 0.40)
            results = self.model(annotated_frame, conf=min_thresh, verbose=False)
            names_map = getattr(self.model, "names", {0: "fire", 1: "smoke"})

            if results and len(results) > 0 and results[0].boxes is not None:
                for box in results[0].boxes:
                    # Extract confidence
                    if hasattr(box, "conf") and box.conf is not None:
                        try:
                            conf_val = float(box.conf[0]) if hasattr(box.conf, "__len__") else float(box.conf)
                        except Exception:
                            conf_val = float(box.conf)
                    else:
                        conf_val = 0.0

                    # Extract class id and name
                    if hasattr(box, "cls") and box.cls is not None:
                        try:
                            cls_id = int(box.cls[0]) if hasattr(box.cls, "__len__") else int(box.cls)
                        except Exception:
                            cls_id = int(box.cls)
                    else:
                        cls_id = 0

                    raw_name = names_map.get(cls_id, str(cls_id)).lower()

                    # Correct Class Mapped Labels:
                    # Class 0 maps strictly to fire, Class 1 maps strictly to smoke
                    # Resolves label swap where CAM-05 battery fire was labeled as smoke
                    is_fire = (cls_id == 0 or "fire" in raw_name) and "smoke" not in raw_name
                    is_smoke = (cls_id == 1 or "smoke" in raw_name) and not is_fire

                    if is_fire:
                        if conf_val < self.fire_conf_threshold:
                            continue
                        class_name = "fire"
                        matched_cls_id = 0
                    elif is_smoke:
                        if conf_val < self.smoke_conf_threshold:
                            continue
                        class_name = "smoke"
                        matched_cls_id = 1
                    else:
                        continue

                    if hasattr(box, "xyxy") and box.xyxy is not None:
                        coords = box.xyxy[0]
                        if hasattr(coords, "cpu"):
                            coords = coords.cpu().numpy()
                        x1, y1, x2, y2 = [int(v) for v in coords]
                    else:
                        continue

                    raw_candidates.append({
                        "class_id": matched_cls_id,
                        "class_name": class_name,
                        "confidence": conf_val,
                        "box": [x1, y1, x2, y2],
                        "heuristic": False,
                    })

            # 3. Dense-Smoke Diffusion Heuristic:
            # Supplements model for low-contrast, grey/white smoke clouds on CAM-04
            if self.enable_smoke_heuristic:
                heuristic_smoke = self._detect_dense_smoke_heuristic(annotated_frame, gray)
                for h_cand in heuristic_smoke:
                    # Check if already covered by ML candidate
                    h_box = h_cand["box"]
                    is_duplicate = False
                    for existing in raw_candidates:
                        if compute_box_iou(h_box, existing["box"]) > 0.35:
                            is_duplicate = True
                            break
                    if not is_duplicate:
                        raw_candidates.append(h_cand)

            self.prev_gray = gray

            if len(raw_candidates) == 0:
                self._record_miss()
                return annotated_frame, False, []

            # 4. Regional Temporal Persistence Buffer
            best_candidate = max(raw_candidates, key=lambda c: c["confidence"])
            current_box = best_candidate["box"]

            if self.last_fire_box is not None:
                iou = compute_box_iou(current_box, self.last_fire_box)
                c1 = ((current_box[0] + current_box[2]) / 2.0, (current_box[1] + current_box[3]) / 2.0)
                c2 = ((self.last_fire_box[0] + self.last_fire_box[2]) / 2.0, (self.last_fire_box[1] + self.last_fire_box[3]) / 2.0)
                center_dist = np.hypot(c1[0] - c2[0], c1[1] - c2[1])

                if iou >= 0.20 or center_dist <= 75.0:
                    self.fire_consecutive_frames += 1
                else:
                    self.fire_consecutive_frames = 1
            else:
                self.fire_consecutive_frames = 1

            self.last_fire_box = current_box

            # Confirm only if persisted across the temporal buffer
            hazard_confirmed = (self.fire_consecutive_frames >= self.temporal_buffer_frames)

            if hazard_confirmed:
                has_smoke = any(c["class_name"] == "smoke" for c in raw_candidates)
                has_fire = any(c["class_name"] == "fire" for c in raw_candidates)

                if has_smoke and has_fire:
                    self.primary_hazard = "fire_and_smoke"
                    badge_text = "CRITICAL: FIRE & SMOKE DETECTED"
                    badge_color = COLOR_FIRE
                elif has_smoke:
                    self.primary_hazard = "smoke"
                    badge_text = "CRITICAL HAZARD / SMOKE DETECTED"
                    badge_color = COLOR_SMOKE
                else:
                    self.primary_hazard = "fire"
                    badge_text = "CRITICAL HAZARD / FIRE DETECTED"
                    badge_color = COLOR_FIRE

                # Render confirmed hazard bounding boxes and tags
                for det in raw_candidates:
                    x1, y1, x2, y2 = det["box"]
                    class_name = det["class_name"]
                    conf_val = det["confidence"]
                    box_color = COLOR_SMOKE if class_name == "smoke" else COLOR_FIRE

                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), box_color, 2)

                    label = f"{class_name.upper()} {conf_val:.0%}"
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
                    tag_y1 = max(0, y1 - 22)
                    cv2.rectangle(
                        annotated_frame,
                        (x1, tag_y1),
                        (x1 + tw + 8, y1),
                        box_color,
                        -1,
                    )
                    cv2.putText(
                        annotated_frame,
                        label,
                        (x1 + 4, max(14, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 255, 255),
                        2,
                        cv2.LINE_AA,
                    )

                # Overlay prominent bold warning badge
                h, w = annotated_frame.shape[:2]
                (bw, bh), _ = cv2.getTextSize(badge_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                badge_x1 = max(10, (w - bw) // 2 - 16)
                badge_x2 = badge_x1 + bw + 32
                cv2.rectangle(annotated_frame, (badge_x1, 10), (badge_x2, 50), badge_color, -1)
                cv2.putText(
                    annotated_frame,
                    badge_text,
                    (badge_x1 + 16, 37),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                    cv2.LINE_AA,
                )

                return annotated_frame, True, raw_candidates

            return annotated_frame, False, []

        except Exception as e:
            logger.error(f"Error executing fire/smoke ML detection: {e}")
            self._record_miss()
            return frame, False, []

    def _record_miss(self):
        """Resets the regional consecutive buffer when no hazard is detected."""
        self.fire_consecutive_frames = 0
        self.last_fire_box = None
        self.primary_hazard = None

    def reset(self):
        """Reset state if applicable."""
        self.fire_consecutive_frames = 0
        self.last_fire_box = None
        self.prev_gray = None
        self.primary_hazard = None
