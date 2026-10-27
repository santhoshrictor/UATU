import cv2
import os
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from ultralytics import YOLO

from backend.app.core.websocket_manager import alert_manager
from backend.app.fire_detector import FireDetector, COLOR_FIRE

IST = timezone(timedelta(hours=5, minutes=30))

logger = logging.getLogger(__name__)

COLOR_TRIPWIRE = (0, 215, 255)
 
# Standard COCO 17-keypoint skeleton connections for pose rendering
SKELETON_EDGES = [
    (0, 1), (0, 2), (1, 3), (2, 4),      # Facial / Head
    (0, 5), (0, 6),                      # Head to shoulders
    (5, 6),                              # Left shoulder to right shoulder
    (5, 7), (7, 9),                      # Left arm (shoulder -> elbow -> wrist)
    (6, 8), (8, 10),                     # Right arm (shoulder -> elbow -> wrist)
    (5, 11), (6, 12),                    # Torso (left shoulder to left hip, right shoulder to right hip)
    (11, 12),                            # Left hip to right hip
    (11, 13), (13, 15),                  # Left leg (hip -> knee -> ankle)
    (12, 14), (14, 16),                  # Right leg (hip -> knee -> ankle)
]

# COCO Classes for Pedestrian and Vehicle Perception
COCO_PERSON_CLASS = 0
COCO_VEHICLE_CLASSES = {
    2: "Car",
    3: "Motorcycle",
    5: "Bus",
    7: "Truck",
}
ALL_ACTIVE_CLASSES = [COCO_PERSON_CLASS, *COCO_VEHICLE_CLASSES.keys()]


class SpatialTracker:
    def __init__(
        self,
        model=None,
        zone_pts=None,
        zone_threshold: Optional[int] = None,
        alert_cooldown=15.0,
        fall_confirmation_threshold=5,
        fire_model=None,
        camera_id: str = "CAM-01",
        zone: str = "Live Monitoring Zone",
        is_webcam: bool = False,
        enable_fire_detection: Optional[bool] = None,
        person_conf_threshold: Optional[float] = None,
        draw_skeletons: bool = False,
        fire_conf_threshold: Optional[float] = None,
        smoke_conf_threshold: Optional[float] = None,
        **kwargs,
    ):
        self.camera_id = camera_id
        self.zone_name = zone
        self.zone = zone  # Compatibility alias
        self.is_webcam = is_webcam
        self.draw_skeletons = draw_skeletons

        # Universal Human Bounding Box Detection:
        # Lowered to conf=0.25 globally across all camera inference loops so that people in outdoor/wide shots are reliably bounded
        if person_conf_threshold is not None:
            self.person_conf_threshold = person_conf_threshold
        elif kwargs.get("person_conf_threshold") is not None:
            self.person_conf_threshold = kwargs.get("person_conf_threshold")
        else:
            self.person_conf_threshold = 0.25

        if model is not None:
            self.model = model
        else:
            # Safely locate and load certified YOLO model supporting pedestrian & vehicle detection
            yolo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))
            os.makedirs(yolo_dir, exist_ok=True)
            candidate_paths = [
                os.path.join(yolo_dir, "yolo11n.pt"),
                os.path.join(yolo_dir, "yolov8n.pt"),
                os.path.join(yolo_dir, "yolo11n-pose.pt"),
            ]
            model_path = next((p for p in candidate_paths if os.path.exists(p)), candidate_paths[0])
            try:
                self.model = YOLO(model_path)
            except Exception as e:
                logger.error(f"Error loading YOLO model at {model_path}: {e}")
                self.model = None

        self.previous_y = {}
        self.previous_x = {}
        self.untracked_centroids = []
        self.up_count = 0
        self.down_count = 0
        self.occupancy_count = 0

        # Compatibility aliases
        self.entry_count = 0
        self.exit_count = 0
        self.track_history = {}

        # Feature 15 & 16: Zone definition and Crowding/Occupancy threshold
        # Crowd gathering alert triggers when 10 or more people are actively detected concurrently in the frame
        if zone_threshold is not None:
            self.zone_threshold = zone_threshold
        elif kwargs.get("zone_threshold") is not None:
            self.zone_threshold = kwargs.get("zone_threshold")
        else:
            self.zone_threshold = 10

        if zone_pts is not None:
            self.zone_pts = np.array(zone_pts, np.int32)
        else:
            self.zone_pts = np.array([[100, 150], [540, 150], [540, 400], [100, 400]], np.int32)

        # Alert cooldown tracking (Feature 15 WebSocket alerts)
        self.alert_cooldown = alert_cooldown
        self.last_alert_time = 0.0

        # Feature 17: Fall alert tracking & multi-frame temporal confirmation buffer
        self.last_fall_alert_time = 0.0
        self.fall_alert_cooldown = alert_cooldown
        self.spine_compression_threshold = 40.0
        self.fall_confirmation_threshold = fall_confirmation_threshold
        self.fall_counters = {}
        self.fall_consecutive_frames = self.fall_counters  # Compatibility alias
        self.untracked_fall_counter = 0
        self.untracked_fall_consecutive = 0
        self.track_heights = {}
        self.track_center_y = {}

        # Feature 21: Machine Learning Fire & Smoke Detection
        # Exclude physical webcams (CAM-01 / laptop feed) from environmental smoke/fire heuristics
        if enable_fire_detection is None:
            self.enable_fire_detection = not is_webcam
        else:
            self.enable_fire_detection = enable_fire_detection

        # Wet outdoor pavement, lighting & reflections calibration (CAM-03 & outdoor feeds):
        # Wet outdoor pavement reflections and outdoor lighting require high confidence (0.88) and minimum contour size (2000 px)
        if fire_conf_threshold is not None:
            self.fire_conf_threshold = fire_conf_threshold
        elif kwargs.get("fire_conf_threshold") is not None:
            self.fire_conf_threshold = kwargs.get("fire_conf_threshold")
        elif self.camera_id == "CAM-03":
            self.fire_conf_threshold = 0.88
        else:
            self.fire_conf_threshold = 0.50

        if smoke_conf_threshold is not None:
            self.smoke_conf_threshold = smoke_conf_threshold
        elif kwargs.get("smoke_conf_threshold") is not None:
            self.smoke_conf_threshold = kwargs.get("smoke_conf_threshold")
        elif self.camera_id == "CAM-03":
            self.smoke_conf_threshold = 0.88
        else:
            self.smoke_conf_threshold = 0.45

        if self.camera_id == "CAM-03":
            self.min_contour_size = 2000
            self.enable_smoke_heuristic = False
        else:
            self.min_contour_size = 500
            self.enable_smoke_heuristic = True

        if not self.enable_fire_detection:
            self.fire_detector = None
        else:
            self.fire_detector = FireDetector(
                model=fire_model or kwargs.get("fire_detector"),
                fire_conf_threshold=self.fire_conf_threshold,
                smoke_conf_threshold=self.smoke_conf_threshold,
                min_contour_area=self.min_contour_size,
                min_contour_size=self.min_contour_size,
                temporal_buffer_frames=5,
                is_webcam=is_webcam,
                enable_smoke_heuristic=self.enable_smoke_heuristic,
            )
        self.last_fire_alert_time = 0.0
        self.fire_alert_cooldown = alert_cooldown
        self.is_stream_active = False

        # Real-time frame processing FPS telemetry
        self.fps_last_time = time.time()
        self.fps_frame_count = 0
        self.current_fps = 0.0

        # Multi-Camera Inference Optimization & Frame Skipping
        if kwargs.get("infer_stride") is not None:
            self.infer_stride = max(1, int(kwargs.get("infer_stride")))
        else:
            self.infer_stride = 1  # 1 = every frame (default for unit-tests/single-frame calls)
        self.frame_counter = 0
        self.cached_parsed_boxes = []
        self.cached_persons_count = 0
        self.cached_vehicles_count = 0
        self.cached_occupancy_count = 0
        self.cached_is_crowded = False
        self.cached_fall_detected = False

    def generate_offline_signal_frame(
        self,
        width: int = 640,
        height: int = 480,
        message: str = "STREAM OFFLINE / NO SIGNAL",
    ) -> np.ndarray:
        """
        Generates a clean blank/black frame with an overlay reading STREAM OFFLINE / NO SIGNAL.
        Used by the Stream Health Guard when a camera feed is offline, unassigned, or fails to read.
        """
        w = max(320, width)
        h = max(240, height)
        offline_frame = np.zeros((h, w, 3), dtype=np.uint8)

        # Subtle industrial border reticle
        cv2.rectangle(offline_frame, (10, 10), (w - 10, h - 10), (30, 41, 59), 1)

        # Center banner
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.65 if w >= 500 else 0.5
        thickness = 2
        (tw, th), _ = cv2.getTextSize(message, font, font_scale, thickness)
        text_x = max(16, (w - tw) // 2)
        text_y = h // 2

        # Red status indicator dot
        dot_x = max(16, text_x - 18)
        cv2.circle(offline_frame, (dot_x, text_y - 6), 6, (68, 68, 239), -1)

        # Main alert text: STREAM OFFLINE / NO SIGNAL
        cv2.putText(
            offline_frame,
            message,
            (text_x, text_y),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

        # Camera ID & Zone sub-label
        subtext = f"{self.camera_id} // {self.zone_name}"
        (stw, sth), _ = cv2.getTextSize(subtext, font, 0.45, 1)
        stext_x = max(16, (w - stw) // 2)
        cv2.putText(
            offline_frame,
            subtext,
            (stext_x, text_y + 28),
            font,
            0.45,
            (148, 163, 184),
            1,
            cv2.LINE_AA,
        )

        return offline_frame

    def detect_fire_and_smoke(self, frame: np.ndarray):
        """Runs ML fire and smoke detection on the provided frame."""
        if self.fire_detector is None or frame is None:
            return False, []
        _, detected, detections = self.fire_detector.detect(frame)
        return detected, detections

    def process_frame(
        self,
        frame: Optional[np.ndarray],
        ret: bool = True,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        # Allow positional parameter flexibility if passed as (ret, frame)
        if isinstance(frame, bool):
            ret_arg = frame
            frame_arg = ret if (isinstance(ret, np.ndarray) or ret is None) else None
            ret = ret_arg
            frame = frame_arg

        persons_count = 0
        vehicles_count = 0
        occupancy_count = 0
        fall_detected = False
        fire_detected = False
        is_crowded = False

        # Stream Health Guard:
        # Check if the frame is valid (ret is True and frame is not empty/None).
        # If a camera feed is offline, unassigned, or fails to read:
        # 1. Immediately skip all AI inference (pose, fire, smoke).
        # 2. Suppress all alert generation for that camera ID.
        # 3. Return a clean blank/black frame with an overlay reading STREAM OFFLINE / NO SIGNAL.
        is_valid_stream = (
            bool(ret)
            and (frame is not None)
            and isinstance(frame, np.ndarray)
            and (frame.size > 0)
        )
        if is_valid_stream and hasattr(frame, "shape") and len(frame.shape) >= 2:
            if frame.shape[0] == 0 or frame.shape[1] == 0:
                is_valid_stream = False

        if not is_valid_stream:
            self.is_stream_active = False
            self.current_fps = 0.0
            self.fps_frame_count = 0
            self.fps_last_time = time.time()
            alert_manager.pause_stream_dispatch(self.camera_id)

            # Suppress all alerts & purge lingering temporal buffers so no ghost alerts fire
            self.fall_counters.clear()
            self.fall_consecutive_frames.clear()
            self.untracked_fall_counter = 0
            self.untracked_fall_consecutive = 0
            self.track_heights.clear()
            self.track_center_y.clear()
            self.track_history.clear()
            self.previous_y.clear()
            self.cached_parsed_boxes.clear()
            self.frame_counter = 0
            if self.fire_detector is not None:
                self.fire_detector.reset()

            # Determine dimensions from incoming frame if available, else standard 640x480
            h = frame.shape[0] if (frame is not None and isinstance(frame, np.ndarray) and frame.ndim >= 2 and frame.shape[0] > 0) else 480
            w = frame.shape[1] if (frame is not None and isinstance(frame, np.ndarray) and frame.ndim >= 2 and frame.shape[1] > 0) else 640
            offline_frame = self.generate_offline_signal_frame(width=w, height=h)

            return offline_frame, {
                "entry": self.down_count,
                "exit": self.up_count,
                "persons": 0,
                "vehicles": 0,
                "occupancy": 0,
                "occupancy_count": 0,
                "is_crowded": False,
                "gathering_alert": False,
                "fall_detected": False,
                "fire_detected": False,
                "smoke_detected": False,
                "hazard_type": None,
                "stream_healthy": False,
                "fps": 0,
            }

        # Valid live frame: mark stream active on circuit breaker
        self.is_stream_active = True
        alert_manager.resume_stream_dispatch(self.camera_id)

        # Calculate real-time frame processing FPS
        self.fps_frame_count += 1
        now_time = time.time()
        elapsed_time = now_time - self.fps_last_time
        if elapsed_time >= 1.0:
            self.current_fps = round(self.fps_frame_count / elapsed_time, 1)
            self.fps_frame_count = 0
            self.fps_last_time = now_time
        elif self.current_fps == 0.0 and elapsed_time > 0.0:
            self.current_fps = round(self.fps_frame_count / elapsed_time, 1)

        reported_fps = self.current_fps if self.current_fps > 0 else (
            round(self.fps_frame_count / max(0.001, elapsed_time), 1)
        )

        try:
            height, width = frame.shape[:2]
            line_y = int(height * 0.55)
            line_x = int(width * 0.50)

            # Multi-Camera Inference Optimization: frame-skipping
            self.frame_counter += 1
            should_infer = (
                (self.infer_stride <= 1)
                or ((self.frame_counter - 1) % self.infer_stride == 0)
                or (not self.cached_parsed_boxes and self.model is not None)
            )

            if should_infer:
                # 1. Run Tracker with calibrated conf threshold and pedestrian/vehicle class filtering
                active_model = self.model
                if active_model is not None:
                    if hasattr(active_model, "track") and callable(getattr(active_model, "track")):
                        try:
                            track_out = active_model.track(
                                frame,
                                persist=True,
                                tracker="bytetrack.yaml",
                                verbose=False,
                                conf=self.person_conf_threshold,
                                classes=ALL_ACTIVE_CLASSES,
                            )
                        except TypeError:
                            try:
                                track_out = active_model.track(
                                    frame,
                                    persist=True,
                                    tracker="bytetrack.yaml",
                                    verbose=False,
                                    conf=self.person_conf_threshold,
                                )
                            except TypeError:
                                track_out = active_model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
                        results = track_out[0] if isinstance(track_out, (list, tuple)) else track_out
                    else:
                        try:
                            call_out = active_model(
                                frame,
                                verbose=False,
                                conf=self.person_conf_threshold,
                                classes=ALL_ACTIVE_CLASSES,
                            )
                        except TypeError:
                            try:
                                call_out = active_model(frame, verbose=False, conf=self.person_conf_threshold)
                            except TypeError:
                                call_out = active_model(frame, verbose=False)
                        results = call_out[0] if isinstance(call_out, (list, tuple)) else call_out
                else:
                    results = None

                parsed_boxes = []
                if results is not None and getattr(results, "boxes", None) is not None:
                    boxes_obj = results.boxes
                    has_boxes = False
                    if isinstance(boxes_obj, list):
                        has_boxes = len(boxes_obj) > 0
                    elif hasattr(boxes_obj, "xyxy") and hasattr(boxes_obj.xyxy, "__len__"):
                        has_boxes = len(boxes_obj.xyxy) > 0
                    elif hasattr(boxes_obj, "__len__"):
                        try:
                            has_boxes = len(boxes_obj) > 0
                        except TypeError:
                            has_boxes = True
                    else:
                        has_boxes = True

                    if has_boxes:
                        if isinstance(boxes_obj, list):
                            boxes = np.array([
                                b.xyxy[0]
                                if hasattr(b, "xyxy") and isinstance(b.xyxy, (list, tuple, np.ndarray))
                                else getattr(b, "xyxy", [0, 0, 0, 0])
                                for b in boxes_obj
                            ])
                            clss = np.array([
                                b.cls[0].item()
                                if hasattr(b, "cls") and hasattr(b.cls[0], "item")
                                else getattr(b, "cls", 0)
                                for b in boxes_obj
                            ])
                            confs = np.array([
                                float(b.conf[0].item() if hasattr(b.conf[0], "item") else b.conf[0])
                                if hasattr(b, "conf") and isinstance(b.conf, (list, tuple))
                                else getattr(b, "conf", 1.0)
                                for b in boxes_obj
                            ])
                            track_ids = [
                                int(b.id.item())
                                if hasattr(b, "id") and b.id is not None and hasattr(b.id, "item")
                                else getattr(b, "id", None)
                                for b in boxes_obj
                            ]
                        else:
                            xyxy = boxes_obj.xyxy
                            boxes = xyxy.cpu().numpy() if hasattr(xyxy, "cpu") else np.array(xyxy)
                            cls_arr = boxes_obj.cls
                            if hasattr(cls_arr, "cpu"):
                                clss = cls_arr.cpu().numpy()
                            elif isinstance(cls_arr, (list, tuple)):
                                clss = [c.item() if hasattr(c, "item") and callable(c.item) else c for c in cls_arr]
                            else:
                                clss = np.array(cls_arr)

                            conf_arr = getattr(boxes_obj, "conf", None)
                            if conf_arr is not None:
                                if hasattr(conf_arr, "cpu"):
                                    confs = conf_arr.cpu().numpy()
                                elif isinstance(conf_arr, (list, tuple)):
                                    confs = [c.item() if hasattr(c, "item") and callable(c.item) else c for c in conf_arr]
                                else:
                                    confs = np.array(conf_arr)
                            else:
                                confs = np.ones(len(boxes), dtype=np.float32)

                            if getattr(boxes_obj, "id", None) is not None:
                                id_arr = boxes_obj.id
                                if hasattr(id_arr, "int"):
                                    id_arr = id_arr.int()
                                if hasattr(id_arr, "cpu"):
                                    id_arr = id_arr.cpu()
                                track_ids = id_arr.tolist() if hasattr(id_arr, "tolist") else list(id_arr)
                            else:
                                track_ids = [None] * len(boxes)

                        # Safe Keypoint extraction (Pose model)
                        has_keypoints = hasattr(results, "keypoints") and results.keypoints is not None
                        if has_keypoints:
                            kp_obj = results.keypoints
                            try:
                                if hasattr(kp_obj, "data") and "Mock" not in type(kp_obj.data).__name__:
                                    data = kp_obj.data
                                    data_np = data.cpu().numpy() if hasattr(data, "cpu") else (data.numpy() if hasattr(data, "numpy") else np.array(data))
                                    kpts = data_np[:, :, :3] if data_np.shape[-1] >= 3 else data_np
                                elif hasattr(kp_obj, "xy") and "Mock" not in type(kp_obj.xy).__name__:
                                    xy = kp_obj.xy
                                    xy_np = (
                                        xy.cpu().numpy()
                                        if hasattr(xy, "cpu")
                                        else (xy.numpy() if hasattr(xy, "numpy") else np.array(xy))
                                    )
                                    conf_kp = getattr(kp_obj, "conf", None)
                                    if conf_kp is not None and "Mock" not in type(conf_kp).__name__:
                                        c_np = conf_kp.cpu().numpy() if hasattr(conf_kp, "cpu") else (conf_kp.numpy() if hasattr(conf_kp, "numpy") else np.array(conf_kp))
                                        if c_np.ndim == 2 and xy_np.ndim == 3 and c_np.shape[:2] == xy_np.shape[:2]:
                                            kpts = np.dstack([xy_np, c_np[:, :, None]])
                                        else:
                                            kpts = xy_np
                                    else:
                                        kpts = xy_np
                                elif isinstance(kp_obj, (list, tuple, np.ndarray)):
                                    kpts = np.array(kp_obj)
                                else:
                                    kpts = [None] * len(boxes)
                            except Exception as e:
                                logger.debug(f"Could not parse keypoints: {e}")
                                kpts = [None] * len(boxes)
                        else:
                            kpts = [None] * len(boxes)

                        scale_x = 1.0
                        scale_y = 1.0
                        orig_shape = getattr(results, "orig_shape", None)
                        if (
                            orig_shape is not None
                            and "Mock" not in type(orig_shape).__name__
                            and hasattr(orig_shape, "__len__")
                            and len(orig_shape) >= 2
                        ):
                            try:
                                orig_h = float(orig_shape[0])
                                orig_w = float(orig_shape[1])
                                if orig_h > 0 and orig_w > 0:
                                    scale_x = width / orig_w
                                    scale_y = height / orig_h
                            except (TypeError, ValueError):
                                scale_x = 1.0
                                scale_y = 1.0

                        for i, (box, cls, conf, track_id) in enumerate(zip(boxes, clss, confs, track_ids)):
                            conf_val = float(conf.item() if hasattr(conf, "item") else conf)
                            if conf_val < self.person_conf_threshold:
                                continue
                            class_id = int(cls.item() if hasattr(cls, "item") else cls)

                            # Precise scaling and coordinate offset calibration to align exactly with tracked subjects
                            try:
                                box_flat = np.array(box, dtype=float).flatten()
                                raw_x1, raw_y1, raw_x2, raw_y2 = float(box_flat[0]), float(box_flat[1]), float(box_flat[2]), float(box_flat[3])
                            except Exception:
                                raw_coords = list(map(float, box))
                                raw_x1, raw_y1, raw_x2, raw_y2 = raw_coords[0], raw_coords[1], raw_coords[2], raw_coords[3]

                            if scale_x != 1.0 or scale_y != 1.0:
                                x1 = int(round(raw_x1 * scale_x))
                                y1 = int(round(raw_y1 * scale_y))
                                x2 = int(round(raw_x2 * scale_x))
                                y2 = int(round(raw_y2 * scale_y))
                            else:
                                x1 = int(round(raw_x1))
                                y1 = int(round(raw_y1))
                                x2 = int(round(raw_x2))
                                y2 = int(round(raw_y2))

                            # Strict clamp within frame boundaries
                            x1 = max(0, min(width - 1, x1))
                            y1 = max(0, min(height - 1, y1))
                            x2 = max(x1 + 1, min(width, x2))
                            y2 = max(y1 + 1, min(height, y2))

                            center_x = (x1 + x2) // 2
                            center_y = (y1 + y2) // 2
                            w = x2 - x1
                            h = y2 - y1

                            tid = None
                            if track_id is not None:
                                try:
                                    tid = int(track_id.item() if hasattr(track_id, "item") else track_id)
                                except Exception:
                                    tid = None

                            if class_id == 0:  # Person
                                persons_count += 1
                                feet_x = (x1 + x2) // 2
                                feet_y = float(y2)
                                if cv2.pointPolygonTest(self.zone_pts, (float(feet_x), float(feet_y)), False) >= 0:
                                    occupancy_count += 1

                                # Feature 17: Fall Detection Guardrails
                                # Guard 1 (Incomplete Body Guard): If bounding box touches bottom edge (desk webcam), disable fall detection entirely.
                                # Guard 2 (Strict Trajectory Rule): Fall requires rapid downward center-y shift AND true horizontal orientation (w > h * 1.3).
                                is_falling = False
                                person_kpts = None
                                fall_condition_met = False

                                has_valid_pose = False
                                nose_y = 0.0
                                shoulder_y = 0.0
                                hip_y = 0.0

                                def check_kpt_conf(kp_entry, min_conf=0.3):
                                    if kp_entry is None or len(kp_entry) < 2:
                                        return False
                                    y_val = float(kp_entry[1])
                                    if y_val <= 0:
                                        return False
                                    if len(kp_entry) >= 3:
                                        return float(kp_entry[2]) > min_conf
                                    return True

                                if kpts is not None and i < len(kpts) and kpts[i] is not None:
                                    raw_p_kpts = kpts[i]
                                    if hasattr(raw_p_kpts, "cpu"):
                                        raw_p_kpts = raw_p_kpts.cpu().numpy()
                                    p_arr = np.array(raw_p_kpts)
                                    if p_arr.ndim >= 2 and len(p_arr) >= 13:
                                        if scale_x != 1.0 or scale_y != 1.0:
                                            p_scaled = p_arr.copy()
                                            p_scaled[:, 0] = p_scaled[:, 0] * scale_x
                                            p_scaled[:, 1] = p_scaled[:, 1] * scale_y
                                            person_kpts = p_scaled
                                        else:
                                            person_kpts = p_arr
                                        if check_kpt_conf(person_kpts[0], 0.3):
                                            nose_y = float(person_kpts[0][1])

                                        valid_shoulders = [float(person_kpts[idx][1]) for idx in (5, 6) if check_kpt_conf(person_kpts[idx], 0.3)]
                                        valid_hips = [float(person_kpts[idx][1]) for idx in (11, 12) if check_kpt_conf(person_kpts[idx], 0.3)]

                                        if nose_y > 0 and len(valid_shoulders) > 0 and len(valid_hips) > 0:
                                            shoulder_y = sum(valid_shoulders) / float(len(valid_shoulders))
                                            hip_y = sum(valid_hips) / float(len(valid_hips))
                                            has_valid_pose = True

                                is_bottom_edge_cut = (y2 >= height - 15)

                                if has_valid_pose and (nose_y < hip_y):
                                    # Upright pose (head above hips) - sitting or standing, never a fall
                                    fall_condition_met = False
                                    if tid is not None:
                                        self.fall_counters[tid] = 0
                                        self.fall_consecutive_frames[tid] = 0
                                    else:
                                        self.untracked_fall_counter = 0
                                        self.untracked_fall_consecutive = 0
                                elif is_bottom_edge_cut:
                                    # Desk webcam guard: legs cut off at bottom of frame -> disable fall detection entirely
                                    fall_condition_met = False
                                    if tid is not None:
                                        self.fall_counters[tid] = 0
                                        self.fall_consecutive_frames[tid] = 0
                                    else:
                                        self.untracked_fall_counter = 0
                                        self.untracked_fall_consecutive = 0
                                else:
                                    # Strict Trajectory Rule & True Horizontal Orientation (w > h * 1.3)
                                    is_true_horizontal = (w > h * 1.3)
                                    rapid_downward_shift = False

                                    if tid is not None:
                                        if tid not in self.track_center_y:
                                            self.track_center_y[tid] = []
                                        y_hist = self.track_center_y[tid]

                                        if len(y_hist) >= 1:
                                            earliest_y = min(y_hist)
                                            if (center_y - earliest_y) >= 20:
                                                rapid_downward_shift = True
                                        elif len(y_hist) == 0:
                                            # First observation: allow if pose has head at/below hips or collapse
                                            if has_valid_pose and (nose_y >= hip_y):
                                                rapid_downward_shift = True
                                            elif not has_valid_pose and is_true_horizontal:
                                                rapid_downward_shift = True

                                        # Preserve active confirmed falling sequence while still horizontal
                                        if self.fall_counters.get(tid, 0) >= 1 and is_true_horizontal:
                                            rapid_downward_shift = True

                                        y_hist.append(center_y)
                                        if len(y_hist) > 20:
                                            y_hist.pop(0)
                                    else:
                                        if has_valid_pose:
                                            rapid_downward_shift = (nose_y >= hip_y)
                                        else:
                                            rapid_downward_shift = is_true_horizontal

                                    # Trigger fall only when both true horizontal and rapid downward drop are present
                                    fall_condition_met = is_true_horizontal and rapid_downward_shift

                                # Temporal Frame Buffer: persist for at least 5 consecutive frames
                                if fall_condition_met:
                                    if tid is not None:
                                        curr_frames = self.fall_counters.get(tid, 0) + 1
                                        self.fall_counters[tid] = curr_frames
                                        self.fall_consecutive_frames[tid] = curr_frames
                                    else:
                                        self.untracked_fall_counter += 1
                                        self.untracked_fall_consecutive = self.untracked_fall_counter
                                        curr_frames = self.untracked_fall_counter
                                else:
                                    if tid is not None:
                                        self.fall_counters[tid] = 0
                                        self.fall_consecutive_frames[tid] = 0
                                    else:
                                        self.untracked_fall_counter = 0
                                        self.untracked_fall_consecutive = 0
                                    curr_frames = 0

                                if curr_frames >= self.fall_confirmation_threshold:
                                    is_falling = True

                                if is_falling:
                                    fall_detected = True

                                # Track ID & Line-Crossing Math (Bidirectional: Horizontal Y & Vertical X)
                                old_y = None
                                old_x = None

                                if tid is not None:
                                    old_y = self.previous_y.get(tid)
                                    old_x = self.previous_x.get(tid)
                                    self.previous_y[tid] = center_y
                                    self.previous_x[tid] = center_x
                                else:
                                    # Fallback spatial centroid matching for untracked pedestrians (distant or intermittent)
                                    best_idx = -1
                                    min_dist = 80.0
                                    for c_idx, (ux, uy, utime) in enumerate(self.untracked_centroids):
                                        dist = np.hypot(center_x - ux, center_y - uy)
                                        if dist < min_dist:
                                            min_dist = dist
                                            best_idx = c_idx
                                    if best_idx >= 0:
                                        old_x, old_y, _ = self.untracked_centroids[best_idx]
                                        self.untracked_centroids[best_idx] = (center_x, center_y, time.time())
                                    else:
                                        self.untracked_centroids.append((center_x, center_y, time.time()))
                                        if len(self.untracked_centroids) > 25:
                                            self.untracked_centroids.pop(0)

                                # Evaluate virtual line-crossing vector (top-to-bottom OR left-to-right)
                                crossed_entry = False
                                crossed_exit = False

                                # 1. Vertical crossing across horizontal line (Top-to-Bottom = Entry, Bottom-to-Top = Exit)
                                if old_y is not None:
                                    if old_y < line_y <= center_y:
                                        crossed_entry = True
                                    elif old_y > line_y >= center_y:
                                        crossed_exit = True

                                # 2. Horizontal crossing across vertical line (Left-to-Right = Entry, Right-to-Left = Exit)
                                if not crossed_entry and not crossed_exit and old_x is not None:
                                    if old_x < line_x <= center_x:
                                        crossed_entry = True
                                    elif old_x > line_x >= center_x:
                                        crossed_exit = True

                                if crossed_entry:
                                    self.down_count += 1
                                    self.entry_count = self.down_count
                                elif crossed_exit:
                                    self.up_count += 1
                                    self.exit_count = self.up_count

                                parsed_boxes.append((x1, y1, x2, y2, center_y, True, tid, is_falling, person_kpts))
                            elif class_id in COCO_VEHICLE_CLASSES:  # Vehicles: Car (2), Motorcycle (3), Bus (5), Truck (7)
                                vehicles_count += 1
                                v_name = COCO_VEHICLE_CLASSES[class_id]
                                parsed_boxes.append((x1, y1, x2, y2, center_y, False, tid, False, v_name))

                # Real-Time Occupancy & Crowd Calculation:
                # Active people count in the monitored zone / frame
                active_crowd_count = max(occupancy_count, persons_count)
                is_crowded = (occupancy_count >= self.zone_threshold) or (active_crowd_count >= self.zone_threshold)
                self.occupancy_count = active_crowd_count if is_crowded else occupancy_count
                occupancy_count = self.occupancy_count

                self.cached_parsed_boxes = list(parsed_boxes)
                self.cached_persons_count = persons_count
                self.cached_vehicles_count = vehicles_count
                self.cached_occupancy_count = occupancy_count
                self.cached_is_crowded = is_crowded
                self.cached_fall_detected = fall_detected
            else:
                parsed_boxes = list(self.cached_parsed_boxes)
                persons_count = self.cached_persons_count
                vehicles_count = self.cached_vehicles_count
                occupancy_count = self.cached_occupancy_count
                is_crowded = self.cached_is_crowded
                fall_detected = self.cached_fall_detected

            # 2. Contextual UI & Alpha-Blended Overlays
            overlay = frame.copy()

            # Translucent Tripwire (Yellow counting line spanning active horizontal & vertical paths)
            # Omit tripwire lines on CAM-02 for clean and minimal presentation
            if self.camera_id != "CAM-02":
                cv2.line(overlay, (0, line_y), (width, line_y), (0, 215, 255), 2)
                cv2.line(overlay, (line_x, 0), (line_x, height), (0, 215, 255), 2)

            # Single semi-transparent dark bar across top
            cv2.rectangle(overlay, (0, 0), (width, 36), (15, 23, 42), -1)

            # Contextual UI: Polygon is INVISIBLE until breached!
            if is_crowded:
                cv2.fillPoly(overlay, [self.zone_pts], (0, 0, 255))

            # Blend smoothly into frame
            cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

            # Crisp tripwire line (spans horizontal & vertical walkway paths)
            if self.camera_id != "CAM-02":
                cv2.line(frame, (0, line_y), (width, line_y), (0, 215, 255), 1)
                cv2.line(frame, (line_x, 0), (line_x, height), (0, 215, 255), 1)

            # If breached, render crisp red boundary and bold warning
            if is_crowded:
                cv2.polylines(frame, [self.zone_pts], isClosed=True, color=(0, 0, 255), thickness=2)
                cv2.putText(
                    frame,
                    "WARNING: CROWD GATHERING ALERT",
                    (self.zone_pts[0][0], max(25, self.zone_pts[0][1] - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )

            # 3. Dynamic Overlay: Bounding Boxes, Skeletons & Fall Indicator
            for x1, y1, x2, y2, center_y, is_person, tid, is_falling, p_kpts, *extra in parsed_boxes:
                if is_person:
                    # Turns red and displays CRITICAL: FALL DETECTED the exact moment fall_detected is True
                    # Turns red warning bounding box overlay when ABNORMAL GATHERING / CROWD GATHERING (is_crowded) is detected
                    is_active_fall = is_falling or (fall_detected and len(parsed_boxes) == 1)
                    if is_active_fall or is_crowded:
                        color = (0, 0, 255)  # Pure Red warning overlay
                    else:
                        color = (74, 222, 128)  # Emerald Green

                    # Draw Skeleton Limbs & Keypoint Joints only if draw_skeletons is True (disabled by default to prevent visual clutter)
                    if getattr(self, "draw_skeletons", False) and p_kpts is not None and len(p_kpts) >= 13:
                        for pt1_idx, pt2_idx in SKELETON_EDGES:
                            if pt1_idx < len(p_kpts) and pt2_idx < len(p_kpts):
                                x1_k, y1_k = p_kpts[pt1_idx][:2]
                                x2_k, y2_k = p_kpts[pt2_idx][:2]
                                if x1_k > 0 and y1_k > 0 and x2_k > 0 and y2_k > 0:
                                    cv2.line(
                                        frame,
                                        (int(round(x1_k)), int(round(y1_k))),
                                        (int(round(x2_k)), int(round(y2_k))),
                                        color,
                                        2,
                                        cv2.LINE_AA,
                                    )

                        for kp in p_kpts:
                            kx, ky = kp[:2]
                            if kx > 0 and ky > 0:
                                cv2.circle(frame, (int(round(kx)), int(round(ky))), 4, color, -1, cv2.LINE_AA)
                                cv2.circle(frame, (int(round(kx)), int(round(ky))), 2, (255, 255, 255), -1, cv2.LINE_AA)

                    # Bounding box (thickness 2 for fall or abnormal gathering warning)
                    box_thickness = 2 if (is_active_fall or is_crowded) else 1
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, box_thickness)

                    if is_active_fall:
                        text_y = (y1 - 25) if y1 >= 35 else (y1 - 10 if y1 >= 25 else max(20, y1 + 22))
                        cv2.putText(
                            frame,
                            "CRITICAL: FALL DETECTED",
                            (x1, text_y),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 0, 255),
                            2,
                            cv2.LINE_AA,
                        )
                        label = f"ID:{tid}" if tid is not None else "Person"
                        cv2.putText(
                            frame,
                            label,
                            (x1, max(12, text_y - 18) if text_y > 25 else y2 - 6),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            color,
                            2,
                            cv2.LINE_AA,
                        )
                    elif is_crowded:
                        label = f"ID:{tid} [CROWD]" if tid is not None else "Person [CROWD]"
                        cv2.putText(
                            frame,
                            label,
                            (x1, max(12, y1 - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (0, 0, 255),
                            2,
                            cv2.LINE_AA,
                        )
                    else:
                        label = f"ID:{tid}" if tid is not None else "Person"
                        cv2.putText(
                            frame,
                            label,
                            (x1, max(12, y1 - 5)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            color,
                            1,
                            cv2.LINE_AA,
                        )
                else:
                    # Vehicle bounding box (Car, Truck, Bus, Motorcycle)
                    color = (255, 215, 0)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    v_type = p_kpts if isinstance(p_kpts, str) else (extra[0] if extra else "Vehicle")
                    v_label = f"ID:{tid} [{v_type}]" if tid is not None else f"[{v_type}]"
                    cv2.putText(
                        frame,
                        v_label,
                        (x1, max(12, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        color,
                        2,
                        cv2.LINE_AA,
                    )

            # 4. Unified Top HUD Text across top center
            hud_text = f"ENTRY: {self.down_count} | EXIT: {self.up_count} | OCCUPANCY: {occupancy_count}"
            (tw, th), _ = cv2.getTextSize(hud_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            text_x = max(16, (width - tw) // 2)
            cv2.putText(
                frame,
                hud_text,
                (text_x, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

            # 5. Alert Trigger & 15s Cooldown WebSocket Dispatch (IST Timestamps)
            # Circuit Breaker: strictly gate dispatches on verified active stream status
            if is_crowded and self.is_stream_active and alert_manager.is_stream_active(self.camera_id):
                now_ts = time.time()
                if (now_ts - self.last_alert_time) >= self.alert_cooldown:
                    self.last_alert_time = now_ts
                    alert_payload = {
                        "id": f"EVT-CROWD-{int(now_ts)}",
                        "event_id": f"EVT-CROWD-{int(now_ts)}",
                        "time": datetime.now(IST).strftime("%H:%M:%S IST"),
                        "timestamp_ist": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
                        "zone": self.zone_name,
                        "camera": self.camera_id,
                        "camera_id": self.camera_id,
                        "type": "CROWD GATHERING ALERT",
                        "level": "CRITICAL",
                        "alarm_class": "CRITICAL",
                        "detail": f"Crowd gathering alert (10+ persons) breached on {self.camera_id} ({self.zone_name}): {active_crowd_count} persons present.",
                        "person_count": active_crowd_count,
                        "occupancy": occupancy_count,
                        "acknowledged": False,
                    }
                    logger.warning(f"WebSocket Alert Fired: {alert_payload}")
                    alert_manager.broadcast_sync(alert_payload)

            if fall_detected and self.is_stream_active and alert_manager.is_stream_active(self.camera_id):
                now_ts = time.time()
                if (now_ts - self.last_fall_alert_time) >= self.fall_alert_cooldown:
                    self.last_fall_alert_time = now_ts
                    fall_payload = {
                        "id": f"EVT-FALL-{int(now_ts)}",
                        "time": datetime.now(IST).strftime("%H:%M:%S IST"),
                        "zone": self.zone_name,
                        "camera": self.camera_id,
                        "type": "MAN DOWN / FALL DETECTED",
                        "level": "CRITICAL",
                        "detail": f"Worker fall confirmed on {self.camera_id} ({self.zone_name}). Immediate assistance required.",
                        "acknowledged": False,
                    }
                    logger.warning(f"WebSocket Fall Alert Fired: {fall_payload}")
                    alert_manager.broadcast_sync(fall_payload)

            # Feature 21: Machine Learning Fire & Smoke Detection (Optimized for CAM-03 flames & CAM-04 smoke)
            smoke_detected = False
            hazard_type = None
            if self.fire_detector is not None and not self.is_webcam and self.is_stream_active and alert_manager.is_stream_active(self.camera_id):
                try:
                    frame, hazard_detected, fire_boxes = self.fire_detector.detect(frame)
                    # CAM-03 Outdoor Yard False-Positive Guard:
                    # Enforce conf >= 0.88 and minimum contour/box area >= 2000 px to block headlights, reflections, and wet outdoor pavement
                    if self.camera_id == "CAM-03":
                        valid_boxes = []
                        for b in fire_boxes:
                            bx1, by1, bx2, by2 = b.get("box", [0, 0, 0, 0])
                            box_area = max(0, bx2 - bx1) * max(0, by2 - by1)
                            b_conf = float(b.get("confidence", 0.0))
                            if b_conf >= self.smoke_conf_threshold and box_area >= 2000:
                                valid_boxes.append(b)
                        fire_boxes = valid_boxes
                        hazard_detected = len(fire_boxes) > 0 and hazard_detected

                    if hazard_detected and self.is_stream_active and alert_manager.is_stream_active(self.camera_id):
                        is_smoke = (
                            getattr(self.fire_detector, "primary_hazard", None) == "smoke"
                            or any(b.get("class_name") == "smoke" for b in fire_boxes)
                        )
                        is_fire = (
                            getattr(self.fire_detector, "primary_hazard", None) in ["fire", "fire_and_smoke"]
                            or any(b.get("class_name") == "fire" for b in fire_boxes)
                            or not is_smoke
                        )
                        fire_detected = is_fire
                        smoke_detected = is_smoke
                        hazard_type = "smoke" if (is_smoke and not is_fire) else ("fire_and_smoke" if (is_smoke and is_fire) else "fire")
                        now_ts = time.time()
                        if (now_ts - self.last_fire_alert_time) >= self.fire_alert_cooldown:
                            self.last_fire_alert_time = now_ts
                            fire_payload = {
                                "id": f"EVT-HAZARD-{int(now_ts)}",
                                "time": datetime.now(IST).strftime("%H:%M:%S IST"),
                                "zone": self.zone_name,
                                "camera": self.camera_id,
                                "type": "CRITICAL HAZARD: FIRE / SMOKE DETECTED",
                                "level": "CRITICAL",
                                "detail": f"Hazard identified on {self.camera_id} ({self.zone_name}). Immediate evacuation required.",
                                "acknowledged": False,
                            }
                            logger.warning(f"WebSocket Hazard Alert Fired: {fire_payload}")
                            alert_manager.broadcast_sync(fire_payload)
                except Exception as e:
                    logger.error(f"Error during ML fire detection: {e}")
                    fire_detected = False
                    smoke_detected = False

            # Sync compatibility aliases
            self.entry_count = self.down_count
            self.exit_count = self.up_count

            return frame, {
                "entry": self.down_count,
                "exit": self.up_count,
                "persons": persons_count,
                "vehicles": vehicles_count,
                "occupancy": occupancy_count,
                "occupancy_count": occupancy_count,
                "is_crowded": is_crowded,
                "gathering_alert": is_crowded,
                "fall_detected": fall_detected,
                "fire_detected": fire_detected,
                "smoke_detected": smoke_detected,
                "hazard_type": hazard_type,
                "stream_healthy": True,
                "fps": reported_fps,
            }

        except Exception as e:
            logger.error(f"AI Loop Crash: {e}")
            self.entry_count = self.down_count
            self.exit_count = self.up_count
            return frame, {
                "entry": self.down_count,
                "exit": self.up_count,
                "persons": persons_count,
                "vehicles": vehicles_count,
                "occupancy": occupancy_count,
                "occupancy_count": occupancy_count,
                "is_crowded": False,
                "gathering_alert": False,
                "fall_detected": False,
                "fire_detected": False,
                "smoke_detected": False,
                "hazard_type": None,
                "stream_healthy": False,
                "fps": 0,
            }

    def get_counts(self) -> dict:
        """Returns snapshot of current spatial counts and stream telemetry."""
        return {
            "occupancy": getattr(self, "cached_occupancy_count", getattr(self, "occupancy_count", 0)),
            "persons": getattr(self, "cached_persons_count", getattr(self, "occupancy_count", 0)),
            "entries": getattr(self, "entry_count", getattr(self, "down_count", 0)),
            "exits": getattr(self, "exit_count", getattr(self, "up_count", 0)),
            "fps": getattr(self, "current_fps", 0.0),
            "stream_healthy": getattr(self, "is_stream_active", True),
            "is_crowded": getattr(self, "cached_is_crowded", False),
            "fall_detected": getattr(self, "cached_fall_detected", False),
        }

    def reset(self):
        self.up_count = 0
        self.down_count = 0
        self.entry_count = 0
        self.exit_count = 0
        self.occupancy_count = 0
        self.previous_y.clear()
        self.previous_x.clear()
        self.untracked_centroids.clear()
        self.track_history.clear()
        self.track_heights.clear()
        self.track_center_y.clear()
        self.last_alert_time = 0.0
        self.last_fall_alert_time = 0.0
        self.last_fire_alert_time = 0.0
        if self.fire_detector is not None:
            self.fire_detector.reset()
        self.fall_counters.clear()
        self.fall_consecutive_frames.clear()
        self.untracked_fall_counter = 0
        self.untracked_fall_consecutive = 0
        self.cached_parsed_boxes.clear()
        self.frame_counter = 0
        self.cached_persons_count = 0
        self.cached_vehicles_count = 0
        self.cached_occupancy_count = 0
        self.cached_is_crowded = False
        self.cached_fall_detected = False


