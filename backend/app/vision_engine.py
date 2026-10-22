import cv2
import os
import logging
import numpy as np
from ultralytics import YOLO

logger = logging.getLogger(__name__)

COLOR_TRIPWIRE = (0, 215, 255)


class SpatialTracker:
    def __init__(self, model=None):
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

    def process_frame(self, frame):
        persons_count = 0
        vehicles_count = 0

        if frame is None or not isinstance(frame, np.ndarray):
            return frame, {
                "entry": self.down_count,
                "exit": self.up_count,
                "persons": 0,
                "vehicles": 0,
            }

        try:
            height, width = frame.shape[:2]
            line_y = int(height * 0.55)

            # 1. Draw Tripwire First
            cv2.line(frame, (0, line_y), (width, line_y), (0, 215, 255), 2)
            cv2.putText(frame, "UATU TRIPWIRE", (10, line_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 215, 255), 2)

            # 2. Run Built-in Tracker (No custom YAML, no class limits)
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
                        if class_id == 0:
                            persons_count += 1
                        else:
                            vehicles_count += 1

                        x1, y1, x2, y2 = map(int, box)
                        center_y = (y1 + y2) // 2

                        is_person = (class_id == 0)
                        color = (74, 222, 128) if is_person else (255, 215, 0)
                        label = f"{'Person' if is_person else 'Vehicle'} {conf_val:.2f}"

                        # ALWAYS draw the raw bounding box
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                        # Apply Tracker ID & Math ONLY if tracker is locked on
                        if track_id is not None:
                            tid = int(track_id.item() if hasattr(track_id, "item") else track_id)
                            label += f" | ID:{tid}"
                            cv2.circle(frame, ((x1 + x2) // 2, center_y), 4, color, -1)

                            old_y = self.previous_y.get(tid)
                            if old_y is not None:
                                if old_y < line_y <= center_y:
                                    self.down_count += 1
                                elif old_y > line_y >= center_y:
                                    self.up_count += 1
                            self.previous_y[tid] = center_y

                        cv2.putText(frame, label, (x1, max(15, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # 3. Draw Clean Telemetry Box
            cv2.rectangle(frame, (frame.shape[1] - 220, 10), (frame.shape[1] - 10, 50), (15, 23, 42), -1)
            cv2.putText(
                frame,
                f"ENTRY: {self.down_count} | EXIT: {self.up_count}",
                (frame.shape[1] - 210, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

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
        }


    def reset(self):
        self.up_count = 0
        self.down_count = 0
        self.entry_count = 0
        self.exit_count = 0
        self.previous_y.clear()
        self.track_history.clear()
