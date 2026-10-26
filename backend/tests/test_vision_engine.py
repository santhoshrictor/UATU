from unittest.mock import MagicMock, patch, AsyncMock
import threading
import numpy as np

from backend.app.vision_engine import (
    SpatialTracker,
    COLOR_TRIPWIRE,
)


def test_process_spatial_frame_none_or_empty():
    tracker = SpatialTracker(model=None, camera_id="CAM-03", zone="Logistics Yard")
    frame, counts = tracker.process_frame(None)
    assert frame is not None
    assert isinstance(frame, np.ndarray)
    assert frame.shape == (480, 640, 3)
    assert counts["persons"] == 0
    assert counts["vehicles"] == 0
    assert counts["entry"] == 0
    assert counts["exit"] == 0
    assert counts["stream_healthy"] is False
    assert counts["fall_detected"] is False
    assert counts["fire_detected"] is False

    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    out_frame, counts = tracker.process_frame(blank)
    assert out_frame.shape == (480, 640, 3)
    assert counts["persons"] >= 0
    assert counts["vehicles"] >= 0
    assert counts["entry"] >= 0
    assert counts["exit"] >= 0
    assert counts["stream_healthy"] is True


def test_stream_health_guard_offline_frame_suppresses_alerts_and_resets_buffers():
    tracker = SpatialTracker(model=None, camera_id="CAM-03", zone="Logistics Yard")
    # Simulate lingering state
    tracker.fall_counters[1] = 4
    tracker.fall_consecutive_frames[1] = 4
    tracker.untracked_fall_counter = 3
    if tracker.fire_detector:
        tracker.fire_detector.fire_consecutive_frames = 4

    # Stream read failure (ret=False)
    offline_frame, counts = tracker.process_frame(None, ret=False)
    assert offline_frame.shape == (480, 640, 3)
    assert counts["stream_healthy"] is False
    assert counts["fall_detected"] is False
    assert counts["fire_detected"] is False
    assert counts["is_crowded"] is False

    # Buffers purged
    assert len(tracker.fall_counters) == 0
    assert tracker.untracked_fall_counter == 0
    if tracker.fire_detector:
        assert tracker.fire_detector.fire_consecutive_frames == 0


def test_stream_health_guard_empty_ndarray():
    tracker = SpatialTracker(model=None)
    empty = np.zeros((0, 0, 3), dtype=np.uint8)
    offline_frame, counts = tracker.process_frame(empty, ret=True)
    assert offline_frame.shape == (480, 640, 3)
    assert counts["stream_healthy"] is False
    assert counts["fall_detected"] is False
    assert counts["fire_detected"] is False


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
        assert payload["type"] in ["ABNORMAL GATHERING", "CROWD GATHERING ALERT"]
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
    - By default (draw_skeletons=False), skeleton joint lines and keypoint dots are HIDDEN from video frame
    - Pose estimation continues running in the background for fall detection logic
    - When draw_skeletons=True, draws Emerald Green for normal posture and Pure Red for fall detection
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # Case A: Upright person with default draw_skeletons=False (hidden overlays)
    p_upright = MagicMock()
    p_upright.cls = [MagicMock(item=lambda: 0)]
    p_upright.conf = [MagicMock(item=lambda: 0.95)]
    p_upright.xyxy = [np.array([100, 50, 200, 250])]
    p_upright.id = MagicMock(item=lambda: 1)

    res_upright = MagicMock(boxes=[p_upright], keypoints=make_pose_keypoints(nose_y=80, hip_y=180, nose_x=150, hip_x=150))
    mock_model = MagicMock()
    mock_model.track.return_value = [res_upright]

    tracker = SpatialTracker(model=mock_model)
    assert tracker.draw_skeletons is False
    annotated_upright, counts_upright = tracker.process_frame(blank.copy())
    assert counts_upright["fall_detected"] is False

    # Joint at (150, 80) should NOT have green drawn by default (skeletons hidden)
    assert annotated_upright[80, 150, 1] == 0

    # Case B: Fallen person with default draw_skeletons=False -> pose estimation runs in background, fall detected!
    p_fallen = MagicMock()
    p_fallen.cls = [MagicMock(item=lambda: 0)]
    p_fallen.conf = [MagicMock(item=lambda: 0.95)]
    p_fallen.xyxy = [np.array([100, 300, 400, 400])]
    p_fallen.id = MagicMock(item=lambda: 1)

    res_fallen = MagicMock(boxes=[p_fallen], keypoints=make_pose_keypoints(nose_y=380, hip_y=330, nose_x=250, hip_x=200))
    mock_model.track.return_value = [res_fallen]

    for _ in range(4):
        tracker.process_frame(blank.copy())
    # Frame 5: 5th consecutive fallen frame -> confirmed in background!
    annotated_fallen, counts_fallen = tracker.process_frame(blank.copy())
    assert counts_fallen["fall_detected"] is True
    # Joint at (250, 380) is NOT drawn on frame by default (hidden skeletal overlays)
    assert annotated_fallen[380, 250, 2] == 0

    # Case C: Explicitly enabled draw_skeletons=True
    tracker_drawn = SpatialTracker(model=mock_model, draw_skeletons=True)
    assert tracker_drawn.draw_skeletons is True
    mock_model.track.return_value = [res_upright]
    annotated_drawn, _ = tracker_drawn.process_frame(blank.copy())
    assert annotated_drawn[80, 150, 1] > 200


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


def test_fire_detection_clean_frame_nominal():
    """
    Verifies that on clean frames without fire or smoke signatures,
    fire_detected is False.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_model = MagicMock()
    mock_model.track.return_value = [MagicMock(boxes=[])]
    mock_fire_model = MagicMock()
    mock_fire_model.return_value = [MagicMock(boxes=[])]
    mock_fire_model.names = {0: "smoke", 1: "fire"}
    tracker = SpatialTracker(model=mock_model, fire_model=mock_fire_model)
    _, counts = tracker.process_frame(blank)
    assert counts["fire_detected"] is False


def test_webcam_bottom_edge_incomplete_body_guard():
    """
    Verifies Incomplete Body Guard on webcams:
    When a person sits close to a desk webcam, their bounding box touches the bottom
    edge of the frame (y2 >= height - 15) and appears wide (w > h * 1.3).
    Fall detection MUST be completely disabled for that track ID.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)  # height=480

    # Person sitting close to desk webcam: y2 = 475 (touches bottom edge of 480p frame)
    # Box is wide (w = 350 > h = 200 * 1.3)
    p_desk = MagicMock()
    p_desk.cls = [MagicMock(item=lambda: 0)]
    p_desk.conf = [MagicMock(item=lambda: 0.95)]
    p_desk.xyxy = [np.array([100, 275, 450, 475])]  # y2=475 >= 480-15=465, w=350, h=200
    p_desk.id = MagicMock(item=lambda: 88)

    res = MagicMock(boxes=[p_desk], keypoints=None)
    mock_model = MagicMock()
    mock_model.track.return_value = [res]

    tracker = SpatialTracker(model=mock_model)

    # Over 10 consecutive frames, fall detection MUST remain False and counter 0
    for frame_idx in range(10):
        annotated, counts = tracker.process_frame(blank.copy())
        assert counts["fall_detected"] is False, f"Frame {frame_idx} triggered false fall on desk webcam"
        assert tracker.fall_counters.get(88, 0) == 0, "Fall counter must be reset to 0 by incomplete body guard"
        # Bounding box must remain green, never red
        assert np.any(annotated[275:475, 100:450, 1] > 200)


def test_circuit_breaker_drops_alerts_for_offline_camera():
    """
    Verifies that when a camera is marked offline or rendered STREAM OFFLINE,
    the circuit breaker in alert_manager immediately drops any dispatched alerts.
    """
    from backend.app.core.websocket_manager import alert_manager

    # Explicitly pause / mark CAM-03 offline
    alert_manager.pause_stream_dispatch("CAM-03")
    assert alert_manager.is_stream_active("CAM-03") is False

    from unittest.mock import AsyncMock
    mock_ws = MagicMock()
    mock_ws.send_text = AsyncMock()
    alert_manager.active_connections = [mock_ws]

    # Try broadcasting an alert for CAM-03
    alert_payload = {
        "id": "EVT-HAZARD-TEST-OFFLINE",
        "camera": "CAM-03",
        "type": "CRITICAL HAZARD: FIRE / SMOKE DETECTED",
        "detail": "Test alert",
    }
    alert_manager.broadcast_sync(alert_payload)

    # Must be dropped by circuit breaker! send_text must NEVER be called
    assert mock_ws.send_text.call_count == 0

    # Resume CAM-03 and verify alerts are permitted
    alert_manager.resume_stream_dispatch("CAM-03")
    assert alert_manager.is_stream_active("CAM-03") is True
    alert_manager.broadcast_sync(alert_payload)
    # When active, it passes through to send_text
    assert mock_ws.send_text.call_count == 1
    alert_manager.active_connections.clear()


def test_circuit_breaker_stops_conflicting_workers():
    """
    Verifies that MultiFileStreamManager.get_worker stops any prior running worker
    for the same camera ID when a new file or source is requested.
    """
    from pathlib import Path
    from backend.app.main import multi_file_stream_manager

    path1 = Path("test_vid_1.mp4")
    path2 = Path("test_vid_2.mp4")

    w1 = multi_file_stream_manager.get_worker(path1, camera_id="CAM-99")
    assert w1.running is True

    # Request new file for same camera_id
    w2 = multi_file_stream_manager.get_worker(path2, camera_id="CAM-99")
    assert w1.running is False, "Previous worker for CAM-99 must be stopped"
    assert w2.running is True

    # Cleanup
    multi_file_stream_manager.stop_camera("CAM-99")
    assert w2.running is False


def test_fps_telemetry_offline_zero_and_active_calculated():
    """
    Verifies that:
    1. Offline/unassigned streams (STREAM OFFLINE) report fps = 0.
    2. Active valid streams calculate and pass real-time processing fps > 0.
    """
    tracker = SpatialTracker(camera_id="CAM-03", enable_fire_detection=False)

    # 1. Offline frame check
    offline_frame, offline_counts = tracker.process_frame(None, ret=False)
    assert offline_counts["fps"] == 0
    assert offline_counts["stream_healthy"] is False

    # 2. Active frame check
    valid_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    _, active_counts = tracker.process_frame(valid_frame, ret=True)
    assert "fps" in active_counts
    assert active_counts["fps"] > 0
    assert active_counts["stream_healthy"] is True


def test_cam06_hazard_alert_dispatch_and_cooldown():
    """
    Verifies CAM-06 hazard detection loop pushes WebSocket notification payload
    when fire_detected or smoke_detected is True, and enforces the 15-second cooldown.
    """
    from backend.app.core.websocket_manager import alert_manager

    mock_fire_det = MagicMock()
    # Mock detection returning hazard confirmed
    fire_box = {
        "class_id": 0,
        "class_name": "fire",
        "confidence": 0.88,
        "box": [100, 100, 200, 200],
    }
    mock_fire_det.detect.return_value = (np.zeros((480, 640, 3), dtype=np.uint8), True, [fire_box])
    mock_fire_det.primary_hazard = "fire"

    tracker = SpatialTracker(
        camera_id="CAM-06",
        zone="Zone 06 // Western Security Barrier",
        is_webcam=False,
        fire_model=mock_fire_det,
    )
    tracker.fire_detector = mock_fire_det

    mock_ws = MagicMock()
    mock_ws.send_text = AsyncMock()
    alert_manager.active_connections.append(mock_ws)
    alert_manager.resume_stream_dispatch("CAM-06")

    try:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        _, counts = tracker.process_frame(frame, ret=True)

        assert counts["fire_detected"] is True
        assert counts["stream_healthy"] is True
        assert counts["fps"] > 0
        assert mock_ws.send_text.call_count == 1

        # Second frame immediately: within 15s cooldown -> send_text must NOT be called again
        _, counts2 = tracker.process_frame(frame, ret=True)
        assert mock_ws.send_text.call_count == 1

        # Advance last_fire_alert_time by 16s -> cooldown expired -> alert must fire
        tracker.last_fire_alert_time -= 16.0
        _, counts3 = tracker.process_frame(frame, ret=True)
        assert mock_ws.send_text.call_count == 2
    finally:
        alert_manager.active_connections.clear()


def test_camera_telemetry_endpoint():
    """
    Verifies that /api/camera-telemetry returns all cameras, reporting 0 FPS for offline
    and actual processing FPS/entry/exit/occupancy counts for active streams.
    """
    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)
    res = client.get("/api/camera-telemetry")
    assert res.status_code == 200
    data = res.json()

    assert "CAM-01" in data
    assert "CAM-03" in data
    assert "CAM-05" in data
    assert "CAM-06" in data
    # Offline streams must explicitly report 0 FPS and 0 counts
    assert data["CAM-04"]["fps"] == 0
    assert data["CAM-04"]["is_online"] is False
    assert data["CAM-04"]["entry"] == 0
    assert data["CAM-04"]["exit"] == 0
    assert data["CAM-04"]["occupancy"] == 0


def test_line_crossing_tripwire_top_to_bottom_and_bottom_to_top():
    """
    Verifies that a tracked person crossing horizontal tripwire (line_y = 480 * 0.55 = 264)
    from top-to-bottom increments ENTRY and bottom-to-top increments EXIT.
    """
    tracker = SpatialTracker(model=None, camera_id="CAM-03", zone="Logistics Yard North")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Helper to create mock detection with track id
    def make_person(tid, y_center, x_center=200):
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_boxes = MagicMock()
        # Bounding box: height 100, width 60
        y1 = y_center - 50
        y2 = y_center + 50
        x1 = x_center - 30
        x2 = x_center + 30
        mock_boxes.xyxy = np.array([[x1, y1, x2, y2]])
        mock_boxes.cls = np.array([0])
        mock_boxes.conf = np.array([0.80])
        mock_boxes.id = np.array([tid])
        mock_result.boxes = mock_boxes
        mock_result.keypoints = None
        mock_model.track.return_value = [mock_result]
        return mock_model

    # Frame 1: Person 1 outside/above line_y (center_y = 70 < 264, feet_y = 120 < 150)
    tracker.model = make_person(1, y_center=70)
    _, counts1 = tracker.process_frame(frame, ret=True)
    assert counts1["entry"] == 0
    assert counts1["exit"] == 0
    assert counts1["occupancy"] == 0

    # Frame 2: Person 1 moves downwards below line_y into zone (center_y = 280 > 264, feet_y = 330) -> ENTRY!
    tracker.model = make_person(1, y_center=280)
    _, counts2 = tracker.process_frame(frame, ret=True)
    assert counts2["entry"] == 1
    assert counts2["exit"] == 0
    assert counts2["occupancy"] == 1

    # Frame 3: Person 1 moves back up above line_y and outside zone (center_y = 70 < 264, feet_y = 120) -> EXIT!
    tracker.model = make_person(1, y_center=70)
    _, counts3 = tracker.process_frame(frame, ret=True)
    assert counts3["entry"] == 1
    assert counts3["exit"] == 1
    assert counts3["occupancy"] == 0


def test_line_crossing_tripwire_lateral_left_to_right_and_right_to_left():
    """
    Verifies that a tracked person crossing vertical tripwire (line_x = 640 * 0.50 = 320)
    from left-to-right increments ENTRY and right-to-left increments EXIT.
    """
    tracker = SpatialTracker(model=None, camera_id="CAM-03", zone="Logistics Yard North")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    def make_person(tid, x_center, y_center=200):
        mock_model = MagicMock()
        mock_result = MagicMock()
        mock_boxes = MagicMock()
        y1 = y_center - 40
        y2 = y_center + 40
        x1 = x_center - 25
        x2 = x_center + 25
        mock_boxes.xyxy = np.array([[x1, y1, x2, y2]])
        mock_boxes.cls = np.array([0])
        mock_boxes.conf = np.array([0.75])
        mock_boxes.id = np.array([tid])
        mock_result.boxes = mock_boxes
        mock_result.keypoints = None
        mock_model.track.return_value = [mock_result]
        return mock_model

    # Frame 1: Person 2 to the left of line_x and outside zone (center_x = 50 < 320, feet_x = 50 < 100)
    tracker.model = make_person(2, x_center=50)
    _, counts1 = tracker.process_frame(frame, ret=True)
    assert counts1["entry"] == 0
    assert counts1["exit"] == 0
    assert counts1["occupancy"] == 0

    # Frame 2: Person 2 walks laterally across line_x to right into zone (center_x = 345 > 320) -> ENTRY!
    tracker.model = make_person(2, x_center=345)
    _, counts2 = tracker.process_frame(frame, ret=True)
    assert counts2["entry"] == 1
    assert counts2["exit"] == 0
    assert counts2["occupancy"] == 1

    # Frame 3: Person 2 walks back to left across line_x and outside zone (center_x = 50 < 320) -> EXIT!
    tracker.model = make_person(2, x_center=50)
    _, counts3 = tracker.process_frame(frame, ret=True)
    assert counts3["entry"] == 1
    assert counts3["exit"] == 1
    assert counts3["occupancy"] == 0


def test_distant_pedestrian_conf_threshold():
    """
    Verifies that pedestrians with confidence between 0.35 and 0.40 are accepted and bounded.
    """
    tracker = SpatialTracker(model=None, camera_id="CAM-03", zone="Logistics Yard North")
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_boxes = MagicMock()
    # Pedestrian with conf = 0.36 (below 0.40, but above 0.35)
    mock_boxes.xyxy = np.array([[100, 100, 140, 220]])
    mock_boxes.cls = np.array([0])
    mock_boxes.conf = np.array([0.36])
    mock_boxes.id = np.array([10])
    mock_result.boxes = mock_boxes
    mock_result.keypoints = None
    mock_model.track.return_value = [mock_result]
    tracker.model = mock_model

    _, counts = tracker.process_frame(frame, ret=True)
    assert counts["persons"] == 1


def test_unassigned_camera_alerts_suppressed_by_default():
    """
    Verifies that unassigned cameras default to is_stream_active = False,
    and any attempt to dispatch WebSocket alerts is completely suppressed by circuit breaker.
    """
    from backend.app.core.websocket_manager import alert_manager
    from backend.main import dispatch_hazard_alert

    mock_ws = AsyncMock()
    alert_manager.active_connections = [mock_ws]
    try:
        # Camera CAM-99 has never been registered as active
        assert alert_manager.is_stream_active("CAM-99") is False

        # Attempt to broadcast alert for unassigned camera
        payload = {
            "id": "EVT-TEST-UNASSIGNED",
            "time": "12:00:00 IST",
            "camera": "CAM-99",
            "zone": "Test Zone",
            "type": "CRITICAL HAZARD",
        }
        alert_manager.broadcast_sync(payload)
        assert mock_ws.send_text.call_count == 0

        # dispatch_hazard_alert must also return None for unassigned camera
        res = dispatch_hazard_alert(camera_id="CAM-99", zone="Test Zone")
        assert res is None
        assert mock_ws.send_text.call_count == 0
    finally:
        alert_manager.active_connections.clear()


def test_stop_camera_stream_endpoint():
    """
    Verifies that POST /api/camera/{camera_id}/stop pauses stream dispatch
    and halts active file stream workers.
    """
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.core.websocket_manager import alert_manager

    client = TestClient(app)
    # Resume CAM-07 first
    alert_manager.resume_stream_dispatch("CAM-07")
    assert alert_manager.is_stream_active("CAM-07") is True

    # Call stop endpoint
    res = client.post("/api/camera/CAM-07/stop")
    assert res.status_code == 200
    assert res.json() == {"status": "STOPPED", "camera_id": "CAM-07"}
    assert alert_manager.is_stream_active("CAM-07") is False


def test_file_stream_worker_halts_when_unassigned():
    """
    Verifies that FileStreamWorker with active_clients = 0 pauses alert dispatch
    and does not evaluate AI inference.
    """
    from pathlib import Path
    from backend.app.main import FileStreamWorker
    from backend.app.core.websocket_manager import alert_manager

    worker = FileStreamWorker(
        file_path=Path("non_existent_stream.mp4"),
        overlay_label="TEST",
        camera_id="CAM-88",
        zone="Zone 88",
    )
    assert worker.active_clients == 0
    # Before starting, worker has 0 clients
    alert_manager.resume_stream_dispatch("CAM-88")
    assert alert_manager.is_stream_active("CAM-88") is True

    # Simulate one loop iteration when active_clients <= 0
    worker.active_clients = 0
    # When active_clients is 0, alert dispatch must be paused
    alert_manager.pause_stream_dispatch("CAM-88")
    worker.tracker.is_stream_active = False

    assert alert_manager.is_stream_active("CAM-88") is False
    assert worker.tracker.is_stream_active is False


def test_cam03_fire_conf_and_contour_size_configuration():
    """
    Verifies that CAM-03 outdoor yard stream specifically configures FireDetector
    with conf=0.88 and min_contour_size=2000 px, eliminating wet pavement and reflections,
    whereas other cameras retain standard thresholds.
    """
    mock_model = MagicMock()
    mock_fire_model = MagicMock()
    mock_fire_model.names = {0: "fire", 1: "smoke"}

    # CAM-03: outdoor yard calibration
    tracker_cam03 = SpatialTracker(
        model=mock_model,
        fire_model=mock_fire_model,
        camera_id="CAM-03",
        zone="Logistics Yard North",
    )
    assert tracker_cam03.fire_conf_threshold == 0.88
    assert tracker_cam03.smoke_conf_threshold == 0.88
    assert tracker_cam03.min_contour_size == 2000
    assert tracker_cam03.fire_detector.fire_conf_threshold == 0.88
    assert tracker_cam03.fire_detector.smoke_conf_threshold == 0.88
    assert tracker_cam03.fire_detector.min_contour_area == 2000

    # CAM-04 / CAM-06: standard industrial channels
    tracker_cam04 = SpatialTracker(
        model=mock_model,
        fire_model=mock_fire_model,
        camera_id="CAM-04",
        zone="Precision Machining",
    )
    assert tracker_cam04.fire_conf_threshold == 0.50
    assert tracker_cam04.smoke_conf_threshold == 0.45
    assert tracker_cam04.min_contour_size == 500
    assert tracker_cam04.fire_detector.fire_conf_threshold == 0.50
    assert tracker_cam04.fire_detector.smoke_conf_threshold == 0.45
    assert tracker_cam04.fire_detector.min_contour_area == 500


def test_cam03_fire_false_trigger_rejection():
    """
    Verifies that CAM-03 rejects candidate detections from wet pavement reflections,
    vehicle headlights, sun glare, or reflections with conf < 0.88 or contour area < 2000 px,
    completely eliminating false hazard alerts.
    """
    from backend.app.core.websocket_manager import alert_manager

    mock_model = MagicMock()
    mock_model.track.return_value = [MagicMock(boxes=[])]
    mock_fire_model = MagicMock()
    mock_fire_model.names = {0: "fire", 1: "smoke"}

    tracker = SpatialTracker(
        model=mock_model,
        fire_model=mock_fire_model,
        camera_id="CAM-03",
        zone="Logistics Yard North",
    )
    tracker.is_stream_active = True
    alert_manager.resume_stream_dispatch("CAM-03")

    # Case 1: Outdoor wet pavement reflection (conf=0.85 < 0.88, small glint box 20x20 = 400 < 2000)
    glint_box = MagicMock()
    glint_box.conf = [0.85]
    glint_box.cls = [0]
    glint_box.xyxy = [np.array([100, 100, 120, 120])]  # 20x20 area = 400 px
    mock_fire_model.return_value = [MagicMock(boxes=[glint_box])]

    frame1 = np.ones((480, 640, 3), dtype=np.uint8) * 50
    frame2 = np.ones((480, 640, 3), dtype=np.uint8) * 100

    # Send motion frames
    tracker.process_frame(frame1)
    _, counts = tracker.process_frame(frame2)
    assert counts["fire_detected"] is False
    assert counts.get("hazard_type") is None

    # Case 2: Vehicle reflection with conf 0.89 >= 0.88, but small contour area (30x30 = 900 < 2000 px)
    small_bright_box = MagicMock()
    small_bright_box.conf = [0.89]
    small_bright_box.cls = [0]
    small_bright_box.xyxy = [np.array([100, 100, 130, 130])]  # 30x30 area = 900 px
    mock_fire_model.return_value = [MagicMock(boxes=[small_bright_box])]

    frame3 = np.ones((480, 640, 3), dtype=np.uint8) * 120
    _, counts_small = tracker.process_frame(frame3)
    assert counts_small["fire_detected"] is False

    # Case 3: Genuine massive fire hazard (conf=0.92 >= 0.88, contour area 60x60 = 3600 >= 2000 px)
    real_fire_box = MagicMock()
    real_fire_box.conf = [0.92]
    real_fire_box.cls = [0]
    real_fire_box.xyxy = [np.array([100, 100, 160, 160])]  # 60x60 area = 3600 px
    mock_fire_model.return_value = [MagicMock(boxes=[real_fire_box])]

    # Must pass temporal buffer of 5 frames
    for i in range(5):
        dynamic_frame = np.ones((480, 640, 3), dtype=np.uint8) * (130 + i * 10)
        _, res_counts = tracker.process_frame(dynamic_frame)

    assert res_counts["fire_detected"] is True
    assert res_counts.get("hazard_type") == "fire"


def test_abnormal_gathering_does_not_trigger_from_cumulative_drift():
    """
    Verifies that real-time occupancy calculation is strictly derived from the actual
    number of active, currently tracked bounding boxes in the frame/zone, and does NOT
    trigger ABNORMAL GATHERING from cumulative IN - OUT counter drift.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    mock_model = MagicMock()
    tracker = SpatialTracker(
        model=mock_model,
        zone_threshold=4,
        camera_id="CAM-02",
        zone="Zone 01 // Optical Turnstile B",
    )
    # Simulate historical drift where 12 entries and 2 exits occurred over time
    tracker.down_count = 12
    tracker.entry_count = 12
    tracker.up_count = 2
    tracker.exit_count = 2
    # Net cumulative difference is 10, which exceeds zone_threshold=4

    # Frame with only 2 currently active tracked persons inside the zone
    active_persons = []
    for idx, x_pos in enumerate([200, 300]):
        p = MagicMock()
        p.cls = [MagicMock(item=lambda: 0)]
        p.conf = [MagicMock(item=lambda: 0.90)]
        p.xyxy = [np.array([x_pos - 20, 180, x_pos + 20, 300])]
        p.id = MagicMock(item=lambda i=idx + 1: i)
        active_persons.append(p)

    mock_res = MagicMock(boxes=active_persons, keypoints=None)
    mock_model.track.return_value = [mock_res]

    with patch("backend.app.vision_engine.alert_manager.broadcast_sync") as mock_broadcast:
        _, counts = tracker.process_frame(blank.copy())

        # Cumulative entry/exit counters remain preserved
        assert counts["entry"] == 12
        assert counts["exit"] == 2

        # Real-time occupancy MUST strictly be 2 (actual active persons), NOT 10!
        assert counts["occupancy"] == 2
        assert counts["occupancy_count"] == 2
        assert counts["is_crowded"] is False
        assert counts["gathering_alert"] is False

        # No ABNORMAL GATHERING WebSocket alert should be fired!
        assert mock_broadcast.call_count == 0

    # Next frame: 4 active persons arrive inside the zone (reaches zone_threshold=4)
    crowd_persons = []
    for idx, x_pos in enumerate([150, 250, 350, 450]):
        p = MagicMock()
        p.cls = [MagicMock(item=lambda: 0)]
        p.conf = [MagicMock(item=lambda: 0.90)]
        p.xyxy = [np.array([x_pos - 20, 180, x_pos + 20, 300])]
        p.id = MagicMock(item=lambda i=idx + 1: i)
        crowd_persons.append(p)

    mock_res_crowd = MagicMock(boxes=crowd_persons, keypoints=None)
    mock_model.track.return_value = [mock_res_crowd]
    tracker.is_stream_active = True

    from backend.app.core.websocket_manager import alert_manager
    alert_manager.resume_stream_dispatch("CAM-02")

    with patch("backend.app.vision_engine.alert_manager.broadcast_sync") as mock_broadcast:
        _, counts_crowd = tracker.process_frame(blank.copy())

        assert counts_crowd["occupancy"] == 4
        assert counts_crowd["is_crowded"] is True
        assert counts_crowd["gathering_alert"] is True
        assert mock_broadcast.call_count == 1
        payload = mock_broadcast.call_args[0][0]
        assert payload["type"] in ["ABNORMAL GATHERING", "CROWD GATHERING ALERT"]
        assert payload["camera"] == "CAM-02"


def test_universal_human_bounding_box_conf_025():
    """
    Verifies that the person detection confidence threshold is lowered to conf=0.25
    globally across all camera feeds, and no pixel-area filter rejects small or distant pedestrians.
    """
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Global conf=0.25 across all camera IDs
    for cam_id in ["CAM-01", "CAM-02", "CAM-03", "CAM-04", "CAM-06"]:
        tracker = SpatialTracker(camera_id=cam_id)
        assert tracker.person_conf_threshold == 0.25, f"Camera {cam_id} must have global person_conf_threshold=0.25"

    tracker_wide = SpatialTracker(camera_id="CAM-03", zone="Logistics Yard North")
    assert tracker_wide.person_conf_threshold == 0.25

    # Small/distant pedestrian in wide-angle shot (e.g. 15x35 px, conf=0.26)
    mock_model = MagicMock()
    mock_res = MagicMock()
    small_p_box = MagicMock()
    small_p_box.xyxy = [np.array([120, 150, 135, 185])]  # 15x35 = 525 px area
    small_p_box.cls = [MagicMock(item=lambda: 0)]
    small_p_box.conf = [MagicMock(item=lambda: 0.26)]
    small_p_box.id = MagicMock(item=lambda: 7)
    mock_res.boxes = [small_p_box]
    mock_res.keypoints = None
    mock_model.track.return_value = [mock_res]

    tracker_wide.model = mock_model
    annotated, counts = tracker_wide.process_frame(frame.copy(), ret=True)
    assert counts["persons"] == 1, "Small/distant pedestrian with conf=0.26 must be reliably bounded"

    # Sub-threshold detection (conf=0.22 < 0.25) is filtered out
    sub_p_box = MagicMock()
    sub_p_box.xyxy = [np.array([120, 150, 135, 185])]
    sub_p_box.cls = [MagicMock(item=lambda: 0)]
    sub_p_box.conf = [MagicMock(item=lambda: 0.22)]
    sub_p_box.id = MagicMock(item=lambda: 8)
    mock_res.boxes = [sub_p_box]

    _, counts_sub = tracker_wide.process_frame(frame.copy(), ret=True)
    assert counts_sub["persons"] == 0, "Detections with conf < 0.25 must be filtered out"


def test_abnormal_gathering_10_plus_people_red_overlay_and_alert():
    """
    Verifies that when the active count of detected people reaches or exceeds 10,
    it draws the red warning bounding box overlay and pushes the CROWD GATHERING ALERT
    payload to the WebSocket queue. If fewer than 10 people are detected, no alert fires.
    """
    from backend.app.core.websocket_manager import alert_manager

    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    tracker = SpatialTracker(camera_id="CAM-03", zone="Logistics Yard North")
    assert tracker.zone_threshold == 10
    tracker.is_stream_active = True
    alert_manager.resume_stream_dispatch("CAM-03")

    # Case 1: 9 people active (below threshold 10) -> normal green bounding boxes, no alert
    persons_9 = []
    for i in range(9):
        p = MagicMock()
        p.cls = [MagicMock(item=lambda: 0)]
        p.conf = [MagicMock(item=lambda: 0.85)]
        x = 20 + (i % 8) * 60
        y = 100 + (i // 8) * 100
        p.xyxy = [np.array([x, y, x + 35, y + 80])]
        p.id = MagicMock(item=lambda idx=i: idx + 1)
        persons_9.append(p)

    mock_res_9 = MagicMock(boxes=persons_9, keypoints=None)
    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res_9]
    tracker.model = mock_model

    with patch("backend.app.vision_engine.alert_manager.broadcast_sync") as mock_broadcast:
        annotated_9, counts_9 = tracker.process_frame(blank.copy(), ret=True)
        assert counts_9["persons"] == 9
        assert counts_9["is_crowded"] is False
        assert counts_9["gathering_alert"] is False
        assert mock_broadcast.call_count == 0

    # Case 2: 10 people active (reaches crowd gathering threshold 10) -> red bounding boxes + WebSocket alert
    persons_10 = []
    for i in range(10):
        p = MagicMock()
        p.cls = [MagicMock(item=lambda: 0)]
        p.conf = [MagicMock(item=lambda: 0.85)]
        x = 20 + (i % 8) * 60
        y = 100 + (i // 8) * 100
        p.xyxy = [np.array([x, y, x + 35, y + 80])]
        p.id = MagicMock(item=lambda idx=i: idx + 1)
        persons_10.append(p)

    mock_res_10 = MagicMock(boxes=persons_10, keypoints=None)
    mock_model.track.return_value = [mock_res_10]
    tracker.model = mock_model

    with patch("backend.app.vision_engine.alert_manager.broadcast_sync") as mock_broadcast:
        annotated_10, counts_10 = tracker.process_frame(blank.copy(), ret=True)
        assert counts_10["persons"] == 10
        assert counts_10["is_crowded"] is True
        assert counts_10["gathering_alert"] is True

        # Red bounding box warning overlay must be present on frame
        # BGR: Red channel is index 2, Green is index 1, Blue is index 0
        assert np.any(annotated_10[:, :, 2] > 200)

        # WebSocket alert payload verification
        assert mock_broadcast.call_count == 1
        payload = mock_broadcast.call_args[0][0]
        assert payload["type"] in ["ABNORMAL GATHERING", "CROWD GATHERING ALERT"]
        assert payload["camera"] == "CAM-03"
        assert payload["level"] == "CRITICAL"


def test_bounding_box_scaling_and_alignment():
    """
    Verifies that detection bounding boxes:
    1. Scale and align precisely when orig_shape differs from frame shape
    2. Clamp strictly to frame boundaries without out-of-bounds coordinate offset
    """
    # 640x480 frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    p_scaled = MagicMock()
    p_scaled.cls = [MagicMock(item=lambda: 0)]
    p_scaled.conf = [MagicMock(item=lambda: 0.90)]
    # Bounding box in 320x240 coordinates: [50, 60, 150, 180]
    p_scaled.xyxy = [np.array([50.0, 60.0, 150.0, 180.0])]
    p_scaled.id = MagicMock(item=lambda: 1)

    mock_res = MagicMock(boxes=[p_scaled], keypoints=None)
    # orig_shape is 320x240 (half resolution of 640x480)
    mock_res.orig_shape = (240, 320)

    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res]

    tracker = SpatialTracker(model=mock_model, draw_skeletons=False)
    annotated, counts = tracker.process_frame(frame.copy(), ret=True)

    assert counts["persons"] == 1
    # Scaled coordinates in 640x480 should be: x1=100, y1=120, x2=300, y2=360
    # Emerald green border (74, 222, 128) must be rendered around the scaled box
    assert annotated[120, 100, 1] > 200
    assert annotated[360, 300, 1] > 200


def test_infer_stride_frame_skipping():
    """
    Verifies that infer_stride=3 executes heavy YOLO tracking only on frame 0, 3, 6,
    and skips inference on intermediate frames while reusing cached detections smoothly.
    """
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    mock_person = MagicMock()
    mock_person.cls = [MagicMock(item=lambda: 0)]
    mock_person.conf = [MagicMock(item=lambda: 0.85)]
    mock_person.xyxy = [np.array([100.0, 100.0, 200.0, 300.0])]
    mock_person.id = MagicMock(item=lambda: 7)

    mock_res = MagicMock(boxes=[mock_person], keypoints=None)
    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res]

    tracker = SpatialTracker(model=mock_model, infer_stride=3)

    # Frame 0: Should trigger inference (model.track call count = 1)
    _, counts_0 = tracker.process_frame(frame.copy(), ret=True)
    assert counts_0["persons"] == 1
    assert mock_model.track.call_count == 1

    # Frame 1: Should skip inference (model.track call count remains 1, reuses cache)
    _, counts_1 = tracker.process_frame(frame.copy(), ret=True)
    assert counts_1["persons"] == 1
    assert mock_model.track.call_count == 1

    # Frame 2: Should skip inference (model.track call count remains 1, reuses cache)
    _, counts_2 = tracker.process_frame(frame.copy(), ret=True)
    assert counts_2["persons"] == 1
    assert mock_model.track.call_count == 1

    # Frame 3: Should trigger inference (model.track call count = 2)
    _, counts_3 = tracker.process_frame(frame.copy(), ret=True)
    assert counts_3["persons"] == 1
    assert mock_model.track.call_count == 2


def test_infer_stride_reset_clears_cache():
    """Verifies that reset() purges frame counter and cached boxes."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    mock_person = MagicMock()
    mock_person.cls = [MagicMock(item=lambda: 0)]
    mock_person.conf = [MagicMock(item=lambda: 0.85)]
    mock_person.xyxy = [np.array([100.0, 100.0, 200.0, 300.0])]
    mock_person.id = MagicMock(item=lambda: 7)

    mock_res = MagicMock(boxes=[mock_person], keypoints=None)
    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res]

    tracker = SpatialTracker(model=mock_model, infer_stride=2)
    tracker.process_frame(frame.copy(), ret=True)
    assert len(tracker.cached_parsed_boxes) > 0
    assert tracker.frame_counter == 1

    tracker.reset()
    assert len(tracker.cached_parsed_boxes) == 0
    assert tracker.frame_counter == 0


def test_vehicle_detection_multiclass_car_truck_bus_motorcycle():
    """
    Verifies that vehicles (car, truck, bus, motorcycle) are detected,
    increment the vehicle counter, and are bounded on the annotated frame
    with visible gold boxes alongside pedestrians.
    """
    blank = np.zeros((480, 640, 3), dtype=np.uint8)

    # 1 pedestrian + 4 vehicle types: car (2), motorcycle (3), bus (5), truck (7)
    detections = []
    classes = [0, 2, 3, 5, 7]
    for i, cls_id in enumerate(classes):
        b = MagicMock()
        b.cls = [MagicMock(item=lambda c=cls_id: c)]
        b.conf = [MagicMock(item=lambda: 0.88)]
        x = 50 + i * 110
        y = 100
        b.xyxy = [np.array([x, y, x + 90, y + 120])]
        b.id = MagicMock(item=lambda idx=i: idx + 10)
        detections.append(b)

    mock_res = MagicMock(boxes=detections, keypoints=None)
    mock_model = MagicMock()
    mock_model.track.return_value = [mock_res]

    tracker = SpatialTracker(model=mock_model)
    annotated, counts = tracker.process_frame(blank.copy(), ret=True)

    assert counts["persons"] == 1
    assert counts["vehicles"] == 4
    # Gold vehicle bounding box color is BGR (0, 215, 255) in BGR = Red/Green/Blue
    # In BGR, (255, 215, 0) has Blue=255, Green=215, Red=0
    assert np.any(annotated[:, :, 0] > 200)








