"""
Root backend entry point delegating to backend.app.main.
Ensures compatibility with both `uvicorn backend.main:app` and `uvicorn backend.app.main:app`.
"""
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))


def get_current_ist_timestamp() -> str:
    """Format the alert time using Indian Standard Time (IST / UTC+5:30)."""
    return datetime.now(IST).strftime("%H:%M:%S IST")


from backend.app.main import (
    app,
    CameraDeviceWorker,
    MultiWebcamManager,
    multi_webcam_manager,
    get_working_camera,
    get_webcam_manager,
    webcam_manager,
    yolo_model,
    EnrollRequest,
    VerifyAccessRequest,
    generate_file_stream,
)
from backend.app.access_engine import (
    AccessCorrelationEngine,
    access_engine,
    evaluate_entry_event,
)
from backend.app.vision_engine import SpatialTracker
from backend.app.core.websocket_manager import alert_manager

__all__ = [
    "app",
    "CameraDeviceWorker",
    "MultiWebcamManager",
    "multi_webcam_manager",
    "get_working_camera",
    "get_webcam_manager",
    "webcam_manager",
    "yolo_model",
    "EnrollRequest",
    "VerifyAccessRequest",
    "generate_file_stream",
    "AccessCorrelationEngine",
    "access_engine",
    "evaluate_entry_event",
    "SpatialTracker",
    "alert_manager",
    "IST",
    "get_current_ist_timestamp",
]

