import cv2
import os
import time
import uuid
import logging
from datetime import datetime, timezone
import numpy as np
from ultralytics import YOLO

from backend.app.core.websocket_manager import alert_manager

logger = logging.getLogger(__name__)

COLOR_TRIPWIRE = (0, 215, 255)


class SpatialTracker:
    def __init__(self, model=None, zone_pts=None, zone_threshold=4, alert_cooldown=15.0):
        if model is not None:
            self.model = model
        else:
            # Safely locate and load the model
            model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "yolo11n.pt"))
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            try:
                self.model = YOLO(model_path)
            except Exception as e:
                logger.error(f"Error loading YOLO model at {model_path}: {e}")
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

    def process_frame(self, frame):
        persons_count = 0
        vehicles_count = 0
        occupancy_count = 0

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
            }

        try:
            height, width = frame.shape[:2]
            line_y = int(height * 0.55)

            # 1. Run Built-in Tracker (No custom YAML, no class limits)
            active_model = self.model
            if active_model is not None:
                if hasattr(active_model, "track") and callable(getattr(active_model, "track")):
                    track_out = active_model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
                    results = track_out[0] if isinstance(track_out, (list, tuple)) else track_out
                else:
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

                if isinstance(boxes_obj, list):
                    # Handle test mock list of boxes
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

                    conf_arr = boxes_obj.conf
                    if hasattr(conf_arr, "cpu"):
                        confs = conf_arr.cpu().numpy()
                    elif isinstance(conf_arr, (list, tuple)):
                        confs = [c.item() if hasattr(c, "item") and callable(c.item) else c for c in conf_arr]
                    else:
                        confs = np.array(conf_arr)

                    if getattr(boxes_obj, "id", None) is not None:
                        id_arr = boxes_obj.id
                        if hasattr(id_arr, "int"):
                            id_arr = id_arr.int()
                        if hasattr(id_arr, "cpu"):
                            id_arr = id_arr.cpu()
                        track_ids = id_arr.tolist() if hasattr(id_arr, "tolist") else list(id_arr)
                    else:
                        track_ids = [None] * len(boxes)

                for box, cls, conf, track_id in zip(boxes, clss, confs, track_ids):
                    class_id = int(cls.item() if hasattr(cls, "item") else cls)
                    conf_val = float(conf.item() if hasattr(conf, "item") else conf)
                    if conf_val < 0.25:
                        continue

                    # Persons (0) and Vehicles (2, 3, 5, 7)
                    if class_id in [0, 2, 3, 5, 7]:
                        x1, y1, x2, y2 = map(int, box)
                        center_y = (y1 + y2) // 2
                        is_person = (class_id == 0)

                        if is_person:
                            persons_count += 1
                            feet_x = (x1 + x2) // 2
                            feet_y = float(y2)
                            if cv2.pointPolygonTest(self.zone_pts, (float(feet_x), float(feet_y)), False) >= 0:
                                occupancy_count += 1
                        else:
                            vehicles_count += 1

                        # Track ID & Line-Crossing Math
                        tid = None
                        if track_id is not None:
                            tid = int(track_id.item() if hasattr(track_id, "item") else track_id)
                            old_y = self.previous_y.get(tid)
                            if old_y is not None:
                                if old_y < line_y <= center_y:
                                    self.down_count += 1
                                elif old_y > line_y >= center_y:
                                    self.up_count += 1
                            self.previous_y[tid] = center_y

                        parsed_boxes.append((x1, y1, x2, y2, center_y, is_person, tid))

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

            # 3. Minimalist Bounding Boxes (thickness=1, clean IDs, no verbose class/scores)
            for x1, y1, x2, y2, center_y, is_person, tid in parsed_boxes:
                color = (74, 222, 128) if is_person else (255, 215, 0)
                # Bounding box thickness = 1
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)

                if is_person:
                    label = f"ID:{tid}" if tid is not None else "Person"
                    if tid is not None:
                        cv2.circle(frame, ((x1 + x2) // 2, center_y), 3, color, -1)
                else:
                    label = "Vehicle"

                cv2.putText(
                    frame,
                    label,
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

            # 5. Alert Trigger & 15s Cooldown WebSocket Dispatch
            if is_crowded:
                now_ts = time.time()
                if (now_ts - self.last_alert_time) >= self.alert_cooldown:
                    self.last_alert_time = now_ts
                    alert_payload = {
                        "id": f"EVT-CROWD-{int(now_ts)}",
                        "time": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
                        "zone": "Live Monitoring Zone",
                        "type": "ABNORMAL GATHERING",
                        "level": "CRITICAL",
                        "detail": "Occupancy threshold breached (> 3 persons).",
                        "acknowledged": False,
                    }
                    logger.warning(f"WebSocket Alert Fired: {alert_payload}")
                    alert_manager.broadcast_sync(alert_payload)

        except Exception as e:
            logger.error(f"AI Loop Crash: {e}")

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
        }

    def reset(self):
        self.up_count = 0
        self.down_count = 0
        self.entry_count = 0
        self.exit_count = 0
        self.previous_y.clear()
        self.track_history.clear()
        self.last_alert_time = 0.0

