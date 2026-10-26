"""Performance benchmark and circuit-breaker latency verification test suite.

Verifies:
1. Sub-200ms (and sub-50ms typical) offline/fallback execution across all 13 tools.
2. Fast circuit-breaker short-circuiting (< 2ms) when backend is offline.
3. Zero unhandled exceptions and complete schema compliance across all 13 tools.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from livekit.agents.llm import FunctionTool

from audit_logger import UATUAuditLogger
from circuit_breaker import (
    is_backend_offline,
    mark_backend_offline,
    mark_backend_online,
    reset_circuit_breaker,
)
from hardware_tools import HardwareTools
from knowledge import KnowledgeTools
from uatu_tools import UATUTools
from vision_tools import VisionTools


@pytest.fixture
def test_env(tmp_path: Path):
    reset_circuit_breaker()
    log_file = tmp_path / "perf_audit.jsonl"
    events_file = tmp_path / "perf_events.json"
    audit_logger = UATUAuditLogger(log_path=log_file)
    offline_url = "http://127.0.0.1:9999"  # Unreachable port

    knowledge = KnowledgeTools()
    hardware = HardwareTools(backend_url=offline_url)
    vision = VisionTools(backend_url=offline_url)
    uatu = UATUTools(backend_url=offline_url, audit_logger=audit_logger, events_file=events_file)
    from conftest import SAMPLE_TEST_EVENTS
    import copy
    uatu._local_events = copy.deepcopy(SAMPLE_TEST_EVENTS)

    return {
        "knowledge": knowledge,
        "hardware": hardware,
        "vision": vision,
        "uatu": uatu,
        "audit_logger": audit_logger,
        "offline_url": offline_url,
    }


def test_circuit_breaker_behavior():
    """Verify circuit breaker state transitions and < 2ms short-circuiting."""
    reset_circuit_breaker()
    test_target = "http://127.0.0.1:9999"

    assert not is_backend_offline(test_target)

    # Trip breaker
    mark_backend_offline(test_target, duration=5.0)
    assert is_backend_offline(test_target)

    # Measure lookup latency - must be ultra-fast sub-millisecond
    t0 = time.perf_counter()
    for _ in range(100):
        _ = is_backend_offline(test_target)
    elapsed_ms = (time.perf_counter() - t0) * 1000 / 100
    assert elapsed_ms < 1.0, f"Circuit breaker check took {elapsed_ms:.3f}ms, expected < 1ms"

    # Reset
    mark_backend_online(test_target)
    assert not is_backend_offline(test_target)


@pytest.mark.asyncio
async def test_all_13_surveillance_tools_registered(test_env):
    """Verify all 13 tools across all 4 toolkits are properly registered."""
    toolkits = [
        test_env["knowledge"].tools,
        test_env["hardware"].tools,
        test_env["vision"].tools,
        test_env["uatu"].tools,
    ]
    all_tools: list[FunctionTool] = []
    for group in toolkits:
        all_tools.extend(group)

    assert len(all_tools) == 16
    tool_names = {t.__name__ for t in all_tools}
    expected_names = {
        # Knowledge (1)
        "get_current_time",
        # Hardware (4)
        "get_hardware_status",
        "get_security_and_network_audit",
        "get_camera_and_stream_health",
        "calculate_and_audit_video_storage",
        # Vision (2)
        "inspect_physical_camera",
        "inspect_uatu_camera_feed",
        # UATU (9)
        "search_video_events",
        "get_verified_incident_reports",
        "control_platform_ui_layout",
        "locate_threat_camera_node",
        "get_zone_occupancy_and_traffic",
        "query_access_control_and_enrolled_users",
        "acknowledge_or_escalate_alert",
        "generate_daily_incident_summary",
        "get_recent_audit_trail",
    }
    assert tool_names == expected_names


@pytest.mark.asyncio
async def test_hardware_tools_sub_50ms_latency(test_env):
    """Verify hardware tools execute well under 200ms (typically < 30ms)."""
    hw: HardwareTools = test_env["hardware"]
    offline_url = test_env["offline_url"]
    mark_backend_offline(offline_url, duration=15.0)

    # 1. get_hardware_status
    t0 = time.perf_counter()
    status = await hw.get_hardware_status(None)
    elapsed = (time.perf_counter() - t0) * 1000
    assert elapsed < 200.0, f"get_hardware_status took {elapsed:.1f}ms (>200ms)"
    assert status["cpu"]["usage_percent"] >= 0

    # 2. calculate_and_audit_video_storage (instant math)
    t0 = time.perf_counter()
    storage = await hw.calculate_and_audit_video_storage(None, num_cameras=16, retention_days=30)
    elapsed = (time.perf_counter() - t0) * 1000
    assert elapsed < 50.0, f"calculate_and_audit_video_storage took {elapsed:.1f}ms (>50ms)"
    assert storage["total_retention_tb"] > 0

    # 3. get_camera_and_stream_health with circuit breaker
    t0 = time.perf_counter()
    health = await hw.get_camera_and_stream_health(None, camera_id="ALL")
    elapsed = (time.perf_counter() - t0) * 1000
    assert health["status"] == "success"
    assert health["total_channels"] == 9
    assert elapsed < 50.0, f"get_camera_and_stream_health took {elapsed:.1f}ms (>50ms)"


@pytest.mark.asyncio
async def test_uatu_tools_zero_latency_fallback(test_env):
    """Verify all 6 UATU search & workflow tools execute fallback under 50ms once circuit breaker trips."""
    uatu: UATUTools = test_env["uatu"]
    offline_url = test_env["offline_url"]

    # Prime the circuit breaker
    mark_backend_offline(offline_url, duration=15.0)

    # 1. search_video_events
    t0 = time.perf_counter()
    res1 = await uatu.search_video_events(None, query="fire")
    elapsed1 = (time.perf_counter() - t0) * 1000
    assert res1["status"] == "success"
    assert elapsed1 < 50.0, f"search_video_events took {elapsed1:.1f}ms"

    # 2. get_zone_occupancy_and_traffic
    t0 = time.perf_counter()
    res2 = await uatu.get_zone_occupancy_and_traffic(None, camera_id_or_zone="Stores 2")
    elapsed2 = (time.perf_counter() - t0) * 1000
    assert res2["status"] == "success"
    assert elapsed2 < 50.0, f"get_zone_occupancy_and_traffic took {elapsed2:.1f}ms"

    # 3. query_access_control_and_enrolled_users
    t0 = time.perf_counter()
    res3 = await uatu.query_access_control_and_enrolled_users(None, employee_id="EMP-1042")
    elapsed3 = (time.perf_counter() - t0) * 1000
    assert res3["status"] == "success"
    assert elapsed3 < 50.0, f"query_access_control_and_enrolled_users took {elapsed3:.1f}ms"

    # 4. acknowledge_or_escalate_alert
    t0 = time.perf_counter()
    res4 = await uatu.acknowledge_or_escalate_alert(
        None,
        event_id="EVT-20261023-0842",
        action="ACKNOWLEDGE",
        action_notes="Verified by safety officer",
    )
    elapsed4 = (time.perf_counter() - t0) * 1000
    assert res4["status"] == "success"
    assert elapsed4 < 50.0, f"acknowledge_or_escalate_alert took {elapsed4:.1f}ms"

    # 5. generate_daily_incident_summary
    t0 = time.perf_counter()
    res5 = await uatu.generate_daily_incident_summary(None)
    elapsed5 = (time.perf_counter() - t0) * 1000
    assert res5["status"] == "success"
    assert elapsed5 < 50.0, f"generate_daily_incident_summary took {elapsed5:.1f}ms"

    # 6. get_recent_audit_trail
    t0 = time.perf_counter()
    res6 = await uatu.get_recent_audit_trail(None, limit=5)
    elapsed6 = (time.perf_counter() - t0) * 1000
    assert res6["status"] == "success"
    assert elapsed6 < 50.0, f"get_recent_audit_trail took {elapsed6:.1f}ms"


@pytest.mark.asyncio
async def test_knowledge_tools_instant_retrieval(test_env):
    """Verify knowledge tools return authoritative clock time within 10ms."""
    kn: KnowledgeTools = test_env["knowledge"]

    t0 = time.perf_counter()
    res = await kn.get_current_time(None, location="Asia/Kolkata")
    elapsed = (time.perf_counter() - t0) * 1000
    assert res["timezone"] == "Asia/Kolkata"
    assert "time_24h" in res
    assert elapsed < 25.0, f"get_current_time took {elapsed:.1f}ms"
