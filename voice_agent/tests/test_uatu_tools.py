import copy
from pathlib import Path

import pytest
from livekit.agents.llm import ToolError

from audit_logger import UATUAuditLogger
from conftest import SAMPLE_TEST_EVENTS
from uatu_seed_data import HUMAN_REVIEW_DISCLAIMER
from uatu_tools import UATUTools


@pytest.fixture
def uatu_tools(tmp_path: Path) -> UATUTools:
    log_file = tmp_path / "test_uatu_audit.jsonl"
    events_file = tmp_path / "test_events.json"
    audit_logger = UATUAuditLogger(log_path=log_file)
    tools = UATUTools(
        backend_url="http://127.0.0.1:9999",  # Unused port to guarantee fallback
        audit_logger=audit_logger,
        events_file=events_file,
    )
    # Dynamically inject test fixture events for unit testing so production boots with 0 events
    tools._local_events = copy.deepcopy(SAMPLE_TEST_EVENTS)
    return tools


@pytest.mark.asyncio
async def test_search_after_hours_stores_and_unmatched_access(uatu_tools: UATUTools):
    # Query for Stores 2 after-hours unmatched access
    res = await uatu_tools.search_video_events(
        None,
        zone="Stores 2",
        after_hours_only=True,
        unmatched_access_only=True,
    )
    assert res["status"] == "success"
    assert res["total_matches"] >= 2

    event_ids = {e["event_id"] for e in res["events"]}
    assert "EVT-20261023-0842" in event_ids
    assert "EVT-20261023-2015" in event_ids

    first = res["events"][0]
    assert first["camera_id"] == "CAM-08"
    assert "Stores 2" in first["zone"]
    assert "IST" in first["timestamp_ist"]
    assert first["confidence_pct"] > 85.0
    assert "human_review_notice" in first
    assert first["human_review_notice"] == HUMAN_REVIEW_DISCLAIMER


@pytest.mark.asyncio
async def test_search_canteen_break_exception(uatu_tools: UATUTools):
    res = await uatu_tools.search_video_events(
        None,
        query="canteen",
        min_duration_minutes=45,
    )
    assert res["status"] == "success"
    assert res["total_matches"] >= 1

    event = res["events"][0]
    assert event["event_id"] == "EVT-20261024-0518"
    assert event["camera_id"] == "CAM-07"
    assert event["duration_minutes"] == 58
    assert "Hari Prasath" in event["details"]
    assert "Sandy" in event["details"]
    assert event["human_review_notice"] == HUMAN_REVIEW_DISCLAIMER


@pytest.mark.asyncio
async def test_search_welding_machine_removal_human_review_notice(uatu_tools: UATUTools):
    res = await uatu_tools.search_video_events(
        None,
        query="welding machine",
    )
    assert res["status"] == "success"
    assert res["total_matches"] >= 1

    for ev in res["events"]:
        assert ev["human_review_notice"] == HUMAN_REVIEW_DISCLAIMER
        # Must never claim definitive theft
        details_lower = ev["details"].lower()
        assert "stole" not in details_lower
        assert "theft" not in details_lower or "possible" in details_lower or "review" in details_lower


@pytest.mark.asyncio
async def test_acknowledge_and_escalate_alert(uatu_tools: UATUTools):
    # Acknowledge
    ack_res = await uatu_tools.acknowledge_or_escalate_alert(
        None,
        event_id="EVT-20261023-0842",
        action="ACKNOWLEDGE",
        responder_name="Duty_Officer_Kiran",
        action_notes="Patrol dispatched to Stores 2 raw copper rack",
    )
    assert ack_res["status"] == "success"
    assert ack_res["new_case_status"] == "ACKNOWLEDGED"
    assert ack_res["incident"]["responder_name"] == "Duty_Officer_Kiran"
    assert "IST" in ack_res["updated_at"]

    # Escalate
    esc_res = await uatu_tools.acknowledge_or_escalate_alert(
        None,
        event_id="EVT-20261023-0842",
        action="ESCALATE",
        responder_name="Duty_Officer_Kiran",
        action_notes="Elevated to Security Manager due to unmatched badge",
    )
    assert esc_res["status"] == "success"
    assert esc_res["new_case_status"] == "ESCALATED"

    # Invalid action raises ToolError
    with pytest.raises(ToolError, match="Invalid alert action"):
        await uatu_tools.acknowledge_or_escalate_alert(
            None,
            event_id="EVT-20261023-0842",
            action="INVALID_ACTION",
        )


@pytest.mark.asyncio
async def test_zone_occupancy_and_abnormal_gathering(uatu_tools: UATUTools):
    res = await uatu_tools.get_zone_occupancy_and_traffic(None, camera_id_or_zone="ZONE-02")
    assert res["status"] == "success"
    assert "ZONE-02" in res["zones"]
    z2 = res["zones"]["ZONE-02"]
    assert z2["current_occupancy"] == 6
    assert z2["crowding_threshold"] == 4
    assert z2["abnormal_gathering_active"] is True


@pytest.mark.asyncio
async def test_query_access_control_and_enrolled_users(uatu_tools: UATUTools):
    # Lookup specific employee
    res_emp = await uatu_tools.query_access_control_and_enrolled_users(
        None,
        employee_id="EMP-1234",
    )
    assert res_emp["status"] == "success"
    assert len(res_emp["enrolled_personnel"]) == 1
    assert res_emp["enrolled_personnel"][0]["name"] == "Hari Prasath"

    # Filter by mismatch status
    res_mismatch = await uatu_tools.query_access_control_and_enrolled_users(
        None,
        filter_status="MISMATCH",
    )
    assert res_mismatch["status"] == "success"
    assert any(u["employee_id"] == "EMP-8812" for u in res_mismatch["enrolled_personnel"])


@pytest.mark.asyncio
async def test_generate_daily_incident_summary(uatu_tools: UATUTools):
    res = await uatu_tools.generate_daily_incident_summary(None)
    assert res["status"] == "success"
    summary = res["daily_incident_summary"]

    assert summary["facility"] == "UATU Industrial Node 01"
    assert summary["total_events_recorded"] >= 8
    assert "CRITICAL" in summary["alarms_by_severity"]
    assert summary["alarms_by_severity"]["CRITICAL"] >= 2  # Fall and fire
    assert summary["active_camera_channels"] == 9
    assert summary["access_control_mismatches_flagged"] >= 1
    assert summary["canteen_break_exceptions_recorded"] >= 1


@pytest.mark.asyncio
async def test_get_recent_audit_trail(uatu_tools: UATUTools):
    # Perform an action that logs an audit
    await uatu_tools.search_video_events(None, query="welding machine")

    res = await uatu_tools.get_recent_audit_trail(None, limit=5)
    assert res["status"] == "success"
    assert res["immutable_chain_verified"] is True
    assert res["total_records_retrieved"] >= 1


@pytest.mark.asyncio
async def test_live_backend_mocked_http(tmp_path: Path):
    from aiohttp import web

    log_file = tmp_path / "mock_audit.jsonl"
    logger = UATUAuditLogger(log_path=log_file)

    app = web.Application()

    async def handle_search(request):
        return web.json_response(
            {
                "source": "UATU_LIVE_FASTAPI_BACKEND",
                "events": [
                    {
                        "event_id": "EVT-MOCK-001",
                        "camera_id": "CAM-01",
                        "zone": "Turnstiles",
                        "timestamp_ist": "2026-10-24 12:00:00 IST",
                        "event_type": "ACCESS_OK",
                        "alarm_class": "LOW",
                        "confidence_pct": 99.0,
                        "access_control_correlation": "AUTHORIZED",
                        "snapshot_url": "/snap.jpg",
                        "evidence_clip_url": "/clip.mp4",
                        "case_status": "OPEN",
                    }
                ],
            }
        )

    app.router.add_get("/api/video-events/search", handle_search)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]

    try:
        live_tools = UATUTools(backend_url=f"http://127.0.0.1:{port}", audit_logger=logger)
        res = await live_tools.search_video_events(None, query="test")
        assert res["status"] == "success"
        assert res["source"] == "UATU_LIVE_FASTAPI_BACKEND"
        assert len(res["events"]) == 1
        assert res["events"][0]["event_id"] == "EVT-MOCK-001"
        assert res["events"][0]["human_review_notice"] == HUMAN_REVIEW_DISCLAIMER
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_get_verified_incident_reports(uatu_tools: UATUTools):
    # Fetch verified incidents (min_confidence default 90.0%)
    res = await uatu_tools.get_verified_incident_reports(None, min_confidence=90.0)
    assert res["status"] == "success"
    assert res["filter_applied"]["verified_only"] is True
    assert res["filter_applied"]["noise_filtered"] is True
    assert res["total_verified_incidents"] > 0

    # Ensure all returned events meet high-confidence threshold
    for ev in res["verified_incidents"]:
        assert ev["confidence_pct"] >= 90.0
        assert "human_review_notice" in ev
        assert ev["telemetry_precision_rating"] == "HIGH_CONFIDENCE_VERIFIED"


@pytest.mark.asyncio
async def test_control_platform_ui_layout(uatu_tools: UATUTools):
    # Execute layout expansion to 1x1 on CAM-01
    res = await uatu_tools.control_platform_ui_layout(None, camera_id="CAM-01", layout="1x1")
    assert res["status"] == "success"
    assert res["action"] == "LAYOUT_CHANGE"
    assert res["layout"] == "1x1"
    assert res["camera_id"] == "CAM-01"

    # Test quad layout with shorthand '2'
    res_quad = await uatu_tools.control_platform_ui_layout(None, camera_id="CAM-05", layout="2x2")
    assert res_quad["layout"] == "2x2"
    assert res_quad["camera_id"] == "CAM-05"


@pytest.mark.asyncio
async def test_locate_threat_camera_node_fire_and_smoke(uatu_tools: UATUTools):
    # Query for fire threat node
    res = await uatu_tools.locate_threat_camera_node(None, threat_type="fire")
    assert res["status"] == "success"
    assert res["threat_detected"] is True
    assert res["camera_id"] in {"CAM-05", "CAM-06"}
    assert "Server Room" in res["zone"] or "Western Security" in res["zone"]
    assert res["confidence_pct"] >= 90.0
    assert "human_in_the_loop_mandatory_rule" in res


@pytest.mark.asyncio
async def test_production_boots_with_zero_preseeded_events(tmp_path: Path):
    """Verify that in production (clean startup), all events are 0 and no fallbacks hallucinate."""
    from uatu_seed_data import UATU_EVENTS

    # 1. Seed array must be strictly empty
    assert len(UATU_EVENTS) == 0

    log_file = tmp_path / "prod_boot_audit.jsonl"
    events_file = tmp_path / "prod_boot_events.json"
    audit_logger = UATUAuditLogger(log_path=log_file)
    clean_tools = UATUTools(
        backend_url="http://127.0.0.1:9999",
        audit_logger=audit_logger,
        events_file=events_file,
    )

    # 2. In-memory local events must be strictly empty
    assert len(clean_tools._local_events) == 0

    # 3. search_video_events returns 0 matches and zero-match message
    search_res = await clean_tools.search_video_events(None, query="fire")
    assert search_res["status"] == "success"
    assert search_res["total_matches"] == 0
    assert search_res["events"] == []
    assert "Zero video events matched" in search_res["message"]

    # 4. locate_threat_camera_node returns not_found and all_cameras_nominal
    threat_res = await clean_tools.locate_threat_camera_node(None, threat_type="fire")
    assert threat_res["status"] == "not_found"
    assert threat_res["all_cameras_nominal"] is True
    assert "No active fire threats" in threat_res["message"]

    # 5. get_verified_incident_reports returns 0 incidents
    verified_res = await clean_tools.get_verified_incident_reports(None)
    assert verified_res["status"] == "success"
    assert verified_res["total_verified_incidents"] == 0
    assert verified_res["verified_incidents"] == []
    assert "Zero verified incident reports" in verified_res["message"]

    # 6. generate_daily_incident_summary reports 0 events and truthful nominal advisory
    summary_res = await clean_tools.generate_daily_incident_summary(None)
    assert summary_res["status"] == "success"
    assert summary_res["daily_incident_summary"]["total_events_recorded"] == 0
    assert "operating within nominal parameters" in summary_res["daily_incident_summary"]["operational_advisory"]

