import re
from pathlib import Path

from audit_logger import GENESIS_HASH, UATUAuditLogger


def test_log_event_and_ist_timestamp(tmp_path: Path) -> None:
    log_file = tmp_path / "uatu_audit_test.jsonl"
    logger = UATUAuditLogger(log_path=log_file)

    record = logger.log_event(
        action_type="VOICE_OR_TEXT_QUERY",
        query_or_command="Stores la 7 PM mela yaaru vantha?",
        retrieved_evidence_ids=["EVT-20261024-001", "CAM-05"],
        response_summary="Stores monitored; possible unverified ingress detected. Human review required.",
        human_review_disclaimer_applied=True,
        operator_role="Security_Operator",
    )

    # Check fields
    assert record["audit_id"].startswith("AUD-")
    assert re.match(r"^AUD-\d{8}-[A-F0-9]{6}$", record["audit_id"])

    # Check IST timestamp format (%Y-%m-%d %H:%M:%S IST)
    assert record["timestamp_ist"].endswith(" IST")
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} IST$", record["timestamp_ist"])

    assert record["action_type"] == "VOICE_OR_TEXT_QUERY"
    assert record["query_or_command"] == "Stores la 7 PM mela yaaru vantha?"
    assert record["retrieved_evidence_ids"] == ["EVT-20261024-001", "CAM-05"]
    assert record["human_review_disclaimer_applied"] is True
    assert record["operator_role"] == "Security_Operator"

    # Genesis previous hash
    assert record["previous_hash"] == GENESIS_HASH
    assert len(record["sha256_hash"]) == 64


def test_sha256_hash_chaining(tmp_path: Path) -> None:
    log_file = tmp_path / "audit_chain.jsonl"
    logger = UATUAuditLogger(log_path=log_file)

    rec1 = logger.log_event(
        action_type="SYSTEM_HEALTH_CHECK",
        query_or_command="Inference server GPU check",
        response_summary="GPU 0 RTX 4070 operating at 48C",
    )
    assert rec1["previous_hash"] == GENESIS_HASH

    rec2 = logger.log_event(
        action_type="EVIDENCE_SEARCH",
        query_or_command="CAM-02 fall alert search",
        retrieved_evidence_ids=["EVT-002", "CAM-02"],
        response_summary="Fall detected in Workshop Floor Alpha. Human review required.",
        human_review_disclaimer_applied=True,
    )
    # rec2's previous_hash must match rec1's sha256_hash
    assert rec2["previous_hash"] == rec1["sha256_hash"]
    assert rec2["sha256_hash"] != rec1["sha256_hash"]

    rec3 = logger.log_event(
        action_type="ALERT_ACKNOWLEDGEMENT",
        query_or_command="Acknowledge alert EVT-002",
        retrieved_evidence_ids=["EVT-002"],
        response_summary="Alert acknowledged by operator",
    )
    # rec3's previous_hash must match rec2's sha256_hash
    assert rec3["previous_hash"] == rec2["sha256_hash"]

    # Verify file reload maintains the chain
    logger_reloaded = UATUAuditLogger(log_path=log_file)
    rec4 = logger_reloaded.log_event(
        action_type="VOICE_OR_TEXT_QUERY",
        query_or_command="Status CAM-07",
        response_summary="Server room vault perimeter secure",
    )
    assert rec4["previous_hash"] == rec3["sha256_hash"]


def test_get_recent_audit_logs(tmp_path: Path) -> None:
    log_file = tmp_path / "recent_logs.jsonl"
    logger = UATUAuditLogger(log_path=log_file)

    # Empty initially
    assert logger.get_recent_audit_logs() == []

    # Add 5 events
    for idx in range(5):
        logger.log_event(
            action_type="VOICE_OR_TEXT_QUERY",
            query_or_command=f"Query {idx}",
            response_summary=f"Summary {idx}",
        )

    all_logs = logger.get_recent_audit_logs(limit=10)
    assert len(all_logs) == 5
    assert all_logs[0]["query_or_command"] == "Query 0"
    assert all_logs[-1]["query_or_command"] == "Query 4"

    # Test limit clamping
    recent_two = logger.get_recent_audit_logs(limit=2)
    assert len(recent_two) == 2
    assert recent_two[0]["query_or_command"] == "Query 3"
    assert recent_two[1]["query_or_command"] == "Query 4"
