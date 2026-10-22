"""
Root backend entry point delegating to backend.app.main.
Ensures compatibility with both `uvicorn backend.main:app` and `uvicorn backend.app.main:app`.
"""
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
)
from backend.app.access_engine import (
    AccessCorrelationEngine,
    access_engine,
    evaluate_entry_event,
)

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
    "AccessCorrelationEngine",
    "access_engine",
    "evaluate_entry_event",
]

