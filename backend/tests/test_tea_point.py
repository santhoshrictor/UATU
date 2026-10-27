import os
import json
from datetime import datetime, timezone, timedelta
import numpy as np
import pytest
from backend.app.tea_point_engine import tea_point_engine
from backend.app import live_event_store

IST = timezone(timedelta(hours=5, minutes=30))

def test_tea_point_initial_config():
    config = tea_point_engine.get_config()
    assert config["camera_id"] == "CAM-05"
    assert "Tea Point" in config["zone"]
    assert config["break_window"]["start"] == "10:00"
    assert config["break_window"]["end"] == "10:10"
    assert config["threshold_seconds"] in [60, 120, 300, 600]
    assert config["demo_mode"] is True

def test_tea_point_schedule_window():
    # 10:05 AM IST is within the 10:00 - 10:10 break window
    inside_dt = datetime(2026, 10, 27, 10, 5, 0, tzinfo=IST)
    assert tea_point_engine.is_in_break_window(inside_dt) is True

    # 10:15 AM IST is outside the break window
    outside_dt = datetime(2026, 10, 27, 10, 15, 0, tzinfo=IST)
    assert tea_point_engine.is_in_break_window(outside_dt) is False

def test_tea_point_update_config():
    # Update threshold to 2 minutes (120s) for demo
    updated = tea_point_engine.update_config(threshold_seconds=120, demo_mode=True)
    assert updated["threshold_seconds"] == 120
    assert updated["demo_mode"] is True

    # Reset back to 60s
    reset = tea_point_engine.update_config(threshold_seconds=60)
    assert reset["threshold_seconds"] == 60

def test_tea_point_trigger_demo_exception():
    # Create test synthetic frame
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    test_frame[:] = (50, 40, 30)

    alert = tea_point_engine.trigger_demo_exception(custom_dwell_minutes=1.8, frame=test_frame)

    assert alert is not None
    assert alert["camera_id"] == "CAM-05"
    assert "Long Break Exception" in alert["event_type"]
    assert "Zone 05" in alert["zone"]
    assert alert["alarm_class"] == "CRITICAL"
    assert "snapshot_url" in alert
    assert alert["snapshot_url"].startswith("http://127.0.0.1:8000/api/snapshots/")
    assert alert["snapshot_url"].endswith(".jpg")

    # Verify that the physical snapshot and sidecar were generated in snapshots directory
    fname = alert["snapshot_url"].split("/")[-1]
    snap_path = os.path.join(live_event_store.SNAPSHOTS_DIR, fname)
    assert os.path.exists(snap_path), f"Snapshot file missing at {snap_path}"

    sidecar_path = os.path.splitext(snap_path)[0] + ".json"
    assert os.path.exists(sidecar_path), f"Sidecar JSON missing at {sidecar_path}"

    with open(sidecar_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["camera_id"] == "CAM-05"
    assert "Long Break" in meta["anomaly_type"]


def test_tea_point_reset():
    cfg = tea_point_engine.reset_dwell()
    assert cfg["current_dwell_seconds"] == 0.0
    assert cfg["is_overstay"] is False
    assert cfg["last_exception_alert"] is None

