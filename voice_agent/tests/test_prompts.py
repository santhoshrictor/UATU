from prompts import (
    AGENT_INSTRUCTIONS,
    INITIAL_GREETING,
)


def test_uatu_identity_and_9_camera_matrix() -> None:
    assert "UATU" in AGENT_INSTRUCTIONS
    assert "Unified Assistant for Threat & Understanding" in AGENT_INSTRUCTIONS
    assert "video intelligence and workplace safety" in AGENT_INSTRUCTIONS.lower()

    # Verify 9-camera matrix coverage (CAM-01 to CAM-09)
    for cam_idx in range(1, 10):
        cam_id = f"CAM-0{cam_idx}"
        assert cam_id in AGENT_INSTRUCTIONS

    # Verify key operational zones
    assert "Turnstiles" in AGENT_INSTRUCTIONS
    assert "Workshop" in AGENT_INSTRUCTIONS
    assert "Canteen" in AGENT_INSTRUCTIONS
    assert "Stores" in AGENT_INSTRUCTIONS
    assert "Tool Room" in AGENT_INSTRUCTIONS
    assert "Server Room Vault" in AGENT_INSTRUCTIONS
    assert "Security Barriers" in AGENT_INSTRUCTIONS


def test_mandatory_human_review_and_uncertainty_guardrails() -> None:
    # Human verification rule
    assert "human verification is required" in AGENT_INSTRUCTIONS.lower()
    assert "decision-support" in AGENT_INSTRUCTIONS.lower()

    # Rule never claiming a person stole an item
    assert "never claim definitively that a person \"stole\" an item" in AGENT_INSTRUCTIONS.lower() or (
        "stole" in AGENT_INSTRUCTIONS.lower() and "never" in AGENT_INSTRUCTIONS.lower()
    )

    # Prohibition of automatic disciplinary/salary/termination action
    assert "disciplinary action" in AGENT_INSTRUCTIONS.lower()
    assert "salary deduction" in AGENT_INSTRUCTIONS.lower()
    assert "termination" in AGENT_INSTRUCTIONS.lower()


def test_evidence_grounded_requirements() -> None:
    # Mandatory citation fields for incident queries
    assert "Event ID" in AGENT_INSTRUCTIONS
    assert "Camera ID" in AGENT_INSTRUCTIONS
    assert "Zone Name" in AGENT_INSTRUCTIONS
    assert "IST Timestamp" in AGENT_INSTRUCTIONS
    assert "Confidence Score" in AGENT_INSTRUCTIONS
    assert "Access-Control Correlation" in AGENT_INSTRUCTIONS
    assert "Evidence Clip" in AGENT_INSTRUCTIONS or "Snapshot" in AGENT_INSTRUCTIONS


def test_bilingual_english_tamil_tanglish_support() -> None:
    assert "English" in AGENT_INSTRUCTIONS
    assert "Tamil" in AGENT_INSTRUCTIONS
    assert "Tanglish" in AGENT_INSTRUCTIONS


def test_privacy_and_biometric_compliance() -> None:
    assert "toilets" in AGENT_INSTRUCTIONS.lower()
    assert "changing rooms" in AGENT_INSTRUCTIONS.lower()
    assert "prayer" in AGENT_INSTRUCTIONS.lower()


def test_initial_session_greeting() -> None:
    assert (
        INITIAL_GREETING
        == "UATU Command Center online. All on-premise safety and video intelligence feeds are ready for query."
    )


def test_active_tools_in_instructions() -> None:
    assert "get_current_time" in AGENT_INSTRUCTIONS
    assert "get_hardware_status" in AGENT_INSTRUCTIONS
    assert "get_security_and_network_audit" in AGENT_INSTRUCTIONS
    assert "get_camera_and_stream_health" in AGENT_INSTRUCTIONS
    assert "calculate_and_audit_video_storage" in AGENT_INSTRUCTIONS
    assert "inspect_physical_camera" in AGENT_INSTRUCTIONS
    assert "inspect_uatu_camera_feed" in AGENT_INSTRUCTIONS
    assert "search_video_events" in AGENT_INSTRUCTIONS
    assert "acknowledge_or_escalate_alert" in AGENT_INSTRUCTIONS
    assert "generate_daily_incident_summary" in AGENT_INSTRUCTIONS
