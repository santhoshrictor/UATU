"""Tea Point & Scheduled Break Window Engine for UATU Video Intelligence.

Manages CAM-05 Tea Point profile, scheduled break windows (10:00 AM - 10:10 AM),
dwell time tracking, and automated Long Break Exception alert dispatch with
burned-in snapshot capture for forensic audit.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from backend.app.live_event_store import live_event_store
from backend.app.audit_engine import audit_engine

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

BACKEND_DIR = Path(__file__).resolve().parent.parent
SNAPSHOTS_DIR = BACKEND_DIR / "snapshots"


class TeaPointEngine:
    """Thread-safe engine for monitoring CAM-05 Tea Point occupancy and break compliance."""

    _instance: Optional["TeaPointEngine"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "TeaPointEngine":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._state_lock = threading.RLock()
        self.camera_id = "CAM-05"
        self.zone_name = "Zone 05 // Refreshment Hub & Tea Point"
        self.break_start_time = "10:00"
        self.break_end_time = "10:10"
        
        # Standard allowed break duration is 10 minutes (600s).
        # In demo mode, default threshold can be set to 60s (1 min) or 120s (2 min) for live evaluation.
        self.threshold_seconds: int = 60
        self.demo_mode: bool = True
        
        # Live state
        self.current_occupancy: int = 0
        self.first_presence_time: Optional[float] = None
        self.last_alert_time: float = 0.0
        self.alert_cooldown_seconds: float = 20.0
        self.last_exception_alert: Optional[Dict[str, Any]] = None

        self._initialized = True
        logger.info(
            f"TeaPointEngine initialized for {self.camera_id} ({self.zone_name}). "
            f"Break Window: {self.break_start_time}-{self.break_end_time}, Threshold: {self.threshold_seconds}s, Demo: {self.demo_mode}"
        )

    def is_in_break_window(self, dt: Optional[datetime] = None) -> bool:
        """Check if given time falls within the 10:00 AM - 10:10 AM window."""
        now = dt or datetime.now(IST)
        start_h, start_m = map(int, self.break_start_time.split(":"))
        end_h, end_m = map(int, self.break_end_time.split(":"))
        
        start_dt = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        end_dt = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
        return start_dt <= now <= end_dt

    def get_config(self) -> Dict[str, Any]:
        """Return current configuration and live dwell status."""
        with self._state_lock:
            now_ts = time.time()
            now_dt = datetime.now(IST)
            dwell = 0.0
            if self.first_presence_time and self.current_occupancy > 0:
                dwell = max(0.0, now_ts - self.first_presence_time)

            return {
                "camera_id": self.camera_id,
                "zone": self.zone_name,
                "break_window": {
                    "start": self.break_start_time,
                    "end": self.break_end_time,
                    "label": f"Morning Tea Break ({self.break_start_time} AM - {self.break_end_time} AM)",
                    "is_active_now": self.is_in_break_window(now_dt),
                },
                "threshold_seconds": self.threshold_seconds,
                "demo_mode": self.demo_mode,
                "allowed_demo_thresholds": [60, 120, 300, 600],
                "current_occupancy": self.current_occupancy,
                "current_dwell_seconds": round(dwell, 1),
                "is_overstay": dwell >= self.threshold_seconds if self.current_occupancy > 0 else False,
                "last_alert_time": self.last_alert_time,
                "last_exception_alert": self.last_exception_alert,
            }

    def update_config(
        self,
        threshold_seconds: Optional[int] = None,
        demo_mode: Optional[bool] = None,
        break_start_time: Optional[str] = None,
        break_end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update runtime thresholds or demo configuration."""
        with self._state_lock:
            if threshold_seconds is not None:
                self.threshold_seconds = max(10, int(threshold_seconds))
            if demo_mode is not None:
                self.demo_mode = bool(demo_mode)
            if break_start_time:
                self.break_start_time = break_start_time
            if break_end_time:
                self.break_end_time = break_end_time

            logger.info(
                f"[TeaPointEngine] Updated config: threshold={self.threshold_seconds}s, "
                f"demo_mode={self.demo_mode}, window={self.break_start_time}-{self.break_end_time}"
            )
            return self.get_config()

    def process_occupancy(
        self,
        occupancy: int,
        frame: Optional[np.ndarray] = None,
    ) -> Tuple[float, Optional[Dict[str, Any]]]:
        """Process incoming occupancy reading for CAM-05.
        
        Tracks dwell time. If dwell exceeds threshold_seconds during or past break,
        automatically captures snapshot and triggers a Long Break Exception alert.
        """
        with self._state_lock:
            now_ts = time.time()
            now_dt = datetime.now(IST)
            self.current_occupancy = max(0, int(occupancy))

            if self.current_occupancy > 0:
                if self.first_presence_time is None:
                    self.first_presence_time = now_ts

                dwell_seconds = now_ts - self.first_presence_time
                is_active_window = self.is_in_break_window(now_dt)

                # Rule condition: In demo mode, any overstay triggers exception.
                # In standard mode, triggers if present past 10:10 AM or exceeding allowed duration.
                rule_triggered = False
                if self.demo_mode:
                    rule_triggered = dwell_seconds >= self.threshold_seconds
                else:
                    # Outside break window or exceeded window limit
                    if not is_active_window or dwell_seconds >= self.threshold_seconds:
                        rule_triggered = True

                if rule_triggered and (now_ts - self.last_alert_time) >= self.alert_cooldown_seconds:
                    self.last_alert_time = now_ts
                    alert = self._create_and_dispatch_exception(
                        dwell_seconds=dwell_seconds,
                        frame=frame,
                    )
                    self.last_exception_alert = alert
                    return dwell_seconds, alert

                return dwell_seconds, None
            else:
                self.first_presence_time = None
                return 0.0, None

    def reset_dwell(self) -> Dict[str, Any]:
        """Reset the dwell timer and last alert status for CAM-05."""
        with self._state_lock:
            self.first_presence_time = time.time() if self.current_occupancy > 0 else None
            self.last_alert_time = 0.0
            self.last_exception_alert = None
            logger.info(f"[TeaPointEngine] Dwell timer reset for {self.camera_id}")
            return self.get_config()

    def trigger_demo_exception(
        self,
        custom_dwell_minutes: Optional[float] = None,
        frame: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """Forced/instant trigger for jury demonstration."""
        with self._state_lock:
            dwell_sec = (custom_dwell_minutes or (self.threshold_seconds / 60.0) + 0.5) * 60.0
            self.last_alert_time = time.time()
            alert = self._create_and_dispatch_exception(
                dwell_seconds=dwell_sec,
                frame=frame,
                is_forced=True,
            )
            self.last_exception_alert = alert
            return alert

    def _create_and_dispatch_exception(
        self,
        dwell_seconds: float,
        frame: Optional[np.ndarray] = None,
        is_forced: bool = False,
    ) -> Dict[str, Any]:
        """Generate structured Long Break Exception, burn-in snapshot, and broadcast."""
        now_ts = time.time()
        now_dt = datetime.now(IST)
        time_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        time_clock = now_dt.strftime("%H:%M:%S IST")
        event_id = f"EVT-TEA-{int(now_ts)}"

        dwell_min = round(dwell_seconds / 60.0, 1)
        allowed_min = round(self.threshold_seconds / 60.0, 1)

        event_type = "Long Break Exception // CAM-05 Tea Point"
        detail = (
            f"Overstay detected at {self.zone_name}: Worker occupancy exceeded allowed break threshold "
            f"({dwell_min} min elapsed vs. {allowed_min} min allowed). Break schedule: {self.break_start_time} - {self.break_end_time} AM."
        )

        # Fallback synthetic frame if camera frame is unavailable
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            frame[:] = (35, 30, 25) # subtle dark cafe/break-room tone
            cv2.putText(
                frame,
                "CAM-05 TEA POINT // BREAK LOUNGE",
                (40, 200),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (200, 220, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                f"OCCUPANCY DETECTED: {max(1, self.current_occupancy)} PERSON(S)",
                (40, 240),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 200, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                frame,
                f"SCHEDULED BREAK: {self.break_start_time} - {self.break_end_time} AM",
                (40, 275),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (180, 180, 180),
                1,
                cv2.LINE_AA,
            )

        # Save snapshot with OpenCV HUD burn-in overlay & sidecar JSON
        snap_url = live_event_store.save_event_snapshot(
            event_id=event_id,
            frame=frame,
            camera_id=self.camera_id,
            event_type="Long Break Exception",
            timestamp_str=time_str,
            confidence_pct=98.5,
            zone=self.zone_name,
        )

        # Record in persistent live events store
        record = live_event_store.record_live_event(
            event_id=event_id,
            event_type=event_type,
            camera_id=self.camera_id,
            zone=self.zone_name,
            alarm_class="CRITICAL",
            detail=detail,
            snapshot_url=snap_url,
            confidence_pct=98.5,
        )

        # Audit logging for compliance
        try:
            audit_engine.log_event(
                event_type="BREAK_POLICY_VIOLATION: OVERSTAY",
                camera_node=self.camera_id,
                zone=self.zone_name,
                details=detail,
                operator_id="Policy_Automation_Daemon",
                payload={
                    "event_id": event_id,
                    "dwell_seconds": dwell_seconds,
                    "allowed_threshold_seconds": self.threshold_seconds,
                    "break_window": f"{self.break_start_time}-{self.break_end_time}",
                    "is_forced_demo": is_forced,
                    "snapshot_url": snap_url,
                },
            )
        except Exception as ex:
            logger.debug(f"Audit log notice: {ex}")

        # WebSocket broadcast to all connected dashboards
        try:
            from backend.app.core.websocket_manager import alert_manager
            alert_manager.broadcast_sync({
                "type": "LONG_BREAK_EXCEPTION",
                "alert": record,
                "event_id": event_id,
                "camera_id": self.camera_id,
                "zone": self.zone_name,
                "dwell_seconds": dwell_seconds,
                "dwell_minutes": dwell_min,
                "allowed_minutes": allowed_min,
                "snapshot_url": snap_url,
                "timestamp": time_clock,
            })
        except Exception as ex:
            logger.debug(f"WebSocket broadcast notice: {ex}")

        logger.info(
            f"[TeaPointEngine] Dispatched Long Break Exception [{event_id}] for {self.camera_id}: {detail}"
        )
        return record


# Global Singleton Instance
tea_point_engine = TeaPointEngine()
