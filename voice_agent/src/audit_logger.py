"""Immutable prompt and evidence audit logger for UATU."""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

GENESIS_HASH = "0" * 64
IST_ZONE = ZoneInfo("Asia/Kolkata")


class UATUAuditLogger:
    """Tamper-evident, hash-chained audit logger for UATU operator queries and decisions."""

    def __init__(self, log_path: Path | str | None = None) -> None:
        if log_path is None:
            # Default to logs/uatu_audit_trail.jsonl in the project root
            base_dir = Path(__file__).resolve().parents[1]
            self.log_path = base_dir / "logs" / "uatu_audit_trail.jsonl"
        else:
            self.log_path = Path(log_path)

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._last_hash = self._read_last_hash()

    def _read_last_hash(self) -> str:
        """Read the SHA-256 hash of the most recent record, or return GENESIS_HASH."""
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            return GENESIS_HASH

        try:
            with open(self.log_path, encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                if not lines:
                    return GENESIS_HASH
                last_record = json.loads(lines[-1])
                return str(last_record.get("sha256_hash", GENESIS_HASH))
        except Exception:
            return GENESIS_HASH

    def log_event(
        self,
        action_type: str,
        query_or_command: str = "",
        retrieved_evidence_ids: list[str] | None = None,
        response_summary: str = "",
        human_review_disclaimer_applied: bool = False,
        operator_role: str = "Security_Operator",
    ) -> dict:
        """Append an immutable, hash-chained audit record.

        Args:
            action_type: Type of action (e.g. VOICE_OR_TEXT_QUERY, EVIDENCE_SEARCH, ALERT_ACKNOWLEDGEMENT, SYSTEM_HEALTH_CHECK).
            query_or_command: User query or command string.
            retrieved_evidence_ids: List of evidence or event IDs referenced.
            response_summary: Summary of AI response or action taken.
            human_review_disclaimer_applied: Whether the human-review uncertainty disclaimer was applied.
            operator_role: Role of operator conducting the query.

        Returns:
            The complete audit record dictionary.
        """
        evidence_ids = list(retrieved_evidence_ids) if retrieved_evidence_ids else []
        now_ist = datetime.now(IST_ZONE)
        audit_id = f"AUD-{now_ist.strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"
        timestamp_ist = now_ist.strftime("%Y-%m-%d %H:%M:%S IST")

        with self._lock:
            previous_hash = self._last_hash

            payload = {
                "audit_id": audit_id,
                "timestamp_ist": timestamp_ist,
                "operator_role": operator_role,
                "action_type": action_type,
                "query_or_command": query_or_command,
                "retrieved_evidence_ids": evidence_ids,
                "response_summary": response_summary,
                "human_review_disclaimer_applied": human_review_disclaimer_applied,
                "previous_hash": previous_hash,
            }

            canonical_string = json.dumps(payload, sort_keys=True)
            sha256_hash = hashlib.sha256(canonical_string.encode("utf-8")).hexdigest()

            record = {
                **payload,
                "sha256_hash": sha256_hash,
            }

            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")

            self._last_hash = sha256_hash
            return record

    def get_recent_audit_logs(self, limit: int = 10) -> list[dict]:
        """Fetch up to `limit` most recent audit records from the log file.

        Args:
            limit: Maximum number of recent records to return.

        Returns:
            List of parsed audit record dictionaries in chronological order.
        """
        if not self.log_path.exists() or self.log_path.stat().st_size == 0:
            return []

        with self._lock:
            try:
                with open(self.log_path, encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
                    selected = lines[-max(1, limit) :]
                    return [json.loads(line) for line in selected]
            except Exception:
                return []
