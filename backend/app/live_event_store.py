"""Real-Time Live Event Store for UATU Video Intelligence & Access Control.

Thread-safe, sub-millisecond in-memory storage backed by persistent JSON storage
and automatic live JPEG snapshot generation for every triggered real event.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
SNAPSHOTS_DIR = BACKEND_DIR / "snapshots"
DB_FILE = DATA_DIR / "live_events_db.json"


class LiveEventStore:
    """Thread-safe real-time store for all live security, vision, and access control alerts."""

    _instance: Optional["LiveEventStore"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "LiveEventStore":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._store_lock = threading.RLock()
        self._events: List[Dict[str, Any]] = []

        # Ensure directories exist
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

        self._load_from_disk()
        self._initialized = True
        logger.info(
            f"LiveEventStore initialized. Loaded {len(self._events)} events from {DB_FILE}."
        )

    def _load_from_disk(self) -> None:
        """Load persisted live events from disk."""
        if DB_FILE.exists():
            try:
                with open(DB_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._events = data
                    elif isinstance(data, dict) and "events" in data:
                        self._events = data["events"]
            except Exception as e:
                logger.error(f"Error loading live events database from {DB_FILE}: {e}")
                self._events = []
        else:
            self._events = []
            self._persist_to_disk()

    def _persist_to_disk(self) -> None:
        """Flush in-memory events to persistent JSON file safely."""
        try:
            temp_file = DB_FILE.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._events, f, indent=2, ensure_ascii=False)
            temp_file.replace(DB_FILE)
        except Exception as e:
            logger.error(f"Failed to persist live events to {DB_FILE}: {e}")

    def save_event_snapshot(
        self, event_id: str, frame: Optional[np.ndarray]
    ) -> Optional[str]:
        """Save triggering OpenCV frame as a high-quality JPEG snapshot and return its public URL."""
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return None

        try:
            SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            safe_id = "".join(c for c in event_id if c.isalnum() or c in ("-", "_"))
            filename = f"{safe_id}.jpg"
            file_path = SNAPSHOTS_DIR / filename

            # Encode as JPEG quality 85
            success, encoded_img = cv2.imencode(
                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            )
            if success:
                with open(file_path, "wb") as f:
                    f.write(encoded_img.tobytes())
                return f"http://127.0.0.1:8000/api/snapshots/{filename}"
            else:
                cv2.imwrite(str(file_path), frame)
                return f"http://127.0.0.1:8000/api/snapshots/{filename}"
        except Exception as e:
            logger.warning(f"Could not save snapshot for event {event_id}: {e}")
            return None

    def record_live_event(
        self,
        event_type: str,
        camera_id: str = "CAM-01",
        zone: str = "Zone 01 // Main Turnstile North",
        alarm_class: str = "INFO",
        confidence_pct: float = 0.0,
        person_count: int = 0,
        occupancy: int = 0,
        entry_count: int = 0,
        exit_count: int = 0,
        employee_id: str = "N/A",
        employee_name: str = "N/A",
        access_control_correlation: str = "NO_BADGE_EVENT",
        detail: str = "",
        event_id: Optional[str] = None,
        frame: Optional[np.ndarray] = None,
        snapshot_url: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a real live event with full telemetry, capture snapshot evidence, and persist."""
        now = datetime.now(IST)
        timestamp_ist = now.strftime("%Y-%m-%d %H:%M:%S IST")
        time_short = now.strftime("%H:%M:%S IST")

        if not event_id:
            # Deterministic clean event prefix based on category
            t_upper = event_type.upper()
            if "FALL" in t_upper:
                prefix = "FALL"
            elif "FIRE" in t_upper or "SMOKE" in t_upper or "HAZARD" in t_upper:
                prefix = "HAZARD"
            elif "CROWD" in t_upper or "GATHERING" in t_upper:
                prefix = "CROWD"
            elif "AUTH" in t_upper or "ACCESS" in t_upper:
                prefix = "ACCESS"
            elif "ENROLL" in t_upper:
                prefix = "ENROLL"
            else:
                prefix = "EVENT"
            event_id = f"EVT-{prefix}-{int(time.time() * 1000)}"

        # Generate live snapshot URL if frame is available and snapshot_url not provided
        if snapshot_url is None and frame is not None:
            snapshot_url = self.save_event_snapshot(event_id, frame)

        # Build comprehensive live event record
        event_record: Dict[str, Any] = {
            "event_id": event_id,
            "id": event_id,  # Compatibility alias
            "timestamp_ist": timestamp_ist,
            "time": time_short,
            "camera_id": camera_id,
            "camera": camera_id,  # Compatibility alias
            "zone": zone,
            "event_type": event_type,
            "type": event_type,  # Compatibility alias
            "alarm_class": alarm_class.upper(),
            "level": alarm_class.upper(),  # Compatibility alias
            "confidence_pct": round(float(confidence_pct), 1),
            "person_count": int(person_count),
            "occupancy": int(occupancy),
            "entry_count": int(entry_count),
            "exit_count": int(exit_count),
            "employee_id": employee_id,
            "employee_name": employee_name,
            "access_control_correlation": access_control_correlation,
            "detail": detail
            or f"{event_type} registered on {camera_id} ({zone}).",
            "snapshot_url": snapshot_url or "",
            "acknowledged": False,
            "acknowledged_by": "Pending",
            "acknowledged_at_ist": None,
            "human_review_notice": "Possible event detected by AI; authorized human review is required.",
            "tags": tags or [event_type.lower().replace(" ", "_"), camera_id.lower()],
            "metadata": metadata or {},
        }

        with self._store_lock:
            # Prepend newest events first
            self._events.insert(0, event_record)
            # Bound memory to last 1000 events
            if len(self._events) > 1000:
                self._events = self._events[:1000]
            self._persist_to_disk()

        logger.info(
            f"Recorded LIVE EVENT: [{event_record['event_id']}] {event_type} on {camera_id} ({zone})"
        )
        return event_record

    def get_live_events(
        self,
        camera_id: Optional[str] = None,
        event_type: Optional[str] = None,
        unacknowledged_only: bool = False,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Query real live events with optional filters (newest first)."""
        with self._store_lock:
            results = []
            cam_filter = camera_id.strip().upper() if camera_id else ""
            type_filter = event_type.strip().upper() if event_type else ""

            for ev in self._events:
                if cam_filter:
                    ev_cam = ev.get("camera_id", "").upper()
                    if cam_filter != ev_cam and cam_filter not in ev_cam:
                        continue

                if type_filter:
                    ev_type = ev.get("event_type", "").upper()
                    if type_filter not in ev_type:
                        continue

                if unacknowledged_only and ev.get("acknowledged", False):
                    continue

                results.append(ev)
                if len(results) >= limit:
                    break

            return list(results)

    def acknowledge_event(
        self, event_id: str, acknowledged_by: str = "Supervisor"
    ) -> Optional[Dict[str, Any]]:
        """Acknowledge an active event in real time and persist update."""
        now_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
        with self._store_lock:
            target = None
            clean_id = event_id.strip().lower()
            for ev in self._events:
                if (
                    ev.get("event_id", "").lower() == clean_id
                    or ev.get("id", "").lower() == clean_id
                ):
                    ev["acknowledged"] = True
                    ev["acknowledged_by"] = acknowledged_by
                    ev["acknowledged_at_ist"] = now_str
                    target = ev
                    break

            if target:
                self._persist_to_disk()
                logger.info(
                    f"Acknowledged LIVE EVENT [{event_id}] by {acknowledged_by} at {now_str}."
                )
                return target
            return None

    def clear_events(self) -> bool:
        """Reset the live event store to empty state."""
        with self._store_lock:
            self._events = []
            self._persist_to_disk()
            logger.info("Cleared all records from LiveEventStore.")
            return True


# Global Singleton instance
live_event_store = LiveEventStore()
