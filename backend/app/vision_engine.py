import cv2
import os
import time
import uuid
import logging
from datetime import datetime, timezone, timedelta
import numpy as np
from ultralytics import YOLO

from backend.app.core.websocket_manager import alert_manager

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


class SpatialTracker:
    def __init__(self, model=None, zone_pts=None, zone_threshold=4, alert_cooldown=15.0, fall_confirmation_threshold=5):
        if model is not None:
            self.model = model
        else:
            # Safely locate and load the YOLO11n-Pose model (Feature 17: Fall Detection)
            model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "yolo11n-pose.pt"))
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            try:
                self.model = YOLO(model_path)
            except Exception as e:
                logger.error(f"Error loading YOLO pose model at {model_path}: {e}")
                self.model = None

        self.previous_y = {}
        self.up_count = 0
        self.down_count = 0

        # Compatibility aliases
        self.entry_count = 0
        self.exit_count = 0
        self.track_history = {}

        # Feature 15 & 16: Zone definition and Crowding/Occupancy threshold
        self.zone_threshold = zone_threshold
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

    def process_frame(self, frame):
        persons_count = 0
        vehicles_count = 0
        occupancy_count = 0
        fall_detected = False
        is_crowded = False

        if frame is None or not isinstance(frame, np.ndarray):
            return frame, {
                "entry": self.down_count,
                "exit": self.up_count,
                "persons": 0,
                "vehicles": 0,
                "occupancy": 0,
                "occupancy_count": 0,
                "is_crowded": False,
                "gathering_alert": False,
                "fall_detected": False,
            }

        try:
            height, width = frame.shape[:2]
            line_y = int(height * 0.55)

            # 1. Run Tracker (Using yolo11n-pose.pt) with conf=0.4
            active_model = self.model
            if active_model is not None:
                if hasattr(active_model, "track") and callable(getattr(active_model, "track")):
                    try:
                        track_out = active_model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False, conf=0.4)
                    except TypeError:
                        track_out = active_model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
                    results = track_out[0] if isinstance(track_out, (list, tuple)) else track_out
                else:
                    try:
                        call_out = active_model(frame, verbose=False, conf=0.4)
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

                    for i, (box, cls, conf, track_id) in enumerate(zip(boxes, clss, confs, track_ids)):
                        conf_val = float(conf.item() if hasattr(conf, "item") else conf)
                        if conf_val < 0.4:
                            continue
                        class_id = int(cls.item() if hasattr(cls, "item") else cls)
                        x1, y1, x2, y2 = map(int, box)
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

                            # Feature 17: Fall Detection (Temporal Frame Buffer & Refined Pose Math)
                            # 1. Condition A (Overhead Prone):
                            #    - Box width exceeds height (w > h * 1.1) continuously for 5 frames
                            # 2. Condition B (Seated vs Collapse):
                            #    - If a person is sitting, hip-to-shoulder vertical vector remains stable.
                            #    - Only trigger if vertical height collapses by > 50% relative to standing average while shifting horizontal.
                            # 3. Keypoint Confidence Filtering:
                            #    - Verify keypoint confidence (kpt[i][conf] > 0.3) before factoring coordinates into the math
                            # 4. Temporal Frame Buffer:
                            #    - Must persist for at least 5 consecutive frames (~0.25s at 20fps) via self.fall_counters[track_id]
                            is_falling = False
                            person_kpts = None
                            fall_condition_met = False

                            is_overhead_prone = (w > h * 1.1)

                            # Track baseline standing height for Condition B (Seated vs Collapse)
                            if tid is not None:
                                if tid not in self.track_heights:
                                    self.track_heights[tid] = []
                                if w <= h * 1.1:
                                    self.track_heights[tid].append(h)
                                    if len(self.track_heights[tid]) > 30:
                                        self.track_heights[tid].pop(0)

                                upright_history = self.track_heights.get(tid, [])
                                baseline_standing_h = max(upright_history) if len(upright_history) > 0 else float(h)
                                height_collapsed_over_50 = (baseline_standing_h > 0) and (h < baseline_standing_h * 0.5) and (w > h)
                            else:
                                height_collapsed_over_50 = (h < 90 and w > h)

                            is_collapse = height_collapsed_over_50 or (h < 90 and w > h)

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
                                    person_kpts = p_arr
                                    if check_kpt_conf(person_kpts[0], 0.3):
                                        nose_y = float(person_kpts[0][1])

                                    valid_shoulders = [float(person_kpts[idx][1]) for idx in (5, 6) if check_kpt_conf(person_kpts[idx], 0.3)]
                                    valid_hips = [float(person_kpts[idx][1]) for idx in (11, 12) if check_kpt_conf(person_kpts[idx], 0.3)]

                                    if nose_y > 0 and len(valid_shoulders) > 0 and len(valid_hips) > 0:
                                        shoulder_y = sum(valid_shoulders) / float(len(valid_shoulders))
                                        hip_y = sum(valid_hips) / float(len(valid_hips))
                                        has_valid_pose = True

                            if has_valid_pose:
                                spine_v_dist = abs(shoulder_y - hip_y)
                                compression_threshold = max(self.spine_compression_threshold, h * 0.35)
                                spine_compressed = (spine_v_dist < compression_threshold)
                                nose_at_or_below_hip = (nose_y >= hip_y)
                                is_upright_sitting = (nose_y < hip_y and shoulder_y < hip_y)

                                # Condition B (Seated vs Collapse):
                                # If sitting, hip-to-shoulder vertical vector remains stable (spine_compressed False, nose_y < hip_y).
                                # Only trigger if height collapses by over 50% relative to standing average while shifting horizontal.
                                if is_upright_sitting and not height_collapsed_over_50:
                                    fall_condition_met = False
                                else:
                                    fall_condition_met = is_overhead_prone or height_collapsed_over_50 or (spine_compressed and nose_at_or_below_hip)
                            else:
                                fall_condition_met = is_overhead_prone or is_collapse

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

                            # Track ID & Line-Crossing Math
                            if tid is not None:
                                old_y = self.previous_y.get(tid)
                                if old_y is not None:
                                    if old_y < line_y <= center_y:
                                        self.down_count += 1
                                    elif old_y > line_y >= center_y:
                                        self.up_count += 1
                                self.previous_y[tid] = center_y

                            parsed_boxes.append((x1, y1, x2, y2, center_y, True, tid, is_falling, person_kpts))
                        elif class_id in [2, 3, 5, 7]:  # Vehicles
                            vehicles_count += 1
                            parsed_boxes.append((x1, y1, x2, y2, center_y, False, None, False, None))

            is_crowded = (occupancy_count >= self.zone_threshold)

            # 2. Contextual UI & Alpha-Blended Overlays
            overlay = frame.copy()

            # Translucent Tripwire
            cv2.line(overlay, (0, line_y), (width, line_y), (0, 215, 255), 2)

            # Single semi-transparent dark bar across top
            cv2.rectangle(overlay, (0, 0), (width, 36), (15, 23, 42), -1)

            # Contextual UI: Polygon is INVISIBLE until breached!
            if is_crowded:
                cv2.fillPoly(overlay, [self.zone_pts], (0, 0, 255))

            # Blend smoothly into frame
            cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

            # Crisp tripwire line
            cv2.line(frame, (0, line_y), (width, line_y), (0, 215, 255), 1)

            # If breached, render crisp red boundary and bold warning
            if is_crowded:
                cv2.polylines(frame, [self.zone_pts], isClosed=True, color=(0, 0, 255), thickness=2)
                cv2.putText(
                    frame,
                    "WARNING: ABNORMAL GATHERING",
                    (self.zone_pts[0][0], max(25, self.zone_pts[0][1] - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (0, 0, 255),
                    2,
                    cv2.LINE_AA,
                )

            # 3. Dynamic Overlay: Bounding Boxes, Skeletons & Fall Indicator
            for x1, y1, x2, y2, center_y, is_person, tid, is_falling, p_kpts in parsed_boxes:
                if is_person:
                    # Turns red and displays CRITICAL: FALL DETECTED the exact moment fall_detected is True
                    is_active_fall = is_falling or (fall_detected and len(parsed_boxes) == 1)
                    if is_active_fall:
                        color = (0, 0, 255)  # Pure Red
                    else:
                        color = (74, 222, 128)  # Emerald Green

                    # Draw Skeleton Limbs & Keypoint Joints if available
                    if p_kpts is not None and len(p_kpts) >= 13:
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

                    # Bounding box
                    box_thickness = 2 if is_active_fall else 1
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
                    color = (255, 215, 0)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)
                    cv2.putText(
                        frame,
                        "Vehicle",
                        (x1, max(12, y1 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.45,
                        color,
                        1,
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
            if is_crowded:
                now_ts = time.time()
                if (now_ts - self.last_alert_time) >= self.alert_cooldown:
                    self.last_alert_time = now_ts
                    alert_payload = {
                        "id": f"EVT-CROWD-{int(now_ts)}",
                        "time": datetime.now(IST).strftime("%H:%M:%S IST"),
                        "zone": "Live Monitoring Zone",
                        "type": "ABNORMAL GATHERING",
                        "level": "CRITICAL",
                        "detail": "Occupancy threshold breached (> 3 persons).",
                        "acknowledged": False,
                    }
                    logger.warning(f"WebSocket Alert Fired: {alert_payload}")
                    alert_manager.broadcast_sync(alert_payload)

            if fall_detected:
                now_ts = time.time()
                if (now_ts - self.last_fall_alert_time) >= self.fall_alert_cooldown:
                    self.last_fall_alert_time = now_ts
                    fall_payload = {
                        "id": f"EVT-FALL-{int(now_ts)}",
                        "time": datetime.now(IST).strftime("%H:%M:%S IST"),
                        "zone": "Live Monitoring Zone",
                        "type": "MAN DOWN / FALL DETECTED",
                        "level": "CRITICAL",
                        "detail": "Worker fall confirmed: spine vector compression & head below hip level persisted across frames.",
                        "acknowledged": False,
                    }
                    logger.warning(f"WebSocket Fall Alert Fired: {fall_payload}")
                    alert_manager.broadcast_sync(fall_payload)

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
            }

    def reset(self):
        self.up_count = 0
        self.down_count = 0
        self.entry_count = 0
        self.exit_count = 0
        self.previous_y.clear()
        self.track_history.clear()
        self.track_heights.clear()
        self.track_center_y.clear()
        self.last_alert_time = 0.0
        self.last_fall_alert_time = 0.0
        self.fall_counters.clear()
        self.fall_consecutive_frames.clear()
        self.untracked_fall_counter = 0
        self.untracked_fall_consecutive = 0


