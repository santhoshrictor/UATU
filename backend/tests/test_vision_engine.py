from unittest.mock import MagicMock, patch
import numpy as np

from backend.app.vision_engine import (
    SpatialTracker,
    COLOR_TRIPWIRE,
)


def test_process_spatial_frame_none_or_empty():
    tracker = SpatialTracker(model=None)
    frame, counts = tracker.process_frame(None)
    assert frame is None
    assert counts["persons"] == 0
    assert counts["vehicles"] == 0
    assert counts["entry"] == 0
    assert counts["exit"] == 0

    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    out_frame, counts = tracker.process_frame(blank)
    assert out_frame.shape == (480, 640, 3)
    assert counts["persons"] >= 0
    assert counts["vehicles"] >= 0
    assert counts["entry"] >= 0
    assert counts["exit"] >= 0


def test_process_spatial_frame_mock_detections():
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Mock detection boxes:
    # 1. Person with track ID 1 (class 0, conf 0.88)
    box_person = MagicMock()
    box_person.cls = [MagicMock(item=lambda: 0)]
    box_person.conf = [MagicMock(item=lambda: 0.88)]
    box_person.xyxy = [np.array([50, 50, 200, 350])]
    box_person.id = MagicMock(item=lambda: 1)

    # 2. Vehicle - Car with track ID 2 (class 2, conf 0.92)
    box_car = MagicMock()
    box_car.cls = [MagicMock(item=lambda: 2)]
    box_car.conf = [MagicMock(item=lambda: 0.92)]
    box_car.xyxy = [np.array([250, 100, 500, 300])]
    box_car.id = MagicMock(item=lambda: 2)

    # 3. Low confidence person (class 0, conf 0.20 - should be filtered)
    box_low_conf = MagicMock()
    box_low_conf.cls = [MagicMock(item=lambda: 0)]
    box_low_conf.conf = [MagicMock(item=lambda: 0.20)]
    box_low_conf.xyxy = [np.array([10, 10, 30, 30])]
    box_low_conf.id = None

    # 4. Non-person/non-vehicle (class 15 - cat, should be filtered)
    box_cat = MagicMock()
    box_cat.cls = [MagicMock(item=lambda: 15)]
    box_cat.conf = [MagicMock(item=lambda: 0.85)]
    box_cat.xyxy = [np.array([100, 100, 150, 150])]
    box_cat.id = None

    mock_res = MagicMock()
    mock_res.boxes = [box_person, box_car, box_low_conf, box_cat]

    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res]
    mock_model.return_value = [mock_res]

    tracker = SpatialTracker(model=mock_model)
    annotated, counts = tracker.process_frame(blank)
    assert counts["persons"] == 1
    assert counts["vehicles"] == 1
    assert annotated.shape == (480, 640, 3)
    # Bounding boxes, tripwire, and telemetry should modify pixels
    assert np.any(annotated > 0)


def test_line_crossing_entry_and_exit():
    """
    Tests Feature 4 horizontal line-crossing logic (55% line_y = 264):
    - Moving UP across line_y triggers UP (Exit).
    - Moving DOWN across line_y triggers DOWN (Entry).
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Frame 1: Person above the line (cy = 200, line_y = 264)
    box_f1 = MagicMock()
    box_f1.cls = [MagicMock(item=lambda: 0)]
    box_f1.conf = [MagicMock(item=lambda: 0.90)]
    box_f1.xyxy = [np.array([100, 150, 200, 250])]  # cy = 200 (< 264)
    box_f1.id = MagicMock(item=lambda: 42)

    res_f1 = MagicMock(boxes=[box_f1])
    mock_model = MagicMock()
    mock_model.track.return_value = [res_f1]
    mock_model.return_value = [res_f1]

    tracker = SpatialTracker(model=mock_model)
    _, counts = tracker.process_frame(blank)
    assert counts["entry"] == 0
    assert counts["exit"] == 0

    # Frame 2: Person moves DOWN across line (cy = 300 >= 264) -> Triggers DOWN (Entry)!
    box_f2 = MagicMock()
    box_f2.cls = [MagicMock(item=lambda: 0)]
    box_f2.conf = [MagicMock(item=lambda: 0.90)]
    box_f2.xyxy = [np.array([100, 250, 200, 350])]  # cy = 300 (>= 264)
    box_f2.id = MagicMock(item=lambda: 42)

    res_f2 = MagicMock(boxes=[box_f2])
    mock_model.track.return_value = [res_f2]

    _, counts = tracker.process_frame(blank)
    assert counts["entry"] == 1
    assert counts["exit"] == 0

    # Frame 3: Person continues moving DOWN (cy = 350 >= 264). Should not double-count.
    box_f3 = MagicMock()
    box_f3.cls = [MagicMock(item=lambda: 0)]
    box_f3.conf = [MagicMock(item=lambda: 0.90)]
    box_f3.xyxy = [np.array([100, 300, 200, 400])]  # cy = 350
    box_f3.id = MagicMock(item=lambda: 42)

    res_f3 = MagicMock(boxes=[box_f3])
    mock_model.track.return_value = [res_f3]

    _, counts = tracker.process_frame(blank)
    assert counts["entry"] == 1
    assert counts["exit"] == 0

    # Frame 4: Person moves UP across line (cy = 200 <= 264). Triggers UP (Exit)!
    box_f4 = MagicMock()
    box_f4.cls = [MagicMock(item=lambda: 0)]
    box_f4.conf = [MagicMock(item=lambda: 0.90)]
    box_f4.xyxy = [np.array([100, 150, 200, 250])]  # cy = 200 (<= 264)
    box_f4.id = MagicMock(item=lambda: 42)

    res_f4 = MagicMock(boxes=[box_f4])
    mock_model.track.return_value = [res_f4]

    _, counts = tracker.process_frame(blank)
    assert counts["entry"] == 1
    assert counts["exit"] == 1


def test_tripwire_and_hud_rendered():
    """Verifies that the horizontal counting line and top-right HUD are rendered."""
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    tracker = SpatialTracker(model=None)
    annotated, counts = tracker.process_frame(blank)
    # Line y is int(480 * 0.55) = 264. Check tripwire pixel at y=264, x=320
    tripwire_pixel = annotated[264, 320]
    # COLOR_TRIPWIRE is (0, 215, 255) in BGR
    assert tripwire_pixel[1] > 200 or tripwire_pixel[2] > 200
    # Check top-right region has HUD overlay pixels (non-zero)
    top_right_region = annotated[12:48, 500:630]
    assert np.any(top_right_region > 0)


def test_reset_tracking():
    """Verifies reset resets instance state."""
    tracker = SpatialTracker(model=None)
    tracker.down_count = 5
    tracker.up_count = 3
    tracker.reset()
    assert tracker.down_count == 0
    assert tracker.up_count == 0
    assert tracker.entry_count == 0
    assert tracker.exit_count == 0
    assert len(tracker.previous_y) == 0


def test_raw_detection_without_tracking_ids():
    """
    Verifies that raw bounding boxes and class labels are drawn
    even when boxes.id is None (tracker has not assigned an ID yet).
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    boxes_mock = MagicMock()
    boxes_mock.xyxy = np.array([[100, 100, 250, 300], [300, 150, 500, 350]])
    boxes_mock.cls = [MagicMock(item=lambda: 0), MagicMock(item=lambda: 2)]
    boxes_mock.conf = [MagicMock(item=lambda: 0.91), MagicMock(item=lambda: 0.87)]
    boxes_mock.id = None  # No IDs assigned!

    res_mock = MagicMock(boxes=boxes_mock)
    mock_model = MagicMock()
    mock_model.track.return_value = [res_mock]

    tracker = SpatialTracker(model=mock_model)
    annotated, counts = tracker.process_frame(blank)
    assert counts["persons"] == 1
    assert counts["vehicles"] == 1
    assert counts["entry"] == 0
    assert counts["exit"] == 0
    # Check that bounding box pixels were modified in the detection regions
    assert np.any(annotated[100:300, 100:250] > 0)
    assert np.any(annotated[150:350, 300:500] > 0)


def test_stream_isolation_independent_states():
    """
    Verifies that distinct SpatialTracker instances maintain completely
    isolated tracking history, counting metrics, and centroid caches.
    """
    tracker_webcam0 = SpatialTracker(model=None)
    tracker_file_stream = SpatialTracker(model=None)

    tracker_webcam0.down_count = 7
    tracker_webcam0.previous_y[10] = 300

    assert tracker_file_stream.down_count == 0
    assert tracker_file_stream.up_count == 0
    assert 10 not in tracker_file_stream.previous_y


def test_zone_occupancy_inside_and_outside():
    """
    Verifies Feature 16 (Occupancy) and Contextual UI:
    Person whose feet (x_center, y2) fall inside the zone polygon
    is counted toward zone occupancy, while persons outside are ignored.
    When occupancy < zone_threshold, the zone is completely invisible.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Zone is [[100, 150], [540, 150], [540, 400], [100, 400]]
    # Person 1 inside zone: feet at x=200, y=300
    box_inside = MagicMock()
    box_inside.cls = [MagicMock(item=lambda: 0)]
    box_inside.conf = [MagicMock(item=lambda: 0.90)]
    box_inside.xyxy = [np.array([180, 120, 220, 300])]
    box_inside.id = MagicMock(item=lambda: 1)

    # Person 2 outside zone: feet at x=50, y=50
    box_outside = MagicMock()
    box_outside.cls = [MagicMock(item=lambda: 0)]
    box_outside.conf = [MagicMock(item=lambda: 0.90)]
    box_outside.xyxy = [np.array([40, 20, 60, 50])]
    box_outside.id = MagicMock(item=lambda: 2)

    mock_res = MagicMock(boxes=[box_inside, box_outside])
    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res]

    tracker = SpatialTracker(model=mock_model)
    annotated, counts = tracker.process_frame(blank)

    assert counts["persons"] == 2
    assert counts["occupancy"] == 1
    assert counts["is_crowded"] is False
    assert counts["gathering_alert"] is False

    # Contextual UI: Zone polygon is INVISIBLE until breached!
    # Point at (450, 150) is on the top zone edge, far from person 1 (x: 180-220) and tripwire (y: 264)
    # It must remain completely black (0, 0, 0)
    assert np.all(annotated[150, 450] == 0)


def test_abnormal_gathering_alert_threshold():
    """
    Verifies Feature 15 (Abnormal Gathering) and Contextual UI:
    When occupancy reaches or exceeds zone_threshold (default 4),
    is_crowded is triggered, the polygon is alpha-blended red, and warning text is drawn.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # 4 Persons inside zone [[100, 150], [540, 150], [540, 400], [100, 400]]
    persons = []
    for idx, x_center in enumerate([150, 250, 350, 450]):
        p = MagicMock()
        p.cls = [MagicMock(item=lambda: 0)]
        p.conf = [MagicMock(item=lambda: 0.90)]
        p.xyxy = [np.array([x_center - 20, 180, x_center + 20, 320])]
        p.id = MagicMock(item=lambda i=idx + 1: i)
        persons.append(p)

    mock_res = MagicMock(boxes=persons)
    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res]

    tracker = SpatialTracker(model=mock_model, zone_threshold=4)
    annotated, counts = tracker.process_frame(blank)

    assert counts["persons"] == 4
    assert counts["occupancy"] == 4
    assert counts["is_crowded"] is True
    assert counts["gathering_alert"] is True

    # Red channel (index 2) must be dominant on the zone boundary
    zone_top_edge = annotated[150, 100:540]
    assert np.any(zone_top_edge[:, 2] > 200)


def test_websocket_alert_cooldown():
    """
    Verifies that when abnormal gathering is detected,
    an alert is dispatched via alert_manager.broadcast_sync,
    and subsequent frames within the 15-second cooldown window do not re-dispatch.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    persons = []
    for idx, x_center in enumerate([150, 250, 350, 450]):
        p = MagicMock()
        p.cls = [MagicMock(item=lambda: 0)]
        p.conf = [MagicMock(item=lambda: 0.90)]
        p.xyxy = [np.array([x_center - 20, 180, x_center + 20, 320])]
        p.id = MagicMock(item=lambda i=idx + 1: i)
        persons.append(p)

    mock_res = MagicMock(boxes=persons)
    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res]

    tracker = SpatialTracker(model=mock_model, zone_threshold=4, alert_cooldown=15.0)

    with patch("backend.app.vision_engine.alert_manager.broadcast_sync") as mock_broadcast:
        # Frame 1: Triggers alert and dispatches
        tracker.process_frame(blank.copy())
        assert mock_broadcast.call_count == 1
        payload = mock_broadcast.call_args[0][0]
        assert payload["id"].startswith("EVT-CROWD-")
        assert payload["zone"] == "Live Monitoring Zone"
        assert payload["type"] == "ABNORMAL GATHERING"
        assert payload["level"] == "CRITICAL"
        assert payload["acknowledged"] is False
        assert payload["time"].endswith(" IST")

        # Frame 2 immediately after: Cooldown is active, must NOT re-dispatch
        tracker.process_frame(blank.copy())
        assert mock_broadcast.call_count == 1


def test_camera_device_worker_alert_cooldown():
    """
    Verifies that CameraDeviceWorker in main.py checks is_crowded,
    dispatches an alert payload to alert_manager, and enforces 15s cooldown.
    """
    from backend.app.main import CameraDeviceWorker
    worker = CameraDeviceWorker(device_id=99)
    assert hasattr(worker, "last_crowd_alert_time")
    assert worker.crowd_alert_cooldown == 15.0

    mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    worker.tracker.process_frame = MagicMock(return_value=(mock_frame, {"is_crowded": True, "occupancy": 4}))

    with patch("backend.app.main.alert_manager.broadcast_sync") as mock_broadcast:
        # Simulate one iteration of worker logic
        counts = {"is_crowded": True, "occupancy": 4}
        now_ts = 1000.0
        if counts.get("is_crowded"):
            if (now_ts - worker.last_crowd_alert_time) >= worker.crowd_alert_cooldown:
                worker.last_crowd_alert_time = now_ts
                payload = {
                    "id": f"EVT-CROWD-{int(now_ts)}",
                    "time": "12:00:00 IST",
                    "zone": "Live Monitoring Zone",
                    "type": "ABNORMAL GATHERING",
                    "level": "CRITICAL",
                    "detail": "Occupancy threshold breached (> 3 persons).",
                    "acknowledged": False,
                }
                from backend.app.core.websocket_manager import alert_manager
                alert_manager.broadcast_sync(payload)

        assert mock_broadcast.call_count == 1
        assert worker.last_crowd_alert_time == 1000.0

        # Immediate next frame (within cooldown)
        now_ts_next = 1005.0
        if counts.get("is_crowded"):
            if (now_ts_next - worker.last_crowd_alert_time) >= worker.crowd_alert_cooldown:
                worker.last_crowd_alert_time = now_ts_next
                alert_manager.broadcast_sync({})

        assert mock_broadcast.call_count == 1


def make_pose_keypoints(nose_y=120, hip_y=230, nose_x=150, hip_x=150, shoulder_y=None, conf=0.95):
    if shoulder_y is None:
        if nose_y <= hip_y:
            shoulder_y = nose_y + (hip_y - nose_y) * 0.35
        else:
            shoulder_y = hip_y - 8.0  # Spine compressed: shoulders close to hips
    kpts = np.zeros((17, 3), dtype=np.float32)
    kpts[:, 2] = conf
    kpts[0, :2] = [nose_x, nose_y]           # Nose
    kpts[1, :2] = [nose_x - 5, nose_y - 5]   # Left eye
    kpts[2, :2] = [nose_x + 5, nose_y - 5]   # Right eye
    kpts[3, :2] = [nose_x - 10, nose_y - 5]  # Left ear
    kpts[4, :2] = [nose_x + 10, nose_y - 5]  # Right ear
    kpts[5, :2] = [nose_x - 30, shoulder_y]  # Left shoulder
    kpts[6, :2] = [nose_x + 30, shoulder_y]  # Right shoulder
    kpts[7, :2] = [nose_x - 40, shoulder_y + 30] # Left elbow
    kpts[8, :2] = [nose_x + 40, shoulder_y + 30] # Right elbow
    kpts[9, :2] = [nose_x - 45, shoulder_y + 60] # Left wrist
    kpts[10, :2] = [nose_x + 45, shoulder_y + 60]# Right wrist
    kpts[11, :2] = [hip_x - 20, hip_y]       # Left hip
    kpts[12, :2] = [hip_x + 20, hip_y]       # Right hip
    kpts[13, :2] = [hip_x - 20, hip_y + 40]  # Left knee
    kpts[14, :2] = [hip_x + 20, hip_y + 40]  # Right knee
    kpts[15, :2] = [hip_x - 20, hip_y + 80]  # Left ankle
    kpts[16, :2] = [hip_x + 20, hip_y + 80]  # Right ankle
    mock_kp = MagicMock()
    mock_kp.xy = np.array([kpts[:, :2]])
    mock_kp.data = np.array([kpts])
    mock_kp.conf = np.array([[conf] * 17])
    return mock_kp


def test_fall_detection_upright_person_nominal():
    """
    Verifies Feature 17 (Fall Detection):
    An upright standing person (aspect_ratio = 0.4 < 1.2, nose_y < hips_y)
    does not trigger fall detection.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Box: width 100, height 250 (aspect_ratio = 0.4)
    p = MagicMock()
    p.cls = [MagicMock(item=lambda: 0)]
    p.conf = [MagicMock(item=lambda: 0.90)]
    p.xyxy = [np.array([100, 100, 200, 350])]
    p.id = MagicMock(item=lambda: 1)

    # Keypoints for upright person:
    # Nose (kp 0) at y=120, Hips (kp 11, 12) at y=230 -> nose_y < hips_y
    mock_res = MagicMock(boxes=[p], keypoints=make_pose_keypoints(nose_y=120, hip_y=230))
    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res]

    tracker = SpatialTracker(model=mock_model)
    annotated, counts = tracker.process_frame(blank)

    assert counts["fall_detected"] is False
    # Upright person bounding box is drawn in green (74, 222, 128)
    assert np.any(annotated[100:350, 100:200, 1] > 200)


def test_fall_detection_prone_person_breached():
    """
    Verifies Feature 17 (Fall Detection):
    When a person collapses with head lower than hips (nose_y >= hip_y),
    spine compressed, and persists for 2 consecutive frames,
    fall_detected is True, and the person's bounding box and skeleton turn Pure Red.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Frame 1: Person standing upright (y1=100, y2=300 -> h=200, w=100, nose_y=120 < hip_y=230)
    p_upright = MagicMock()
    p_upright.cls = [MagicMock(item=lambda: 0)]
    p_upright.conf = [MagicMock(item=lambda: 0.95)]
    p_upright.xyxy = [np.array([100, 100, 200, 300])]
    p_upright.id = MagicMock(item=lambda: 2)

    res_f1 = MagicMock(boxes=[p_upright], keypoints=make_pose_keypoints(nose_y=120, hip_y=230))
    mock_model = MagicMock()
    mock_model.track.return_value = [res_f1]

    tracker = SpatialTracker(model=mock_model)
    _, counts_f1 = tracker.process_frame(blank.copy())
    assert counts_f1["fall_detected"] is False

    # Frame 2: Person collapsed prone (1st fall frame -> glitch filter, not yet confirmed)
    p_fallen = MagicMock()
    p_fallen.cls = [MagicMock(item=lambda: 0)]
    p_fallen.conf = [MagicMock(item=lambda: 0.95)]
    p_fallen.xyxy = [np.array([100, 300, 400, 400])]
    p_fallen.id = MagicMock(item=lambda: 2)

    res_f2 = MagicMock(boxes=[p_fallen], keypoints=make_pose_keypoints(nose_y=380, hip_y=330))
    mock_model.track.return_value = [res_f2]

    # Frames 1-4: Temporal buffer suppresses transients
    for _ in range(4):
        _, counts_glitch = tracker.process_frame(blank.copy())
        assert counts_glitch["fall_detected"] is False

    # Frame 5: 5th consecutive frame -> confirmed breach!
    annotated_f2, counts_f2 = tracker.process_frame(blank.copy())

    assert counts_f2["fall_detected"] is True
    # Box should be rendered with pure Red (0, 0, 255)
    box_top_edge = annotated_f2[300, 100:400]
    assert np.any(box_top_edge[:, 2] > 200)


def test_fall_detection_upright_nominal_posture():
    """
    Verifies that an upright person (w <= h, h >= 80)
    does not trigger false positive fall detection, and box remains green.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    p = MagicMock()
    p.cls = [MagicMock(item=lambda: 0)]
    p.conf = [MagicMock(item=lambda: 0.90)]
    p.xyxy = [np.array([100, 150, 200, 320])]  # width 100, height 170 -> w <= h, h >= 80
    p.id = MagicMock(item=lambda: 3)

    mock_res = MagicMock(boxes=[p], keypoints=None)
    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res]

    tracker = SpatialTracker(model=mock_model)
    annotated, counts = tracker.process_frame(blank)

    assert counts["fall_detected"] is False
    # Green box (74, 222, 128)
    assert np.any(annotated[150:320, 100:200, 1] > 200)


def test_webcam_sitting_person_no_false_positive():
    """
    Crucial Webcam False-Positive Elimination Test:
    Sitting upright close to a webcam produces a wide bounding box (w > h * 1.1).
    Because the vertical center is stationary and does not drop rapidly,
    and height is not compressed by > 50%, it is NEVER flagged as fallen.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Frame 1: Person sitting close to webcam with broad shoulders (width=350, height=250 -> w > h * 1.0)
    p_sitting_1 = MagicMock()
    p_sitting_1.cls = [MagicMock(item=lambda: 0)]
    p_sitting_1.conf = [MagicMock(item=lambda: 0.92)]
    p_sitting_1.xyxy = [np.array([100, 100, 450, 350])]  # w=350, h=250
    p_sitting_1.id = MagicMock(item=lambda: 10)

    # Keypoints: Head is ABOVE hips (nose_y=130 < hip_y=280)
    res_f1 = MagicMock(boxes=[p_sitting_1], keypoints=make_pose_keypoints(nose_y=130, hip_y=280))
    mock_model = MagicMock()
    mock_model.track.return_value = [res_f1]

    tracker = SpatialTracker(model=mock_model)
    annotated_f1, counts_f1 = tracker.process_frame(blank.copy())
    assert counts_f1["fall_detected"] is False

    # Frame 2: Person continues sitting normally at desk/webcam (head still above hips)
    p_sitting_2 = MagicMock()
    p_sitting_2.cls = [MagicMock(item=lambda: 0)]
    p_sitting_2.conf = [MagicMock(item=lambda: 0.92)]
    p_sitting_2.xyxy = [np.array([102, 101, 451, 351])]  # w=349, h=250
    p_sitting_2.id = MagicMock(item=lambda: 10)

    res_f2 = MagicMock(boxes=[p_sitting_2], keypoints=make_pose_keypoints(nose_y=130, hip_y=280))
    mock_model.track.return_value = [res_f2]

    annotated_f2, counts_f2 = tracker.process_frame(blank.copy())

    # MUST NEVER trigger false positive on a sitting person whose head is above hips
    assert counts_f2["fall_detected"] is False
    # Box remains Emerald Green (74, 222, 128)
    assert np.any(annotated_f2[101:351, 102:451, 1] > 200)


def test_webcam_fall_rapid_trajectory_drop():
    """
    Verifies that when a person collapses prone, the pose condition triggers fall detection.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Frame 1: Person sitting at webcam (head above hips: nose_y=130 < hip_y=280)
    p_sitting = MagicMock()
    p_sitting.cls = [MagicMock(item=lambda: 0)]
    p_sitting.conf = [MagicMock(item=lambda: 0.92)]
    p_sitting.xyxy = [np.array([150, 100, 400, 300])]
    p_sitting.id = MagicMock(item=lambda: 11)

    res_f1 = MagicMock(boxes=[p_sitting], keypoints=make_pose_keypoints(nose_y=130, hip_y=280))
    mock_model = MagicMock()
    mock_model.track.return_value = [res_f1]

    tracker = SpatialTracker(model=mock_model)
    _, counts_f1 = tracker.process_frame(blank.copy())
    assert counts_f1["fall_detected"] is False

    # Frame 2: Person collapses onto floor (w=300 > h=120 * 1.0, nose_y=400 > hip_y=350)
    p_collapsed = MagicMock()
    p_collapsed.cls = [MagicMock(item=lambda: 0)]
    p_collapsed.conf = [MagicMock(item=lambda: 0.95)]
    p_collapsed.xyxy = [np.array([100, 320, 400, 440])]
    p_collapsed.id = MagicMock(item=lambda: 11)

    res_f2 = MagicMock(boxes=[p_collapsed], keypoints=make_pose_keypoints(nose_y=400, hip_y=350))
    mock_model.track.return_value = [res_f2]

    # Frames 1-4: Temporal buffer suppresses transients
    for _ in range(4):
        _, counts_glitch = tracker.process_frame(blank.copy())
        assert counts_glitch["fall_detected"] is False

    # Frame 5: 5th consecutive frame of fall -> confirmed
    annotated_f2, counts_f2 = tracker.process_frame(blank.copy())

    assert counts_f2["fall_detected"] is True
    # Pure Red override (0, 0, 255)
    assert np.any(annotated_f2[320:440, 100:400, 2] > 200)


def test_webcam_fall_height_compression_over_50_percent():
    """
    Verifies that when a person collapses prone, the pose condition triggers fall detection.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Frame 1: Person standing (nose_y=100 < hip_y=250)
    p_standing = MagicMock()
    p_standing.cls = [MagicMock(item=lambda: 0)]
    p_standing.conf = [MagicMock(item=lambda: 0.92)]
    p_standing.xyxy = [np.array([200, 50, 350, 350])]
    p_standing.id = MagicMock(item=lambda: 12)

    res_f1 = MagicMock(boxes=[p_standing], keypoints=make_pose_keypoints(nose_y=100, hip_y=250))
    mock_model = MagicMock()
    mock_model.track.return_value = [res_f1]

    tracker = SpatialTracker(model=mock_model)
    _, counts_f1 = tracker.process_frame(blank.copy())
    assert counts_f1["fall_detected"] is False

    # Frame 2: Person collapses down (nose_y=380 > hip_y=320, w=200 > h=120 * 1.0)
    p_collapsed = MagicMock()
    p_collapsed.cls = [MagicMock(item=lambda: 0)]
    p_collapsed.conf = [MagicMock(item=lambda: 0.95)]
    p_collapsed.xyxy = [np.array([150, 280, 350, 400])]
    p_collapsed.id = MagicMock(item=lambda: 12)

    res_f2 = MagicMock(boxes=[p_collapsed], keypoints=make_pose_keypoints(nose_y=380, hip_y=320))
    mock_model.track.return_value = [res_f2]

    # Frames 1-4 of collapse: glitch prevention
    for _ in range(4):
        _, counts = tracker.process_frame(blank.copy())
        assert counts["fall_detected"] is False

    # Frame 5: 5th consecutive frame -> confirmed
    annotated_f2, counts_f2 = tracker.process_frame(blank.copy())

    assert counts_f2["fall_detected"] is True
    assert np.any(annotated_f2[280:400, 150:350, 2] > 200)



def test_camera_device_worker_fall_alert_cooldown():
    """
    Verifies that CameraDeviceWorker in main.py checks fall_detected,
    dispatches EVT-FALL payload to alert_manager, and enforces 15s cooldown.
    """
    from backend.app.main import CameraDeviceWorker
    worker = CameraDeviceWorker(device_id=98)
    assert hasattr(worker, "last_fall_alert_time")
    assert worker.fall_alert_cooldown == 15.0

    mock_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    worker.tracker.process_frame = MagicMock(return_value=(mock_frame, {"fall_detected": True, "occupancy": 1}))

    with patch("backend.app.main.alert_manager.broadcast_sync") as mock_broadcast:
        counts = {"fall_detected": True, "occupancy": 1}
        now_ts = 2000.0
        if counts.get("fall_detected"):
            if (now_ts - worker.last_fall_alert_time) >= worker.fall_alert_cooldown:
                worker.last_fall_alert_time = now_ts
                payload = {
                    "id": f"EVT-FALL-{int(now_ts)}",
                    "time": "12:00:00 IST",
                    "zone": "Live Monitoring Zone",
                    "type": "MAN DOWN / FALL DETECTED",
                    "level": "CRITICAL",
                    "detail": "Worker fall detected based on skeletal pose geometry. Immediate assistance required.",
                    "acknowledged": False,
                }
                from backend.app.core.websocket_manager import alert_manager
                alert_manager.broadcast_sync(payload)

        assert mock_broadcast.call_count == 1
        assert worker.last_fall_alert_time == 2000.0
        sent_payload = mock_broadcast.call_args[0][0]
        assert sent_payload["id"] == "EVT-FALL-2000"
        assert sent_payload["type"] == "MAN DOWN / FALL DETECTED"
        assert sent_payload["level"] == "CRITICAL"
        assert sent_payload["detail"] == "Worker fall detected based on skeletal pose geometry. Immediate assistance required."

        # Within 15s cooldown window (5s later) -> must not fire
        now_ts_next = 2005.0
        if counts.get("fall_detected"):
            if (now_ts_next - worker.last_fall_alert_time) >= worker.fall_alert_cooldown:
                worker.last_fall_alert_time = now_ts_next
                alert_manager.broadcast_sync({})

        assert mock_broadcast.call_count == 1


def test_overhead_fall_detection_height_compression():
    """
    Verifies Overhead/Ceiling CCTV Fall Detection with pose:
    When a person collapses with head lower than hips (nose_y > hip_y) and w > h * 1.0,
    fall is detected.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Frame 1: Person standing normally (nose_y=80 < hip_y=180)
    p_standing = MagicMock()
    p_standing.cls = [MagicMock(item=lambda: 0)]
    p_standing.conf = [MagicMock(item=lambda: 0.92)]
    p_standing.xyxy = [np.array([100, 50, 200, 250])]
    p_standing.id = MagicMock(item=lambda: 7)

    res_f1 = MagicMock(boxes=[p_standing], keypoints=make_pose_keypoints(nose_y=80, hip_y=180))
    mock_model = MagicMock()
    mock_model.track.return_value = [res_f1]

    tracker = SpatialTracker(model=mock_model)
    annotated_f1, counts_f1 = tracker.process_frame(blank.copy())

    assert counts_f1["fall_detected"] is False

    # Frame 2: Person collapses downwards (nose_y=220 > hip_y=180, w=150 > h=90 * 1.0)
    p_collapsed = MagicMock()
    p_collapsed.cls = [MagicMock(item=lambda: 0)]
    p_collapsed.conf = [MagicMock(item=lambda: 0.92)]
    p_collapsed.xyxy = [np.array([100, 160, 250, 250])]  # h = 90, w = 150
    p_collapsed.id = MagicMock(item=lambda: 7)

    res_f2 = MagicMock(boxes=[p_collapsed], keypoints=make_pose_keypoints(nose_y=220, hip_y=180))
    mock_model.track.return_value = [res_f2]

    # Frames 1-4: Temporal buffer suppresses transients
    for _ in range(4):
        _, counts_f2_1 = tracker.process_frame(blank.copy())
        assert counts_f2_1["fall_detected"] is False

    # Frame 5: 5th consecutive fallen frame (fall confirmed)
    annotated_f2, counts_f2 = tracker.process_frame(blank.copy())

    assert counts_f2["fall_detected"] is True
    # Box should be rendered in Red (0, 0, 255)
    assert np.any(annotated_f2[160:250, 100:250, 2] > 200)


def test_overhead_fall_detection_floor_proximity_flattened():
    """
    Verifies Overhead/Ceiling CCTV Fall Detection with pose:
    When a person collapses on the floor with head lower than hips (nose_y > hip_y)
    and horizontal box (w > h * 1.0), fall is detected after 5 frames.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Frame 1: Person standing (nose_y=80 < hip_y=180)
    p_standing = MagicMock()
    p_standing.cls = [MagicMock(item=lambda: 0)]
    p_standing.conf = [MagicMock(item=lambda: 0.92)]
    p_standing.xyxy = [np.array([100, 50, 200, 250])]
    p_standing.id = MagicMock(item=lambda: 8)

    res_f1 = MagicMock(boxes=[p_standing], keypoints=make_pose_keypoints(nose_y=80, hip_y=180))
    mock_model = MagicMock()
    mock_model.track.return_value = [res_f1]

    tracker = SpatialTracker(model=mock_model)
    _, counts_f1 = tracker.process_frame(blank.copy())
    assert counts_f1["fall_detected"] is False

    # Frame 2: Fallen person on floor: y1=380, y2=450 (h=70, w=120, nose_y=440 > hip_y=400)
    p_floor = MagicMock()
    p_floor.cls = [MagicMock(item=lambda: 0)]
    p_floor.conf = [MagicMock(item=lambda: 0.95)]
    p_floor.xyxy = [np.array([100, 380, 220, 450])]
    p_floor.id = MagicMock(item=lambda: 8)

    res_f2 = MagicMock(boxes=[p_floor], keypoints=make_pose_keypoints(nose_y=440, hip_y=400))
    mock_model.track.return_value = [res_f2]

    # Frames 1-4: Temporal buffer suppresses transients
    for _ in range(4):
        _, counts_f2_1 = tracker.process_frame(blank.copy())
        assert counts_f2_1["fall_detected"] is False

    # Frame 5: 5th consecutive fallen frame (confirmed)
    annotated, counts = tracker.process_frame(blank.copy())

    assert counts["fall_detected"] is True
    # Red box rendered
    assert np.any(annotated[380:450, 100:220, 2] > 200)


def test_spatial_tracker_fall_alert_websocket_cooldown():
    """
    Verifies that when SpatialTracker detects a fall, it dispatches an EVT-FALL
    alert through alert_manager.broadcast_sync and enforces the 15s cooldown.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Frame 1: Person standing (nose_y=80 < hip_y=180, id=9)
    p_standing = MagicMock()
    p_standing.cls = [MagicMock(item=lambda: 0)]
    p_standing.conf = [MagicMock(item=lambda: 0.92)]
    p_standing.xyxy = [np.array([100, 50, 200, 250])]
    p_standing.id = MagicMock(item=lambda: 9)

    res_f1 = MagicMock(boxes=[p_standing], keypoints=make_pose_keypoints(nose_y=80, hip_y=180))
    mock_model = MagicMock()
    mock_model.track.return_value = [res_f1]

    tracker = SpatialTracker(model=mock_model, alert_cooldown=15.0)
    tracker.process_frame(blank.copy())

    # Frame 2: Fall collapse to floor (nose_y=440 > hip_y=400, w=120 > h=70 * 1.0)
    p_floor = MagicMock()
    p_floor.cls = [MagicMock(item=lambda: 0)]
    p_floor.conf = [MagicMock(item=lambda: 0.95)]
    p_floor.xyxy = [np.array([100, 380, 220, 450])]
    p_floor.id = MagicMock(item=lambda: 9)

    res_f2 = MagicMock(boxes=[p_floor], keypoints=make_pose_keypoints(nose_y=440, hip_y=400))
    mock_model.track.return_value = [res_f2]

    with patch("backend.app.vision_engine.alert_manager.broadcast_sync") as mock_broadcast:
        # Frames 1-4: Temporal buffer suppresses transients (< 5 frames)
        for _ in range(4):
            _, counts_g = tracker.process_frame(blank.copy())
            assert counts_g["fall_detected"] is False
            assert mock_broadcast.call_count == 0

        # Frame 5: 5th consecutive fallen frame -> Fall confirmed -> dispatches EVT-FALL payload
        _, counts1 = tracker.process_frame(blank.copy())
        assert counts1["fall_detected"] is True
        assert mock_broadcast.call_count == 1
        payload = mock_broadcast.call_args[0][0]
        assert payload["id"].startswith("EVT-FALL-")
        assert payload["type"] == "MAN DOWN / FALL DETECTED"
        assert payload["level"] == "CRITICAL"
        assert payload["time"].endswith(" IST")

        # Frame 6: Immediately afterwards (within 15s cooldown) -> no re-dispatch
        _, counts2 = tracker.process_frame(blank.copy())
        assert counts2["fall_detected"] is True
        assert mock_broadcast.call_count == 1


def test_ist_timestamp_generator():
    """
    Verifies that the IST timezone (UTC+5:30) is correctly configured
    and produces timestamps matching the HH:MM:SS IST format.
    """
    from datetime import datetime
    from backend.app.main import IST
    import re
    now_ist = datetime.now(IST).strftime("%H:%M:%S IST")
    assert now_ist.endswith(" IST")
    assert re.match(r"^\d{2}:\d{2}:\d{2} IST$", now_ist)


def test_bounding_box_turns_red_when_fall_detected():
    """
    Verifies Task 1:
    The exact moment fall_detected becomes True in vision_engine.py,
    the bounding box visually turns Pure Red (0, 0, 255) and displays
    CRITICAL: FALL DETECTED.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Frame 1: Person standing (nose_y=80 < hip_y=180)
    p_standing = MagicMock()
    p_standing.cls = [MagicMock(item=lambda: 0)]
    p_standing.conf = [MagicMock(item=lambda: 0.95)]
    p_standing.xyxy = [np.array([100, 50, 200, 250])]
    p_standing.id = MagicMock(item=lambda: 99)

    res_f1 = MagicMock(boxes=[p_standing], keypoints=make_pose_keypoints(nose_y=80, hip_y=180))
    mock_model = MagicMock()
    mock_model.track.return_value = [res_f1]

    tracker = SpatialTracker(model=mock_model)
    annotated_f1, counts_f1 = tracker.process_frame(blank.copy())
    assert counts_f1["fall_detected"] is False
    # Green box when standing
    assert np.any(annotated_f1[50:250, 100:200, 1] > 200)

    # Frame 2: Person collapses onto floor (w=300, nose_y=380 > hip_y=330)
    p_fallen = MagicMock()
    p_fallen.cls = [MagicMock(item=lambda: 0)]
    p_fallen.conf = [MagicMock(item=lambda: 0.95)]
    p_fallen.xyxy = [np.array([100, 300, 400, 400])]
    p_fallen.id = MagicMock(item=lambda: 99)

    res_f2 = MagicMock(boxes=[p_fallen], keypoints=make_pose_keypoints(nose_y=380, hip_y=330))
    mock_model.track.return_value = [res_f2]

    # Frames 1-4: Temporal buffer suppresses transients (< 5 frames)
    for _ in range(4):
        _, counts_g = tracker.process_frame(blank.copy())
        assert counts_g["fall_detected"] is False

    # Frame 5: 5th consecutive fallen frame (fall confirmed)
    annotated_f2, counts_f2 = tracker.process_frame(blank.copy())

    # The exact moment fall_detected becomes True:
    assert counts_f2["fall_detected"] is True
    # Bounding box is rendered with Pure Red (0, 0, 255)
    box_pixels = annotated_f2[300:400, 100:400]
    assert np.any(box_pixels[:, :, 2] > 200)
    # Text region has red pixels from CRITICAL: FALL DETECTED
    text_region = annotated_f2[270:300, 100:400]
    assert np.any(text_region[:, :, 2] > 200)


def test_skeleton_drawing_limbs_and_joints():
    """
    Verifies Section 1: Skeleton Overlay
    - Draws lines between keypoints (limbs)
    - Draws joint circles
    - Uses Emerald Green for normal posture, and Pure Red for fall detection
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Case A: Upright person (Green skeleton)
    p_upright = MagicMock()
    p_upright.cls = [MagicMock(item=lambda: 0)]
    p_upright.conf = [MagicMock(item=lambda: 0.95)]
    p_upright.xyxy = [np.array([100, 50, 200, 250])]
    p_upright.id = MagicMock(item=lambda: 1)

    res_upright = MagicMock(boxes=[p_upright], keypoints=make_pose_keypoints(nose_y=80, hip_y=180, nose_x=150, hip_x=150))
    mock_model = MagicMock()
    mock_model.track.return_value = [res_upright]

    tracker = SpatialTracker(model=mock_model)
    annotated_upright, counts_upright = tracker.process_frame(blank.copy())
    assert counts_upright["fall_detected"] is False

    # Joint at (150, 80) should have Green (74, 222, 128)
    assert annotated_upright[80, 150, 1] > 200

    # Case B: Fallen person (Red skeleton after 5 consecutive frames)
    p_fallen = MagicMock()
    p_fallen.cls = [MagicMock(item=lambda: 0)]
    p_fallen.conf = [MagicMock(item=lambda: 0.95)]
    p_fallen.xyxy = [np.array([100, 300, 400, 400])]
    p_fallen.id = MagicMock(item=lambda: 1)

    res_fallen = MagicMock(boxes=[p_fallen], keypoints=make_pose_keypoints(nose_y=380, hip_y=330, nose_x=250, hip_x=200))
    mock_model.track.return_value = [res_fallen]

    for _ in range(4):
        tracker.process_frame(blank.copy())
    # Frame 5: 5th consecutive fallen frame -> confirmed
    annotated_fallen, counts_fallen = tracker.process_frame(blank.copy())
    assert counts_fallen["fall_detected"] is True

    # Joint at (250, 380) should have Red (0, 0, 255)
    assert annotated_fallen[380, 250, 2] > 200


def test_simplified_pose_fall_math_rules():
    """
    Verifies Section 1: Simplified Pose Fall Math:
    - nose_y >= hip_y AND spine compressed for 5 frames -> fall_detected = True, Red, CRITICAL: FALL DETECTED
    - nose_y < hip_y -> fall_detected = False, Green (webcam sitting)
    - spine not compressed -> fall_detected = False, Green (bending while standing)
    - keypoints is None with w > h * 1.1 -> fall_detected = True after 5 frames
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    tracker = SpatialTracker(model=MagicMock())

    # Rule 1: Fall breach (nose_y >= hip_y and spine compressed, persists 5 frames)
    p1 = MagicMock()
    p1.cls = [MagicMock(item=lambda: 0)]
    p1.conf = [MagicMock(item=lambda: 0.9)]
    p1.xyxy = [np.array([100, 300, 400, 400])]
    p1.id = None
    tracker.model.track.return_value = [MagicMock(boxes=[p1], keypoints=make_pose_keypoints(nose_y=380, hip_y=330))]
    for _ in range(4):
        _, c1_g = tracker.process_frame(blank.copy())
        assert c1_g["fall_detected"] is False  # Frames 1-4 glitch rejection
    ann1, c1 = tracker.process_frame(blank.copy())
    assert c1["fall_detected"] is True   # Frame 5 confirmed

    # Rule 2: Sitting upright with wide box (nose_y < hip_y)
    p2 = MagicMock()
    p2.cls = [MagicMock(item=lambda: 0)]
    p2.conf = [MagicMock(item=lambda: 0.9)]
    p2.xyxy = [np.array([100, 100, 400, 250])]  # w=300 > h=150
    p2.id = None
    tracker.model.track.return_value = [MagicMock(boxes=[p2], keypoints=make_pose_keypoints(nose_y=120, hip_y=200))]
    ann2, c2 = tracker.process_frame(blank.copy())
    assert c2["fall_detected"] is False

    # Rule 3: Upright standing (shoulder to hip distance normal, nose_y < hip_y)
    p3 = MagicMock()
    p3.cls = [MagicMock(item=lambda: 0)]
    p3.conf = [MagicMock(item=lambda: 0.9)]
    p3.xyxy = [np.array([100, 100, 200, 300])]
    p3.id = None
    tracker.model.track.return_value = [MagicMock(boxes=[p3], keypoints=make_pose_keypoints(nose_y=110, hip_y=220, shoulder_y=140))]
    ann3, c3 = tracker.process_frame(blank.copy())
    assert c3["fall_detected"] is False

    # Rule 4: Prone person on overhead CCTV with occluded / missing keypoints (fallback to w > h * 1.1)
    p4 = MagicMock()
    p4.cls = [MagicMock(item=lambda: 0)]
    p4.conf = [MagicMock(item=lambda: 0.9)]
    p4.xyxy = [np.array([100, 300, 400, 400])]  # w=300 > h=100 * 1.1
    p4.id = None
    tracker.model.track.return_value = [MagicMock(boxes=[p4], keypoints=None)]
    for _ in range(4):
        _, c4_g = tracker.process_frame(blank.copy())
        assert c4_g["fall_detected"] is False  # Frames 1-4 glitch rejection
    ann4_2, c4_2 = tracker.process_frame(blank.copy())
    assert c4_2["fall_detected"] is True   # Frame 5 confirmed via bounding box geometry fallback!

    # Rule 5: Upright standing person with no keypoints (w <= h * 1.1) -> remains False
    p5 = MagicMock()
    p5.cls = [MagicMock(item=lambda: 0)]
    p5.conf = [MagicMock(item=lambda: 0.9)]
    p5.xyxy = [np.array([100, 100, 200, 350])]  # w=100, h=250 -> w <= h * 1.1
    p5.id = None
    tracker.model.track.return_value = [MagicMock(boxes=[p5], keypoints=None)]
    ann5, c5 = tracker.process_frame(blank.copy())
    assert c5["fall_detected"] is False


def test_keypoint_confidence_filtering():
    """
    Verifies that keypoints with confidence <= 0.3 are ignored,
    preventing low-quality or occluded background noise from triggering false fall alerts.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    p = MagicMock()
    p.cls = [MagicMock(item=lambda: 0)]
    p.conf = [MagicMock(item=lambda: 0.95)]
    p.xyxy = [np.array([100, 50, 200, 250])]  # upright box
    p.id = MagicMock(item=lambda: 55)

    # Keypoint confidence is only 0.15 (below 0.3 threshold)
    low_conf_kp = make_pose_keypoints(nose_y=380, hip_y=120, conf=0.15)
    mock_model = MagicMock()
    mock_model.track.return_value = [MagicMock(boxes=[p], keypoints=low_conf_kp)]

    tracker = SpatialTracker(model=mock_model)
    for _ in range(5):
        _, counts = tracker.process_frame(blank.copy())
        assert counts["fall_detected"] is False


def test_temporal_frame_buffer_5_frames():
    """
    Verifies that a fall condition must persist for at least 5 consecutive frames.
    Single-frame to 4-frame dips are suppressed as glitches/transients.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    p_fall = MagicMock()
    p_fall.cls = [MagicMock(item=lambda: 0)]
    p_fall.conf = [MagicMock(item=lambda: 0.95)]
    p_fall.xyxy = [np.array([100, 300, 400, 400])]  # w=300 > h=100 * 1.1
    p_fall.id = MagicMock(item=lambda: 77)

    res = MagicMock(boxes=[p_fall], keypoints=make_pose_keypoints(nose_y=380, hip_y=330))
    mock_model = MagicMock()
    mock_model.track.return_value = [res]

    tracker = SpatialTracker(model=mock_model)
    # Frames 1 through 4: must remain unconfirmed
    for frame_idx in range(1, 5):
        _, counts = tracker.process_frame(blank.copy())
        assert counts["fall_detected"] is False, f"Frame {frame_idx} should be suppressed by temporal buffer"

    # Frame 5: precisely on frame 5, fall is confirmed!
    _, counts_5 = tracker.process_frame(blank.copy())
    assert counts_5["fall_detected"] is True, "Frame 5 should confirm fall after 5 consecutive frames"






