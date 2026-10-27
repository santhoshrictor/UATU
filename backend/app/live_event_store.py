"""Real-Time Live Event Store for UATU Video Intelligence & Access Control.

Thread-safe, sub-millisecond in-memory storage backed by persistent JSON storage
and automatic live JPEG snapshot generation for every triggered real event.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
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
        self,
        event_id: str,
        frame: Optional[np.ndarray],
        camera_id: str = "CAM-01",
        event_type: str = "ANOMALY",
        timestamp_str: Optional[str] = None,
        confidence_pct: float = 0.0,
        zone: str = "",
    ) -> Optional[str]:
        """Save triggering OpenCV frame as a high-quality JPEG snapshot with burned-in HUD metadata,
        structured filename (CAM-03_fall_detection_YYYY-MM-DD_HH-MM-SS.jpg), and JSON sidecar.
        """
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return None

        try:
            SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            now = datetime.now(IST)
            if not timestamp_str:
                timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")

            date_time_slug = now.strftime("%Y-%m-%d_%H-%M-%S")
            safe_id = "".join(c for c in event_id if c.isalnum() or c in ("-", "_"))
            cam_clean = re.sub(r"[^A-Za-z0-9_-]", "", camera_id) or "CAM-01"
            anomaly_slug = re.sub(r"[^a-z0-9]+", "_", event_type.lower()).strip("_") or "anomaly"

            # Requirement 3: Structured filename format, e.g., CAM-03_fall_detection_2026-10-27_11-58-00.jpg
            # Incorporating safe_id ensures total uniqueness across multiple rapid anomalies
            structured_filename = f"{cam_clean}_{anomaly_slug}_{date_time_slug}_{safe_id}.jpg"
            legacy_filename = f"{safe_id}.jpg"

            # Requirement 2: Timestamp & Metadata Burn-in directly onto the image
            annotated_img = frame.copy()
            h, w = annotated_img.shape[:2]

            # Bottom HUD Banner (semi-transparent dark background)
            banner_h = max(38, int(h * 0.065))
            overlay = annotated_img.copy()
            cv2.rectangle(overlay, (0, h - banner_h), (w, h), (10, 15, 30), -1)
            # Red accent stripe on top of banner
            cv2.line(overlay, (0, h - banner_h), (w, h - banner_h), (0, 0, 225), 2)
            cv2.addWeighted(overlay, 0.85, annotated_img, 0.15, 0, annotated_img)

            # Top-left alert evidence badge
            badge_w = 170
            badge_h = 28
            cv2.rectangle(annotated_img, (10, 10), (10 + badge_w, 10 + badge_h), (0, 0, 180), -1)
            cv2.putText(
                annotated_img,
                "CRITICAL EVIDENCE",
                (16, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

            # Bottom Left: Anomaly label & Camera ID
            zone_desc = f" [{zone}]" if zone else ""
            left_text = f"ANOMALY: {event_type.upper()} | CAM: {camera_id}{zone_desc}"
            if len(left_text) > 55:
                left_text = left_text[:52] + "..."
            cv2.putText(
                annotated_img,
                left_text,
                (14, h - int(banner_h * 0.35)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

            # Bottom Right: Exact timestamp
            right_text = f"{timestamp_str} IST"
            cv2.putText(
                annotated_img,
                right_text,
                (max(14, w - 210), h - int(banner_h * 0.35)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (0, 225, 255),
                1,
                cv2.LINE_AA,
            )

            # Encode as JPEG quality 85
            success, encoded_img = cv2.imencode(
                ".jpg", annotated_img, [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            )
            img_bytes = encoded_img.tobytes() if success else None

            file_path = SNAPSHOTS_DIR / structured_filename
            legacy_path = SNAPSHOTS_DIR / legacy_filename

            if img_bytes:
                with open(file_path, "wb") as f:
                    f.write(img_bytes)
                with open(legacy_path, "wb") as f:
                    f.write(img_bytes)
            else:
                cv2.imwrite(str(file_path), annotated_img)
                cv2.imwrite(str(legacy_path), annotated_img)

            # Save structured metadata sidecar JSON (both .json and .jpg.json for universal compatibility)
            stem = structured_filename[:-4] if structured_filename.endswith(".jpg") else structured_filename
            sidecar_path = SNAPSHOTS_DIR / f"{stem}.json"
            sidecar_alt = SNAPSHOTS_DIR / f"{structured_filename}.json"
            metadata_record = {
                "event_id": event_id,
                "camera_id": camera_id,
                "anomaly_type": event_type,
                "timestamp": timestamp_str,
                "zone": zone,
                "confidence_pct": round(float(confidence_pct), 1),
                "filename": structured_filename,
                "url": f"http://127.0.0.1:8000/api/snapshots/{structured_filename}",
            }
            try:
                with open(sidecar_path, "w", encoding="utf-8") as f:
                    json.dump(metadata_record, f, indent=2)
                with open(sidecar_alt, "w", encoding="utf-8") as f:
                    json.dump(metadata_record, f, indent=2)
            except Exception as e:
                logger.debug(f"Sidecar save note: {e}")

            logger.info(
                f"Saved anomaly snapshot: {structured_filename} with burned-in timestamp and metadata."
            )
            return f"http://127.0.0.1:8000/api/snapshots/{structured_filename}"
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
            snapshot_url = self.save_event_snapshot(
                event_id=event_id,
                frame=frame,
                camera_id=camera_id,
                event_type=event_type,
                timestamp_str=now.strftime("%Y-%m-%d %H:%M:%S"),
                confidence_pct=confidence_pct,
                zone=zone,
            )

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

        try:
            from backend.app.audit_engine import audit_engine
            audit_engine.log_event(
                event_type=event_type,
                camera_node=camera_id,
                zone=zone,
                details=detail,
                payload=event_record,
                operator_id="System",
            )
        except Exception as e:
            logger.debug(f"Audit log trigger note: {e}")

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
                try:
                    from backend.app.audit_engine import audit_engine
                    audit_engine.log_event(
                        event_type="SYSTEM_ACTION: ACKNOWLEDGE_ALERT",
                        camera_node=target.get("camera_id", "N/A"),
                        zone=target.get("zone", "N/A"),
                        details=f"Alert [{event_id}] acknowledged by {acknowledged_by}.",
                        operator_id=acknowledged_by,
                        payload={"event_id": event_id, "acknowledged_by": acknowledged_by},
                    )
                except Exception:
                    pass
                return target
            return None

    def clear_events(self) -> bool:
        """Reset the live event store to empty state."""
        with self._store_lock:
            self._events = []
            self._persist_to_disk()
            logger.info("Cleared all records from LiveEventStore.")
            try:
                from backend.app.audit_engine import audit_engine
                audit_engine.log_event(
                    event_type="SYSTEM_ACTION: CLEAR_ALERTS",
                    details="Operator cleared active incident dispatch queue.",
                    operator_id="Operator",
                )
            except Exception:
                pass
            return True

    def list_recent_snapshots(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recently saved anomaly snapshots with associated sidecar metadata."""
        if not SNAPSHOTS_DIR.exists():
            return []

        results = []
        jpg_files = sorted(
            SNAPSHOTS_DIR.glob("*.jpg"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for p in jpg_files[:limit]:
            sidecar = p.with_suffix(".json")
            if not sidecar.exists():
                sidecar = p.with_suffix(".jpg.json")

            meta: Dict[str, Any] = {}
            if sidecar.exists():
                try:
                    with open(sidecar, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                except Exception:
                    pass

            fname = p.name
            ts = meta.get("timestamp") or datetime.fromtimestamp(p.stat().st_mtime, IST).strftime("%Y-%m-%d %H:%M:%S")
            cam = meta.get("camera_id") or (fname.split("_")[0] if "_" in fname else "CAM-01")
            atype = meta.get("anomaly_type") or (fname.split("_")[1].replace("_", " ").upper() if "_" in fname else "ANOMALY")

            results.append({
                "filename": fname,
                "url": f"http://127.0.0.1:8000/api/snapshots/{fname}",
                "timestamp": ts,
                "camera_id": cam,
                "anomaly_type": atype,
                "zone": meta.get("zone", ""),
                "confidence_pct": meta.get("confidence_pct", 95.0),
                "event_id": meta.get("event_id", fname.replace(".jpg", "")),
                "size_bytes": p.stat().st_size,
            })

        return results


# Global Singleton instance
live_event_store = LiveEventStore()


# Module-level convenience wrappers
def save_event_snapshot(
    event_id: str,
    frame: Optional[np.ndarray],
    camera_id: str = "CAM-01",
    event_type: str = "ANOMALY",
    timestamp_str: Optional[str] = None,
    confidence_pct: float = 0.0,
    zone: str = "",
) -> Optional[str]:
    return live_event_store.save_event_snapshot(
        event_id=event_id,
        frame=frame,
        camera_id=camera_id,
        event_type=event_type,
        timestamp_str=timestamp_str,
        confidence_pct=confidence_pct,
        zone=zone,
    )


def list_recent_snapshots(limit: int = 50) -> List[Dict[str, Any]]:
    return live_event_store.list_recent_snapshots(limit=limit)


def record_live_event(*args, **kwargs):
    return live_event_store.record_live_event(*args, **kwargs)


def get_events(*args, **kwargs):
    return live_event_store.get_events(*args, **kwargs)


def clear_events():
    return live_event_store.clear_events()
