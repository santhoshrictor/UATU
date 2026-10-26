from unittest.mock import MagicMock

import pytest

from hardware_tools import HardwareTools, _get_gpu_telemetry


def test_hardware_tools_registration():
    tools = HardwareTools()
    assert len(tools.tools) == 4
    tool_names = {t.__name__ for t in tools.tools}
    assert tool_names == {
        "get_hardware_status",
        "get_security_and_network_audit",
        "get_camera_and_stream_health",
        "calculate_and_audit_video_storage",
    }


@pytest.mark.asyncio
async def test_get_hardware_status():
    tools = HardwareTools()
    status = await tools.get_hardware_status(None)

    assert "cpu" in status
    assert "usage_percent" in status["cpu"]
    assert "memory" in status
    assert "total_gb" in status["memory"]
    assert "percent_used" in status["memory"]
    assert "disk" in status
    assert "total_gb" in status["disk"]
    assert "network" in status


def test_gpu_telemetry_mocked(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda cmd: "C:\\Windows\\System32\\nvidia-smi.exe")
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "NVIDIA GeForce RTX 4070, 48, 15, 2048, 12288, 35.5\n"
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: mock_res)

    gpu = _get_gpu_telemetry()
    assert gpu is not None
    assert gpu["model"] == "NVIDIA GeForce RTX 4070"
    assert gpu["temperature_celsius"] == 48
    assert gpu["core_utilization_percent"] == 15
    assert gpu["vram_used_mb"] == 2048
    assert gpu["vram_total_mb"] == 12288
    assert gpu["power_draw_watts"] == 35.5


def test_gpu_telemetry_unavailable(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    gpu = _get_gpu_telemetry()
    assert gpu is None


@pytest.mark.asyncio
async def test_get_security_and_network_audit():
    tools = HardwareTools()
    res = await tools.get_security_and_network_audit(None)
    assert "local_ip" in res
    assert "total_listening_ports" in res
    assert "security_status" in res


@pytest.mark.asyncio
async def test_get_camera_and_stream_health_nominal():
    tools = HardwareTools()
    res = await tools.get_camera_and_stream_health(None, camera_id="ALL")

    assert res["status"] == "success"
    assert res["total_channels"] == 9
    assert "CAM-01" in res["cameras"]
    assert "CAM-05" in res["cameras"]
    assert "CAM-09" in res["cameras"]

    # In default seed, cameras are online with 25-30 FPS
    cam1 = res["cameras"]["CAM-01"]
    assert cam1["is_online"] is True
    assert cam1["fps"] in {25, 30}
    assert cam1["stream_health_guard"] == "ACTIVE_NOMINAL"
    assert cam1["is_critical_zone"] is True


@pytest.mark.asyncio
async def test_get_camera_and_stream_health_offline_and_critical_flag(monkeypatch):
    tools = HardwareTools()

    # Simulate backend returning CAM-05 (Server room vault) as offline
    def mock_telemetry(*args, **kwargs):
        class MockResp:
            status = 200

            async def json(self):
                return {
                    "cameras": {
                        "CAM-05": {"is_online": False, "fps": 0},
                    }
                }

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                pass

        return MockResp()

    monkeypatch.setattr("aiohttp.ClientSession.get", mock_telemetry)

    res = await tools.get_camera_and_stream_health(None, camera_id="ALL")
    cam5 = res["cameras"]["CAM-05"]

    # Strictly 0 FPS when offline
    assert cam5["is_online"] is False
    assert cam5["fps"] == 0
    assert cam5["stream_health_guard"] == "STREAM_OFFLINE_CIRCUIT_BREAKER_TRIPPED"
    assert cam5["is_critical_zone"] is True

    # Must flag critical-zone offline alert
    assert len(res["critical_offline_alerts"]) >= 1
    assert any("CAM-05" in a for a in res["critical_offline_alerts"])
    assert res["system_health"] == "DEGRADED_CRITICAL"


@pytest.mark.asyncio
async def test_calculate_and_audit_video_storage_spec_benchmark():
    tools = HardwareTools()
    # 16 cameras @ 4 Mbps for 30 days = exactly 691.2 GB/day and ~20.7 TB
    res = await tools.calculate_and_audit_video_storage(
        None,
        num_cameras=16,
        avg_bitrate_mbps=4.0,
        retention_days=30,
    )
    assert res["status"] == "success"
    assert res["storage_gb_per_day"] == 691.2
    assert res["total_retention_gb"] == 20736.0
    assert res["total_retention_tb"] == 20.74
    assert "24-40 TB" in res["recommended_raid_architecture"]
    assert "local_storage_audit" in res


@pytest.mark.asyncio
async def test_video_storage_warning_thresholds(monkeypatch):
    tools = HardwareTools()

    class MockDisk:
        def __init__(self, pct):
            self.percent = pct
            self.total = 1000 * (1024**3)
            self.free = (1000 - pct * 10) * (1024**3)

    # 1. Nominal (< 70%)
    monkeypatch.setattr("psutil.disk_usage", lambda path: MockDisk(65.0))
    res_nom = await tools.calculate_and_audit_video_storage(None)
    assert res_nom["local_storage_audit"]["threshold_status"] == "NOMINAL"

    # 2. Warning (>= 70% and < 80%)
    monkeypatch.setattr("psutil.disk_usage", lambda path: MockDisk(75.0))
    res_warn = await tools.calculate_and_audit_video_storage(None)
    assert res_warn["local_storage_audit"]["threshold_status"] == "WARNING"

    # 3. High Warning (>= 80% and < 90%)
    monkeypatch.setattr("psutil.disk_usage", lambda path: MockDisk(85.0))
    res_high = await tools.calculate_and_audit_video_storage(None)
    assert res_high["local_storage_audit"]["threshold_status"] == "HIGH_WARNING"

    # 4. Critical Capacity (>= 90%)
    monkeypatch.setattr("psutil.disk_usage", lambda path: MockDisk(92.0))
    res_crit = await tools.calculate_and_audit_video_storage(None)
    assert res_crit["local_storage_audit"]["threshold_status"] == "CRITICAL_CAPACITY"
