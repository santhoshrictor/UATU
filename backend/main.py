"""
Root backend entry point delegating to backend.app.main.
Ensures compatibility with both `uvicorn backend.main:app` and `uvicorn backend.app.main:app`.
"""
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

IST = timezone(timedelta(hours=5, minutes=30))


def get_current_ist_timestamp() -> str:
    """Format the alert time using Indian Standard Time (IST / UTC+5:30)."""
    return datetime.now(IST).strftime("%H:%M:%S IST")


def create_hazard_alert_payload(
    camera_id: str = "CAM-05",
    zone: str = "Zone 04 // Tier-3 Data Center Vault",
    timestamp: Optional[int] = None,
) -> Dict[str, Any]:
    """Builds a standardized critical hazard alert payload carrying camera source and zone."""
    now_ts = int(time.time()) if timestamp is None else timestamp
    current_ist_time = get_current_ist_timestamp()
    return {
        "id": f"EVT-HAZARD-{now_ts}",
        "time": current_ist_time,
        "zone": zone,
        "camera": camera_id,
        "type": "CRITICAL HAZARD: FIRE / SMOKE DETECTED",
        "level": "CRITICAL",
        "detail": f"Hazard identified on {camera_id} ({zone}). Immediate evacuation required.",
        "acknowledged": False,
    }


def dispatch_hazard_alert(
    camera_id: str = "CAM-05",
    zone: str = "Zone 04 // Tier-3 Data Center Vault",
    timestamp: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Dispatches a critical hazard alert to WebSocket queue ONLY IF the camera stream
    is verified active. Offline, unassigned, or invalid streams are blocked by circuit breaker.
    """
    if not alert_manager.is_stream_active(camera_id):
        return None
    payload = create_hazard_alert_payload(camera_id, zone, timestamp)
    alert_manager.broadcast_sync(payload)
    return payload


from backend.app.main import (
    app,
    CameraDeviceWorker,
    MultiWebcamManager,
    multi_webcam_manager,
    FileStreamWorker,
    MultiFileStreamManager,
    multi_file_stream_manager,
    get_working_camera,
    get_webcam_manager,
    webcam_manager,
    yolo_model,
    EnrollRequest,
    VerifyAccessRequest,
    generate_file_stream,
    get_camera_telemetry,
    stop_camera_stream,
    detect_face_alignment,
)
from backend.app.biometric_registry import BiometricRegistry, biometric_registry
from backend.app.access_engine import (
    AccessCorrelationEngine,
    access_engine,
    evaluate_entry_event,
)
from backend.app.vision_engine import SpatialTracker
from backend.app.fire_detector import FireDetector
from backend.app.core.websocket_manager import alert_manager

__all__ = [
    "app",
    "CameraDeviceWorker",
    "MultiWebcamManager",
    "multi_webcam_manager",
    "FileStreamWorker",
    "MultiFileStreamManager",
    "multi_file_stream_manager",
    "get_working_camera",
    "get_webcam_manager",
    "webcam_manager",
    "yolo_model",
    "EnrollRequest",
    "VerifyAccessRequest",
    "generate_file_stream",
    "get_camera_telemetry",
    "stop_camera_stream",
    "detect_face_alignment",
    "BiometricRegistry",
    "biometric_registry",
    "AccessCorrelationEngine",
    "access_engine",
    "evaluate_entry_event",
    "SpatialTracker",
    "FireDetector",
    "alert_manager",
    "IST",
    "get_current_ist_timestamp",
    "create_hazard_alert_payload",
    "dispatch_hazard_alert",
]


