"""Audit Logging Engine for UATU Video Intelligence & Safety Platform.

Date-wise partitioned persistent audit store and CSV generator.
Captures all security alerts, biometric mismatches, system operations,
voice AI commands, and agent responses with UTC and IST timestamps.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
AUDIT_DIR = DATA_DIR / "audit_logs"
LIVE_EVENTS_DB = DATA_DIR / "live_events_db.json"


class AuditEngine:
    """Thread-safe date-wise audit log storage and CSV export engine."""

    _instance: Optional["AuditEngine"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "AuditEngine":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._store_lock = threading.RLock()
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._initialized = True
        logger.info(f"AuditEngine initialized. Audit directory at {AUDIT_DIR}.")

    def _get_date_key(self, dt: Optional[datetime] = None) -> str:
        """Return YYYY-MM-DD string in IST timezone."""
        target_dt = dt or datetime.now(IST)
        if target_dt.tzinfo is None:
            target_dt = target_dt.replace(tzinfo=IST)
        else:
            target_dt = target_dt.astimezone(IST)
        return target_dt.strftime("%Y-%m-%d")

    def _get_log_path_for_date(self, date_str: str) -> Path:
        """Return file path for a given date."""
        return AUDIT_DIR / f"audit_{date_str}.json"

    def _load_logs_for_date(self, date_str: str) -> List[Dict[str, Any]]:
        """Load logs from memory cache or disk for a specific date."""
        with self._store_lock:
            if date_str in self._cache:
                return self._cache[date_str]

            log_file = self._get_log_path_for_date(date_str)
            records: List[Dict[str, Any]] = []

            if log_file.exists():
                try:
                    with open(log_file, "r", encoding="utf-8") as f:
                        records = json.load(f)
                        if not isinstance(records, list):
                            records = []
                except Exception as e:
                    logger.error(f"Failed to read audit log {log_file}: {e}")
                    records = []
            else:
                # If no specific audit file exists yet for today, backfill from live_events_db
                records = self._backfill_from_live_events(date_str)

            self._cache[date_str] = records
            return records

    def _backfill_from_live_events(self, date_str: str) -> List[Dict[str, Any]]:
        """Backfill existing live events for the requested date."""
        backfilled: List[Dict[str, Any]] = []
        if not LIVE_EVENTS_DB.exists():
            return backfilled

        try:
            with open(LIVE_EVENTS_DB, "r", encoding="utf-8") as f:
                data = json.load(f)
                events = data if isinstance(data, list) else data.get("events", [])
                for ev in events:
                    ts_ist = ev.get("timestamp_ist", "")
                    if ts_ist.startswith(date_str):
                        backfilled.append({
                            "log_id": f"AUD-{ev.get('event_id', str(uuid.uuid4())[:8])}",
                            "timestamp_ist": ts_ist,
                            "timestamp_utc": ev.get("timestamp_utc", ""),
                            "event_type": ev.get("event_type", "SECURITY_ALERT"),
                            "camera_node": ev.get("camera_id", "N/A"),
                            "zone": ev.get("zone", "N/A"),
                            "details": ev.get("detail", ""),
                            "voice_command": ev.get("voice_command", ""),
                            "agent_response": ev.get("agent_response", ""),
                            "operator_id": ev.get("acknowledged_by", "System"),
                            "payload": ev,
                        })
        except Exception as e:
            logger.debug(f"Audit backfill note: {e}")
        return backfilled

    def _persist_date_logs(self, date_str: str, records: List[Dict[str, Any]]) -> None:
        """Write logs for a specific date atomically to disk."""
        log_file = self._get_log_path_for_date(date_str)
        temp_file = log_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
            temp_file.replace(log_file)
        except Exception as e:
            logger.error(f"Failed to persist audit log {log_file}: {e}")
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    def log_event(
        self,
        event_type: str,
        camera_node: str = "N/A",
        zone: str = "N/A",
        details: str = "",
        voice_command: str = "",
        agent_response: str = "",
        operator_id: str = "System",
        payload: Optional[Dict[str, Any]] = None,
        dt: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Record an audit event entry with IST and UTC timestamps."""
        now = dt or datetime.now(timezone.utc)
        now_ist = now.astimezone(IST)
        now_utc = now.astimezone(UTC)

        date_key = now_ist.strftime("%Y-%m-%d")
        timestamp_ist = now_ist.strftime("%Y-%m-%d %H:%M:%S IST")
        timestamp_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        log_id = f"AUD-{now_ist.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

        record: Dict[str, Any] = {
            "log_id": log_id,
            "timestamp_ist": timestamp_ist,
            "timestamp_utc": timestamp_utc,
            "event_type": event_type,
            "camera_node": camera_node,
            "zone": zone,
            "details": details,
            "voice_command": voice_command,
            "agent_response": agent_response,
            "operator_id": operator_id,
            "payload": payload or {},
        }

        with self._store_lock:
            records = self._load_logs_for_date(date_key)
            records.append(record)
            self._cache[date_key] = records
            self._persist_date_logs(date_key, records)

        logger.info(f"Audit log recorded [{event_type}] on {camera_node}: {details[:60]}")
        return record

    def get_logs_for_date(self, date_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all audit logs for a given date (YYYY-MM-DD), newest first."""
        target_date = date_str or self._get_date_key()
        records = self._load_logs_for_date(target_date)
        return list(reversed(records))

    def get_available_dates(self) -> List[str]:
        """Return list of all dates that contain audit log files, newest first."""
        dates = set()
        dates.add(self._get_date_key())

        if AUDIT_DIR.exists():
            for p in AUDIT_DIR.glob("audit_*.json"):
                parts = p.stem.split("_")
                if len(parts) >= 2:
                    dates.add(parts[1])

        return sorted(list(dates), reverse=True)

    def get_logs_range(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve audit logs across a range of dates, newest first."""
        all_dates = self.get_available_dates()
        matched_dates = []

        for d in all_dates:
            if start_date and d < start_date:
                continue
            if end_date and d > end_date:
                continue
            matched_dates.append(d)

        combined_records: List[Dict[str, Any]] = []
        for d in matched_dates:
            combined_records.extend(self._load_logs_for_date(d))

        # Return newest first
        return list(reversed(combined_records))

    def get_all_event_types(self) -> List[str]:
        """Return list of distinct event types found across all available dates."""
        all_dates = self.get_available_dates()
        types = set()
        for d in all_dates:
            for rec in self._load_logs_for_date(d):
                t = rec.get("event_type")
                if t:
                    types.add(t)
        return sorted(list(types))

    def export_csv_records(self, records: List[Dict[str, Any]]) -> str:
        """Format an arbitrary list of audit records as CSV."""
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        headers = [
            "Timestamp (IST)",
            "Timestamp (UTC)",
            "Event Type",
            "Camera Node",
            "Zone",
            "Details",
            "Voice Command",
            "Response",
            "Operator / System",
            "Audit Log ID",
        ]
        writer.writerow(headers)

        for rec in records:
            writer.writerow([
                rec.get("timestamp_ist", ""),
                rec.get("timestamp_utc", ""),
                rec.get("event_type", ""),
                rec.get("camera_node", ""),
                rec.get("zone", ""),
                rec.get("details", ""),
                rec.get("voice_command", ""),
                rec.get("agent_response", ""),
                rec.get("operator_id", ""),
                rec.get("log_id", ""),
            ])

        return output.getvalue()

    def export_csv_for_date(self, date_str: Optional[str] = None) -> str:
        """Generate formatted CSV string for all events on the specified date."""
        target_date = date_str or self._get_date_key()
        records = self._load_logs_for_date(target_date)
        return self.export_csv_records(records)


# Global Singleton Instance
audit_engine = AuditEngine()

