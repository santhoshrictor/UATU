import os
import json
import numpy as np
import pytest
from backend.app import live_event_store

def test_save_event_snapshot_with_metadata_and_burn_in():
    # Create synthetic test frame (480x640x3 RGB/BGR)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:] = (40, 40, 40)  # dark background

    event_id = "EVT-TEST-FALL-001"
    camera_id = "CAM-03"
    event_type = "Fall Detection"
    timestamp_str = "2026-10-27 12:30:45"
    confidence = 94.5
    zone = "Zone 03 // Precision Line"

    snap_url = live_event_store.save_event_snapshot(
        event_id=event_id,
        frame=frame,
        camera_id=camera_id,
        event_type=event_type,
        timestamp_str=timestamp_str,
        confidence_pct=confidence,
        zone=zone,
    )

    assert snap_url is not None
    assert "/api/snapshots/" in snap_url

    filename = snap_url.split("/")[-1]
    assert filename.startswith("CAM-03_fall_detection_")
    assert filename.endswith(".jpg")

    snapshot_path = os.path.join(live_event_store.SNAPSHOTS_DIR, filename)
    assert os.path.exists(snapshot_path), f"Snapshot file not created at {snapshot_path}"

    # Check sidecar JSON metadata
    sidecar_path = os.path.splitext(snapshot_path)[0] + ".json"
    assert os.path.exists(sidecar_path), f"Sidecar JSON not found at {sidecar_path}"

    with open(sidecar_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["camera_id"] == "CAM-03"
    assert meta["anomaly_type"] == "Fall Detection"
    assert meta["timestamp"] == "2026-10-27 12:30:45"
    assert meta["confidence_pct"] == 94.5
    assert meta["event_id"] == "EVT-TEST-FALL-001"
    assert meta["zone"] == "Zone 03 // Precision Line"

    # Also verify legacy ID alias file was created for backwards compatibility
    legacy_file = os.path.join(live_event_store.SNAPSHOTS_DIR, f"{event_id}.jpg")
    assert os.path.exists(legacy_file), f"Legacy alias file not created at {legacy_file}"

def test_list_recent_snapshots():
    snapshots = live_event_store.list_recent_snapshots(limit=10)
    assert isinstance(snapshots, list)
    assert len(snapshots) > 0
    first = snapshots[0]
    assert "filename" in first
    assert "url" in first
    assert "timestamp" in first
    assert "camera_id" in first
    assert "anomaly_type" in first
