import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

from pathlib import Path
import pickle
import sys
import threading
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
import uuid

import cv2
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import numpy as np
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.api.v1.api import api_router
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.core.websocket_manager import alert_manager
from backend.app.vision_engine import SpatialTracker

# Base directory for uploads and video assets
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------------------------
# InsightFace Initialization for Biometric Live Enrollment
# -----------------------------------------------------------------------------
INSIGHTFACE_ROOT = BACKEND_DIR / "models" / "insightface"
candidate_roots = [
    INSIGHTFACE_ROOT,
    BACKEND_DIR / "models",
]
target_face_root = next(
    (p for p in candidate_roots if (p / "models" / "buffalo_l").exists() or (p / "buffalo_l").exists()),
    INSIGHTFACE_ROOT,
)

face_analysis_app = None
try:
    from insightface.app import FaceAnalysis
    import torch

    has_cuda = torch.cuda.is_available()
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if has_cuda else ["CPUExecutionProvider"]
    logger.info(f"Initializing FaceAnalysis (buffalo_l) from root: {target_face_root} with providers: {providers}...")
    face_analysis_app = FaceAnalysis(
        name="buffalo_l",
        root=str(target_face_root),
        providers=providers,
    )
    face_analysis_app.prepare(ctx_id=0 if has_cuda else -1, det_size=(640, 640))
    logger.info("FaceAnalysis pipeline ready for live GUI enrollment.")
except Exception as e:
    logger.warning(f"Could not initialize live FaceAnalysis: {e}. Check models in {INSIGHTFACE_ROOT}.")
UPLOADS_DIR = BACKEND_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
MOCK_DB_PATH = BACKEND_DIR / "mock_employee_db.pkl"
from backend.app.biometric_registry import biometric_registry
biometric_registry.db_path = MOCK_DB_PATH


# -----------------------------------------------------------------------------
# YOLOv8 Person Detection Initialization
# -----------------------------------------------------------------------------
yolo_model = None
try:
    from ultralytics import YOLO

    yolo_model = YOLO("yolov8n.pt")
    logger.info("YOLOv8 person detector initialized successfully.")
except Exception as e:
    logger.warning(f"Could not initialize YOLOv8: {e}")

# Locate test_video.mp4
TEST_VIDEO_PATHS = [
    BACKEND_DIR / "test_video.mp4",
    WORKSPACE_ROOT / "test_video.mp4",
    BACKEND_DIR / "uploads" / "test_video.mp4",
]


def get_test_video_path() -> Path:
    for p in TEST_VIDEO_PATHS:
        if p.exists():
            return p
    return TEST_VIDEO_PATHS[0]


def generate_offline_frame(
    title: str = "UATU // NO SIGNAL",
    subtitle: str = "CAMERA FEED UNAVAILABLE",
    width: int = 640,
    height: int = 360,
) -> bytes:
    """Generates an industrial high-contrast standby/offline MJPEG test pattern frame."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # Dark slate background #020617
    frame[:] = (23, 6, 2)

    # Grid lines
    for x in range(0, width, 40):
        cv2.line(frame, (x, 0), (x, height), (44, 30, 20), 1)
    for y in range(0, height, 40):
        cv2.line(frame, (0, y), (width, y), (44, 30, 20), 1)

    # Outer border reticle
    cv2.rectangle(frame, (10, 10), (width - 10, height - 10), (51, 65, 85), 1)

    # Status indicators
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    cv2.circle(frame, (35, height // 2 - 12), 7, (68, 68, 239), -1)  # Coral red dot
    cv2.putText(
        frame,
        title,
        (55, height // 2 - 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (248, 250, 252),
        2,
    )
    cv2.putText(
        frame,
        subtitle,
        (55, height // 2 + 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (148, 163, 184),
        1,
    )

    # Telemetry footer with unified UATU branding
    cv2.putText(
        frame,
        f"UATU // EDGE SYSTEM // {now_str}",
        (20, height - 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (100, 116, 139),
        1,
    )

    _, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return encoded.tobytes()


def generate_clean_raw_offline_frame(
    title: str = "UATU // STANDBY",
    subtitle: str = "CLEAN RAW VIDEO STREAM",
    width: int = 640,
    height: int = 480,
) -> bytes:
    """Generates a clean raw standby frame with NO grid lines, crosshairs, border reticles, or target boxes."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (23, 6, 2)
    cv2.circle(frame, (35, height // 2 - 12), 7, (68, 68, 239), -1)
    cv2.putText(
        frame,
        title,
        (55, height // 2 - 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (248, 250, 252),
        2,
    )
    cv2.putText(
        frame,
        subtitle,
        (55, height // 2 + 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        (148, 163, 184),
        1,
    )
    _, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    return encoded.tobytes()


# =============================================================================
# SINGLETON THREADED WEBCAM MANAGER (DIRECTSHOW ON WINDOWS)
# =============================================================================


def get_working_camera(preferred_indices=(0, 1, 2)):
    """
    Attempts to initialize physical hardware cameras across multiple indices.
    Prioritizes index 0 for the physical laptop webcam (cv2.VideoCapture(0)).
    """
    for idx in preferred_indices:
        try:
            if sys.platform.startswith("win"):
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(idx)

            if cap is not None and cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 30)
                ret, test_frame = cap.read()
                if ret and test_frame is not None:
                    logger.info(
                        f"Hardware camera successfully acquired on index {idx} "
                        f"({test_frame.shape[1]}x{test_frame.shape[0]})."
                    )
                    return cap, idx
                cap.release()
        except Exception as e:
            logger.warning(f"Could not initialize camera index {idx}: {e}")
    return None, None


class CameraDeviceWorker:
    """Thread-safe capture worker for a specific video hardware/virtual device index."""

    def __init__(self, device_id: int = 0):
        self.device_id = device_id
        if device_id == 0:
            self.camera_id = "CAM-01"
            self.zone_name = "Zone 01 // Main Turnstile North"
        elif device_id == 1:
            self.camera_id = "CAM-02"
            self.zone_name = "Zone 01 // Optical Turnstile B"
        else:
            self.camera_id = f"CAM-{device_id:02d}"
            self.zone_name = f"Zone {device_id:02d} // DirectShow Device"

        self.running = False
        self.cap = None
        self.current_jpeg: bytes = generate_offline_frame(
            f"UATU // DEV-{device_id} INITIALIZING",
            f"CONNECTING TO DIRECTSHOW DEVICE {device_id}...",
        )
        self.raw_jpeg: bytes = generate_clean_raw_offline_frame(
            f"UATU // DEV-{device_id} STANDBY",
            "CLEAN RAW VIDEO STREAM",
        )
        self.frame_lock = threading.Lock()
        self.worker_thread = None
        self.is_live = False
        self.is_webcam = True
        # For physical webcams (CAM-01 / laptop feed), completely disable background environmental fire/smoke heuristics
        self.tracker = SpatialTracker(
            camera_id=self.camera_id,
            zone=self.zone_name,
            is_webcam=True,
            enable_fire_detection=False,
        )
        self.last_crowd_alert_time = 0.0
        self.crowd_alert_cooldown = 15.0
        self.last_fall_alert_time = 0.0
        self.fall_alert_cooldown = 15.0
        self.last_fire_alert_time = 0.0
        self.fire_alert_cooldown = 15.0
        self.current_fps = 0.0

    def _open_capture(self):
        try:
            if sys.platform.startswith("win"):
                cap = cv2.VideoCapture(self.device_id, cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(self.device_id)

            if cap is not None and cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, 30)
                ret, test_frame = cap.read()
                if ret and test_frame is not None:
                    self.is_live = True
                    logger.info(
                        f"Hardware device {self.device_id} acquired successfully ({test_frame.shape[1]}x{test_frame.shape[0]})"
                    )
                    return cap
                cap.release()
        except Exception as e:
            logger.warning(f"Error opening camera device index {self.device_id}: {e}")
        return None

    def _run(self):
        consecutive_errors = 0
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                alert_manager.pause_stream_dispatch(self.camera_id)
                self.cap = self._open_capture()
                if self.cap is None:
                    self.is_live = False
                    self.current_fps = 0.0
                    # Stream Health Guard: skip AI inference, suppress alerts, and return offline signal frame
                    offline_frame, _ = self.tracker.process_frame(None, ret=False)
                    _, encoded = cv2.imencode(
                        ".jpg", offline_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                    )
                    clean_raw = generate_clean_raw_offline_frame(
                        f"UATU // DEV-{self.device_id} STANDBY",
                        "CLEAN RAW VIDEO STREAM",
                    )
                    with self.frame_lock:
                        self.current_jpeg = encoded.tobytes()
                        self.raw_jpeg = clean_raw
                    time.sleep(1.0)
                    continue

            ret, frame = self.cap.read()
            if ret and frame is not None and frame.size > 0:
                consecutive_errors = 0
                self.is_live = True
                alert_manager.resume_stream_dispatch(self.camera_id)

                # Capture pristine un-annotated copy with memory isolation (no geometric overlays)
                raw_frame = frame.copy()
                _, raw_encoded = cv2.imencode(
                    ".jpg", raw_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                )
                raw_bytes = raw_encoded.tobytes()

                # Feature 1-4, 15-17 (ByteTrack, Tripwire, Occupancy HUD, Fall Detection) with Stream Health Guard
                annotated_frame, counts = self.tracker.process_frame(frame, ret=ret)
                self.current_fps = counts.get("fps", 30.0)

                # Skip alert processing if stream health check failed or stream is inactive
                if not counts.get("stream_healthy", False) or not self.is_live or not self.tracker.is_stream_active or not alert_manager.is_stream_active(self.camera_id):
                    self.current_fps = 0.0
                    alert_manager.pause_stream_dispatch(self.camera_id)
                    _, encoded = cv2.imencode(
                        ".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                    )
                    with self.frame_lock:
                        self.current_jpeg = encoded.tobytes()
                        self.raw_jpeg = raw_bytes
                    time.sleep(0.033)
                    continue

                # Feature 15 WebSocket Alert Engine: dispatch when is_crowded with 15s cooldown
                if counts.get("is_crowded"):
                    now_ts = time.time()
                    if (now_ts - self.last_crowd_alert_time) >= self.crowd_alert_cooldown:
                        self.last_crowd_alert_time = now_ts
                        alert_payload = {
                            "id": f"EVT-CROWD-{int(now_ts)}",
                            "time": datetime.now(IST).strftime("%H:%M:%S IST"),
                            "zone": self.zone_name,
                            "camera": self.camera_id,
                            "type": "ABNORMAL GATHERING",
                            "level": "CRITICAL",
                            "detail": f"Occupancy threshold breached on {self.camera_id} ({self.zone_name}).",
                            "acknowledged": False,
                        }
                        logger.warning(
                            f"WebSocket Alert Fired from Device {self.device_id}: {alert_payload}"
                        )
                        alert_manager.broadcast_sync(alert_payload)

                # Feature 17 Fall Detection: dispatch when fall_detected with 15s cooldown
                if counts.get("fall_detected"):
                    now_ts = time.time()
                    if (now_ts - self.last_fall_alert_time) >= self.fall_alert_cooldown:
                        self.last_fall_alert_time = now_ts
                        fall_payload = {
                            "id": f"EVT-FALL-{int(now_ts)}",
                            "time": datetime.now(IST).strftime("%H:%M:%S IST"),
                            "zone": self.zone_name,
                            "camera": self.camera_id,
                            "type": "MAN DOWN / FALL DETECTED",
                            "level": "CRITICAL",
                            "detail": f"Worker fall confirmed on {self.camera_id} ({self.zone_name}). Immediate assistance required.",
                            "acknowledged": False,
                        }
                        logger.warning(
                            f"WebSocket Fall Alert Fired from Device {self.device_id}: {fall_payload}"
                        )
                        alert_manager.broadcast_sync(fall_payload)

                # Feature 21 Fire & Smoke Detection: webcams are strictly excluded to prevent false positives
                if (counts.get("fire_detected") or counts.get("smoke_detected")) and not self.is_webcam:
                    now_ts = time.time()
                    cooldown_elapsed = (
                        (now_ts - self.last_fire_alert_time) >= self.fire_alert_cooldown
                        and (now_ts - self.tracker.last_fire_alert_time) >= self.fire_alert_cooldown
                    )
                    if cooldown_elapsed:
                        self.last_fire_alert_time = now_ts
                        self.tracker.last_fire_alert_time = now_ts
                        fire_payload = {
                            "id": f"EVT-HAZARD-{int(now_ts)}",
                            "time": datetime.now(IST).strftime("%H:%M:%S IST"),
                            "zone": self.zone_name,
                            "camera": self.camera_id,
                            "type": "CRITICAL HAZARD: FIRE / SMOKE DETECTED",
                            "level": "CRITICAL",
                            "detail": f"Hazard identified on {self.camera_id} ({self.zone_name}). Immediate evacuation required.",
                            "acknowledged": False,
                        }
                        logger.warning(
                            f"WebSocket Hazard Alert Fired from Device {self.device_id}: {fire_payload}"
                        )
                        alert_manager.broadcast_sync(fire_payload)
                    else:
                        self.last_fire_alert_time = max(self.last_fire_alert_time, self.tracker.last_fire_alert_time)

                _, encoded = cv2.imencode(
                    ".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                )
                jpeg_bytes = encoded.tobytes()
                with self.frame_lock:
                    self.current_jpeg = jpeg_bytes
                    self.raw_jpeg = raw_bytes
                time.sleep(0.033)  # ~30 FPS
            else:
                alert_manager.pause_stream_dispatch(self.camera_id)
                self.current_fps = 0.0
                consecutive_errors += 1
                if consecutive_errors > 8:
                    logger.warning(
                        f"Device {self.device_id} repeated frame drop. Re-opening capture."
                    )
                    if self.cap is not None:
                        self.cap.release()
                        self.cap = None
                    self.is_live = False
                # Stream Health Guard: offline/dropped frame -> purge alerts & yield clean signal
                offline_frame, _ = self.tracker.process_frame(None, ret=False)
                _, encoded = cv2.imencode(
                    ".jpg", offline_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                )
                clean_raw = generate_clean_raw_offline_frame(
                    f"UATU // DEV-{self.device_id} RECONNECTING",
                    "CLEAN RAW VIDEO STREAM",
                )
                with self.frame_lock:
                    self.current_jpeg = encoded.tobytes()
                    self.raw_jpeg = clean_raw
                time.sleep(0.1)

    def start(self):
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(
                target=self._run, daemon=True, name=f"UATU-Worker-Dev{self.device_id}"
            )
            self.worker_thread.start()

    def get_latest_jpeg(self, raw: bool = False) -> bytes:
        with self.frame_lock:
            if raw and getattr(self, "raw_jpeg", None) is not None:
                return self.raw_jpeg
            return self.current_jpeg

    def stop(self):
        self.running = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            logger.info(f"Released capture handle for device {self.device_id}")


class MultiWebcamManager:
    """Thread-safe manager coordinating multiple concurrent camera devices."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MultiWebcamManager, cls).__new__(cls)
                cls._instance._workers = {}
                cls._instance._worker_lock = threading.Lock()
            return cls._instance

    def get_worker(self, device_id: int) -> CameraDeviceWorker:
        with self._worker_lock:
            if device_id not in self._workers:
                worker = CameraDeviceWorker(device_id)
                worker.start()
                self._workers[device_id] = worker
            return self._workers[device_id]

    def stop_all(self):
        with self._worker_lock:
            for dev_id, worker in self._workers.items():
                worker.stop()
            self._workers.clear()


multi_webcam_manager = MultiWebcamManager()


# Backwards compatibility alias
class WebcamManager:
    def get_latest_jpeg(self):
        return multi_webcam_manager.get_worker(0).get_latest_jpeg()

    def stop(self):
        multi_webcam_manager.stop_all()


webcam_manager = WebcamManager()


def get_webcam_manager() -> WebcamManager:
    return webcam_manager


# =============================================================================
# FASTAPI APPLICATION SETUP
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown management."""
    logger.info(
        f"Starting {settings.PROJECT_NAME} (UNIFIED ASSISTANT FOR THREAT & UNDERSTANDING) [{settings.STAGE}] in {settings.ENVIRONMENT} mode"
    )
    # Register running event loop for thread-safe alert broadcasts
    alert_manager.set_event_loop(asyncio.get_running_loop())

    # Warm up device 0 (laptop physical webcam) on startup
    multi_webcam_manager.get_worker(0)
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}")
    multi_webcam_manager.stop_all()
    multi_file_stream_manager.stop_all()


app = FastAPI(
    title="UATU AI Operations Platform",
    version="1.0.0-foundation",
    description="UNIFIED ASSISTANT FOR THREAT & UNDERSTANDING (AI) — Stage 1 Foundation.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Narrowly configured development CORS origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# Standardized Error Handlers
@app.exception_handler(StarletteHTTPException)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    status_code = getattr(exc, "status_code", 500)
    detail = getattr(exc, "detail", str(exc))
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": f"HTTP_{status_code}",
                "message": detail,
                "details": None,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = []
    for err in exc.errors():
        loc = " -> ".join([str(x) for x in err.get("loc", [])])
        errors.append({"field": loc, "message": err.get("msg")})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed",
                "details": errors,
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.error(f"Unhandled server exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred. Please contact the system administrator.",
                "details": None,
            }
        },
    )


# Root information endpoint
@app.get("/")
def get_root():
    return {
        "service": "UNIFIED ASSISTANT FOR THREAT & UNDERSTANDING (AI)",
        "acronym": "UATU",
        "stage": settings.STAGE,
        "status": "operational",
        "documentation": "/docs",
        "api_v1": settings.API_V1_STR,
    }


# =============================================================================
# REAL-TIME AI INCIDENT WEBSOCKET BRIDGE
# =============================================================================


@app.websocket("/ws/alerts")
async def websocket_alerts_endpoint(websocket: WebSocket):
    """
    Real-time WebSocket stream pushing spatial AI alerts directly
    to connected React dashboards (e.g., Abnormal Gathering, Occupancy).
    """
    await alert_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        alert_manager.disconnect(websocket)
    except Exception as e:
        logger.info(f"WebSocket client disconnected: {e}")
        alert_manager.disconnect(websocket)


# Mount API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)


# =============================================================================
# MULTI-CAMERA STREAMING & VIDEO INGESTION ENDPOINTS
# =============================================================================


class FileStreamWorker:
    """Thread-safe background reader for video files with dedicated frame buffer for smooth 25-30 FPS playback."""

    def __init__(
        self,
        file_path: Path,
        overlay_label: str = "FEED",
        camera_id: str = "CAM-03",
        zone: str = "Zone 03 // Logistics Yard North",
    ):
        self.file_path = file_path
        self.overlay_label = overlay_label
        self.camera_id = camera_id
        self.zone = zone
        self.running = False
        self.current_jpeg: bytes = generate_offline_frame(
            f"UATU // {self.camera_id} INITIALIZING", "BUFFERING VIDEO FRAMES..."
        )
        self.raw_jpeg: bytes = generate_clean_raw_offline_frame(
            f"UATU // {self.camera_id} STANDBY", "CLEAN RAW VIDEO STREAM"
        )
        self.frame_lock = threading.Lock()
        self.worker_thread: Optional[threading.Thread] = None
        self.fps = 25.0
        self.tracker = SpatialTracker(
            camera_id=camera_id,
            zone=zone,
            is_webcam=False,
            enable_fire_detection=True,
        )
        self.last_fall_alert_time = 0.0
        self.fall_alert_cooldown = 15.0
        self.last_fire_alert_time = 0.0
        self.fire_alert_cooldown = 15.0
        self.current_fps = 0.0
        self.active_clients = 0

    def add_client(self):
        with self.frame_lock:
            self.active_clients += 1

    def remove_client(self):
        with self.frame_lock:
            self.active_clients = max(0, self.active_clients - 1)

    def _run(self):
        while self.running:
            # 1. Unassigned / Standby Guard: If no active clients, halt background execution
            if self.active_clients <= 0:
                self.current_fps = 0.0
                alert_manager.pause_stream_dispatch(self.camera_id)
                self.tracker.is_stream_active = False
                time.sleep(0.5)
                continue

            if not self.file_path.exists():
                # 2. Offline Guard: Missing file -> halt inference, suppress alerts, return clean offline frame
                self.current_fps = 0.0
                alert_manager.pause_stream_dispatch(self.camera_id)
                self.tracker.is_stream_active = False
                offline_frame, _ = self.tracker.process_frame(None, ret=False)
                _, encoded = cv2.imencode(
                    ".jpg", offline_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                )
                with self.frame_lock:
                    self.current_jpeg = encoded.tobytes()
                time.sleep(1.0)
                continue

            cap = cv2.VideoCapture(str(self.file_path))
            if not cap.isOpened():
                self.current_fps = 0.0
                alert_manager.pause_stream_dispatch(self.camera_id)
                self.tracker.is_stream_active = False
                offline_frame, _ = self.tracker.process_frame(None, ret=False)
                _, encoded = cv2.imencode(
                    ".jpg", offline_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                )
                with self.frame_lock:
                    self.current_jpeg = encoded.tobytes()
                time.sleep(1.0)
                continue

            raw_fps = cap.get(cv2.CAP_PROP_FPS)
            self.fps = raw_fps if raw_fps and 5.0 <= raw_fps <= 60.0 else 25.0
            frame_delay = 1.0 / self.fps

            try:
                while self.running:
                    # Unassigned / Disconnected client guard inside loop
                    if self.active_clients <= 0:
                        self.current_fps = 0.0
                        alert_manager.pause_stream_dispatch(self.camera_id)
                        self.tracker.is_stream_active = False
                        time.sleep(0.5)
                        break

                    t_start = time.perf_counter()
                    ret, frame = cap.read()
                    if not ret or frame is None or frame.size == 0:
                        # Seamless continuous loop
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()
                        if not ret or frame is None or frame.size == 0:
                            # Stream Health Guard: End/Failure -> suppress alerts & return clean offline signal
                            self.current_fps = 0.0
                            alert_manager.pause_stream_dispatch(self.camera_id)
                            self.tracker.is_stream_active = False
                            offline_frame, _ = self.tracker.process_frame(None, ret=False)
                            _, encoded = cv2.imencode(
                                ".jpg", offline_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                            )
                            with self.frame_lock:
                                self.current_jpeg = encoded.tobytes()
                            time.sleep(0.5)
                            continue

                    # Stream is valid and active: resume alert dispatch permissions
                    alert_manager.resume_stream_dispatch(self.camera_id)

                    # Capture pristine un-annotated copy with memory isolation (no geometric overlays)
                    raw_frame = frame.copy()
                    _, raw_encoded = cv2.imencode(
                        ".jpg", raw_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                    )
                    raw_bytes = raw_encoded.tobytes()

                    # Run AI Inference (ByteTrack, Tripwire, Fall Detection & Fire Detection) with Stream Health Guard
                    counts = {
                        "persons": 0,
                        "vehicles": 0,
                        "entry": 0,
                        "exit": 0,
                        "fall_detected": False,
                        "fire_detected": False,
                        "smoke_detected": False,
                        "stream_healthy": True,
                        "fps": 0,
                    }
                    try:
                        frame, counts = self.tracker.process_frame(frame, ret=ret)
                    except Exception as e:
                        logger.debug(f"AI inference error in worker: {e}")

                    self.current_fps = counts.get("fps", self.fps)

                    # If stream health check returned unhealthy, skip alert dispatch
                    if not counts.get("stream_healthy", False):
                        self.current_fps = 0.0
                        alert_manager.pause_stream_dispatch(self.camera_id)
                        _, encoded = cv2.imencode(
                            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                        )
                        with self.frame_lock:
                            self.current_jpeg = encoded.tobytes()
                            self.raw_jpeg = raw_bytes
                        time.sleep(0.05)
                        continue

                    # Strict Alert Circuit Breaker: Only streams with an active, valid video source frame can trigger hazard alerts
                    is_active = (
                        alert_manager.is_stream_active(self.camera_id)
                        and self.tracker.is_stream_active
                        and counts.get("stream_healthy", False)
                    )
                    if not is_active:
                        continue

                    # Fall Detection Alert with 15s cooldown
                    if counts.get("fall_detected"):
                        now_ts = time.time()
                        if (now_ts - self.last_fall_alert_time) >= self.fall_alert_cooldown:
                            self.last_fall_alert_time = now_ts
                            fall_payload = {
                                "id": f"EVT-FALL-{int(now_ts)}",
                                "time": datetime.now(IST).strftime("%H:%M:%S IST"),
                                "zone": self.zone,
                                "camera": self.camera_id,
                                "type": "MAN DOWN / FALL DETECTED",
                                "level": "CRITICAL",
                                "detail": f"Worker fall confirmed on {self.camera_id} ({self.zone}). Immediate assistance required.",
                                "acknowledged": False,
                            }
                            logger.warning(
                                f"WebSocket Fall Alert Fired from File Stream [{self.camera_id}]: {fall_payload}"
                            )
                            alert_manager.broadcast_sync(fall_payload)

                    # Fire & Smoke Detection Alert with 15s cooldown
                    if counts.get("fire_detected") or counts.get("smoke_detected"):
                        now_ts = time.time()
                        cooldown_elapsed = (
                            (now_ts - self.last_fire_alert_time) >= self.fire_alert_cooldown
                            and (now_ts - self.tracker.last_fire_alert_time) >= self.fire_alert_cooldown
                        )
                        if cooldown_elapsed:
                            self.last_fire_alert_time = now_ts
                            self.tracker.last_fire_alert_time = now_ts
                            fire_payload = {
                                "id": f"EVT-HAZARD-{int(now_ts)}",
                                "time": datetime.now(IST).strftime("%H:%M:%S IST"),
                                "zone": self.zone,
                                "camera": self.camera_id,
                                "type": "CRITICAL HAZARD: FIRE / SMOKE DETECTED",
                                "level": "CRITICAL",
                                "detail": f"Hazard identified on {self.camera_id} ({self.zone}). Immediate evacuation required.",
                                "acknowledged": False,
                            }
                            logger.warning(
                                f"WebSocket Hazard Alert Fired from File Stream [{self.camera_id}]: {fire_payload}"
                            )
                            alert_manager.broadcast_sync(fire_payload)
                        else:
                            self.last_fire_alert_time = max(self.last_fire_alert_time, self.tracker.last_fire_alert_time)

                    # Encode clean annotated frame directly
                    _, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                    jpeg_bytes = encoded.tobytes()
                    with self.frame_lock:
                        self.current_jpeg = jpeg_bytes
                        self.raw_jpeg = raw_bytes

                    t_proc = time.perf_counter() - t_start
                    sleep_dur = max(0.005, frame_delay - t_proc)
                    time.sleep(sleep_dur)
            finally:
                cap.release()

    def start(self):
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(
                target=self._run,
                daemon=True,
                name=f"UATU-FileWorker-{self.camera_id}",
            )
            self.worker_thread.start()

    def get_latest_jpeg(self, raw: bool = False) -> bytes:
        with self.frame_lock:
            if raw and getattr(self, "raw_jpeg", None) is not None:
                return self.raw_jpeg
            return self.current_jpeg

    def stop(self):
        self.running = False
        alert_manager.pause_stream_dispatch(self.camera_id)


class MultiFileStreamManager:
    """Thread-safe manager coordinating concurrent video file stream workers."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MultiFileStreamManager, cls).__new__(cls)
                cls._instance._workers = {}
                cls._instance._worker_lock = threading.Lock()
            return cls._instance

    def get_worker(
        self,
        file_path: Path,
        overlay_label: str = "FEED",
        camera_id: str = "CAM-03",
        zone: str = "Zone 03 // Logistics Yard North",
    ) -> FileStreamWorker:
        key = f"{camera_id}:{file_path.resolve()}"
        with self._worker_lock:
            # Circuit Breaker: Stop any prior worker running for the same camera_id with a different file
            for k, w in list(self._workers.items()):
                if w.camera_id == camera_id and k != key:
                    logger.info(f"Circuit Breaker: Stopping previous worker for {camera_id}: {w.file_path}")
                    w.stop()
                    del self._workers[k]

            if key not in self._workers or not self._workers[key].running:
                worker = FileStreamWorker(file_path, overlay_label, camera_id, zone)
                worker.start()
                self._workers[key] = worker
            return self._workers[key]

    def stop_camera(self, camera_id: str):
        """Stops all active file stream workers associated with the specified camera ID."""
        with self._worker_lock:
            for k, w in list(self._workers.items()):
                if w.camera_id == camera_id:
                    logger.info(f"Circuit Breaker: Stopping worker for {camera_id}")
                    w.stop()
                    del self._workers[k]
            alert_manager.pause_stream_dispatch(camera_id)

    def stop_all(self):
        with self._worker_lock:
            for _, worker in self._workers.items():
                worker.stop()
            self._workers.clear()


multi_file_stream_manager = MultiFileStreamManager()


async def generate_file_stream(
    file_path: Path,
    overlay_label: str = "FEED",
    camera_id: str = "CAM-03",
    zone: str = "Zone 03 // Logistics Yard North",
    raw: bool = False,
):
    """Streams from a threaded video file reader buffer at full frame rate without blocking."""
    worker = multi_file_stream_manager.get_worker(
        file_path=file_path,
        overlay_label=overlay_label,
        camera_id=camera_id,
        zone=zone,
    )
    worker.add_client()
    frame_interval = 1.0 / max(10.0, worker.fps)
    try:
        while True:
            frame_bytes = worker.get_latest_jpeg(raw=raw)
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
            await asyncio.sleep(frame_interval)
    except (asyncio.CancelledError, GeneratorExit):
        pass
    finally:
        worker.remove_client()


async def generate_parameterized_webcam_stream(device_id: int, raw: bool = False):
    """Yields frames from the designated device worker at ~25-30 FPS."""
    worker = multi_webcam_manager.get_worker(device_id)
    try:
        while True:
            frame_bytes = worker.get_latest_jpeg(raw=raw)
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
            await asyncio.sleep(0.035)
    except (asyncio.CancelledError, GeneratorExit):
        pass


@app.get("/api/video-stream")
def get_video_stream(raw: bool = False):
    """Camera 3 / Loop stream: loops test_video.mp4 continuously."""
    video_path = get_test_video_path()
    return StreamingResponse(
        generate_file_stream(
            video_path,
            overlay_label="UATU CAM-03 [TEST LOOP]",
            camera_id="CAM-03",
            zone="Zone 03 // Logistics Yard North",
            raw=raw,
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/webcam-stream/{device_id}")
def get_webcam_stream_by_device(device_id: int, raw: bool = False):
    """Streams from specified hardware camera device index (e.g. 0 for Iriun, 1 for laptop webcam, 2 for HD)."""
    return StreamingResponse(
        generate_parameterized_webcam_stream(device_id, raw=raw),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/webcam-stream")
def get_webcam_stream(device_id: int = 0, raw: bool = False):
    """Default webcam stream (defaults to device_id=0 to prioritize physical laptop camera)."""
    return StreamingResponse(
        generate_parameterized_webcam_stream(device_id, raw=raw),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/raw-webcam-stream/{device_id}")
def get_raw_webcam_stream_by_device(device_id: int):
    """Dedicated endpoint returning raw clean camera feed without overlays for enrollment viewfinder."""
    return StreamingResponse(
        generate_parameterized_webcam_stream(device_id, raw=True),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/camera-telemetry")
def get_camera_telemetry():
    """
    Returns real-time processing FPS, health status, line-crossing counters, and metadata for all cameras.
    Guarantees 0 FPS for offline or unassigned streams, and real-time FPS/counts for active streams.
    """
    telemetry = {
        f"CAM-0{i}": {
            "camera_id": f"CAM-0{i}",
            "is_online": False,
            "fps": 0,
            "status": "STREAM OFFLINE",
            "entry": 0,
            "exit": 0,
            "occupancy": 0,
        }
        for i in range(1, 10)
    }

    # 1. Device workers (Webcams / hardware devices)
    with multi_webcam_manager._worker_lock:
        for dev_id, worker in multi_webcam_manager._workers.items():
            cam_id = f"CAM-0{dev_id + 1}"
            is_active = worker.is_live and alert_manager.is_stream_active(cam_id)
            fps = float(getattr(worker, "current_fps", 0.0)) if is_active else 0.0
            entry = int(getattr(worker.tracker, "down_count", 0)) if (is_active and hasattr(worker, "tracker")) else 0
            exit = int(getattr(worker.tracker, "up_count", 0)) if (is_active and hasattr(worker, "tracker")) else 0
            occupancy = int(getattr(worker.tracker, "occupancy_count", 0)) if (is_active and hasattr(worker, "tracker")) else 0
            telemetry[cam_id] = {
                "camera_id": cam_id,
                "is_online": is_active,
                "fps": round(fps, 1) if is_active else 0,
                "status": "LIVE" if is_active else "STREAM OFFLINE",
                "device_id": dev_id,
                "entry": entry,
                "exit": exit,
                "occupancy": occupancy,
            }

    # 2. File stream workers (Custom uploads / video loops)
    with multi_file_stream_manager._worker_lock:
        for key, worker in multi_file_stream_manager._workers.items():
            cam_id = worker.camera_id
            is_active = worker.running and alert_manager.is_stream_active(cam_id)
            fps = float(getattr(worker, "current_fps", 0.0)) if is_active else 0.0
            entry = int(getattr(worker.tracker, "down_count", 0)) if (is_active and hasattr(worker, "tracker")) else 0
            exit = int(getattr(worker.tracker, "up_count", 0)) if (is_active and hasattr(worker, "tracker")) else 0
            occupancy = int(getattr(worker.tracker, "occupancy_count", 0)) if (is_active and hasattr(worker, "tracker")) else 0
            telemetry[cam_id] = {
                "camera_id": cam_id,
                "is_online": is_active,
                "fps": round(fps, 1) if is_active else 0,
                "status": "LIVE" if is_active else "STREAM OFFLINE",
                "zone": worker.zone,
                "entry": entry,
                "exit": exit,
                "occupancy": occupancy,
            }

    return telemetry


@app.post("/api/camera/{camera_id}/stop")
def stop_camera_stream(camera_id: str):
    """
    Halts all background workers and pauses alert dispatch for the designated camera ID.
    Used when a camera node is set to Unassigned/Standby.
    """
    multi_file_stream_manager.stop_camera(camera_id)
    alert_manager.pause_stream_dispatch(camera_id)
    return {"status": "STOPPED", "camera_id": camera_id}


@app.post("/api/upload-video")
async def upload_video(file: UploadFile = File(...)):
    """Uploads a local .mp4 file to backend/uploads/ and returns stream assignment parameters."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in upload request",
        )

    video_id = str(uuid.uuid4())[:8]
    clean_name = "".join(c for c in file.filename if c.isalnum() or c in "._-").strip()
    saved_filename = f"{video_id}_{clean_name}"
    target_path = UPLOADS_DIR / saved_filename

    try:
        content = await file.read()
        with open(target_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to save uploaded video {file.filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store video file: {str(e)}",
        )

    logger.info(f"Video uploaded successfully: {saved_filename} (ID: {video_id})")

    return {
        "video_id": video_id,
        "filename": file.filename,
        "stream_url": f"/api/custom-stream/{video_id}",
        "full_url": f"http://127.0.0.1:8000/api/custom-stream/{video_id}",
        "size_bytes": len(content),
        "status": "success",
    }


@app.get("/api/custom-stream/{video_id}")
def get_custom_stream(
    video_id: str,
    camera: Optional[str] = None,
    zone: Optional[str] = None,
):
    """Streams an uploaded custom video file matching the video_id."""
    matched_files = list(UPLOADS_DIR.glob(f"{video_id}_*"))
    if not matched_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video stream ID '{video_id}' not found in uploads directory",
        )

    target_video = matched_files[0]

    cam_to_zone = {
        "CAM-01": "Zone 01 // Main Turnstile North",
        "CAM-02": "Zone 01 // Optical Turnstile B",
        "CAM-03": "Zone 03 // Logistics Yard North",
        "CAM-04": "Zone 02 // Precision Machining Line",
        "CAM-05": "Zone 04 // Tier-3 Data Center Vault",
        "CAM-06": "Zone 06 // Western Security Barrier",
        "CAM-07": "Zone 05 // Cleanroom Corridor",
        "CAM-08": "Zone 07 // Executive Wing",
        "CAM-09": "Zone 08 // South Perimeter Gate",
    }

    if not camera:
        fname = target_video.name.lower()
        if "momentfatal" in fname or "batteryplant" in fname:
            camera = "CAM-05"
            zone = "Zone 04 // Tier-3 Data Center Vault"
        elif "cctvpeople" in fname or "aluminumfactory" in fname or "holysmokes" in fname:
            camera = "CAM-06"
            zone = "Zone 06 // Western Security Barrier"
        else:
            camera = "CAM-04"
            zone = "Zone 02 // Precision Machining Line"
    elif not zone:
        zone = cam_to_zone.get(camera, "Zone 04 // Tier-3 Data Center Vault")

    return StreamingResponse(
        generate_file_stream(
            target_video,
            overlay_label=f"UATU CUSTOM STREAM [{camera}]",
            camera_id=camera,
            zone=zone,
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/detect-face/{device_id}")
@app.get("/api/detect-face")
def detect_face_alignment(device_id: int = 0):
    """
    Evaluates current live frame from specified camera device index.
    Detects face presence, size, and geometry relative to the central circular alignment guide.
    Returns alignment status (aligned: bool), bounding box, confidence, and positioning advice.
    """
    try:
        worker = multi_webcam_manager.get_worker(device_id)
        jpeg_bytes = worker.get_latest_jpeg(raw=True)
        if not jpeg_bytes:
            return {
                "detected": False,
                "aligned": False,
                "confidence": 0.0,
                "message": "Connecting to camera feed...",
                "box": None,
                "center": None,
            }

        nparr = np.frombuffer(jpeg_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None or frame.size == 0:
            return {
                "detected": False,
                "aligned": False,
                "confidence": 0.0,
                "message": "Camera stream standby",
                "box": None,
                "center": None,
            }

        h, w = frame.shape[:2]
        guide_cx = w * 0.50
        guide_cy = h * 0.48
        guide_rx = w * 0.22
        guide_ry = h * 0.32

        faces = []
        if face_analysis_app is not None:
            try:
                faces = face_analysis_app.get(frame)
            except Exception as e:
                logger.debug(f"InsightFace detection error: {e}")

        # Fallback to OpenCV Haar cascade if InsightFace didn't return faces
        if not faces:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                cascade = cv2.CascadeClassifier(cascade_path)
                rects = cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=4, minSize=(int(w * 0.10), int(h * 0.12))
                )
                for (rx, ry, rw, rh) in rects:
                    class DummyFace:
                        pass
                    df = DummyFace()
                    df.bbox = np.array([rx, ry, rx + rw, ry + rh], dtype=float)
                    df.det_score = 0.85
                    faces.append(df)
            except Exception as e:
                logger.debug(f"Haar fallback error: {e}")

        if not faces:
            return {
                "detected": False,
                "aligned": False,
                "confidence": 0.0,
                "message": "Position face inside the target circle",
                "box": None,
                "center": None,
            }

        # Select most prominent face
        best_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        fx1, fy1, fx2, fy2 = [float(v) for v in best_face.bbox]
        det_score = float(getattr(best_face, "det_score", 1.0))
        face_w = fx2 - fx1
        face_h = fy2 - fy1
        face_cx = (fx1 + fx2) / 2.0
        face_cy = (fy1 + fy2) / 2.0

        min_w = w * 0.10
        max_w = w * 0.65
        min_h = h * 0.12
        max_h = h * 0.75
        is_size_ok = (min_w <= face_w <= max_w) and (min_h <= face_h <= max_h)

        # Elliptical normalized distance to guide center
        norm_dist = ((face_cx - guide_cx) / guide_rx) ** 2 + ((face_cy - guide_cy) / guide_ry) ** 2
        is_centered = norm_dist <= 1.05

        if is_size_ok and is_centered and det_score >= 0.40:
            aligned = True
            message = "Face aligned. Ready for biometric enrollment."
        elif not is_centered:
            aligned = False
            message = "Center your face inside the target circle."
        elif face_w < min_w or face_h < min_h:
            aligned = False
            message = "Move closer to the camera."
        elif face_w > max_w or face_h > max_h:
            aligned = False
            message = "Step back slightly from the camera."
        else:
            aligned = False
            message = "Position face inside the target area."

        return {
            "detected": True,
            "aligned": aligned,
            "confidence": round(det_score, 2),
            "box": [round(fx1), round(fy1), round(fx2), round(fy2)],
            "center": [round(face_cx), round(face_cy)],
            "message": message,
        }
    except Exception as exc:
        logger.debug(f"Face alignment endpoint error: {exc}")
        return {
            "detected": False,
            "aligned": False,
            "confidence": 0.0,
            "message": "Analyzing optical frame...",
            "box": None,
            "center": None,
        }


class EnrollRequest(BaseModel):
    device_id: int = Field(default=0, description="Camera device index (e.g. 0 for Laptop Webcam, 1 for Mobile/Iriun Webcam)")
    employee_id: str = Field(..., description="Unique employee badge identifier (e.g. EMP-1001)")
    name: str = Field(..., description="Full personnel name")
    roll: str = Field(..., description="Roll number or departmental ID")


def extract_face_biometrics(frame: np.ndarray) -> Tuple[Optional[np.ndarray], Optional[Any], int]:
    """
    Unified Canonical Biometric Feature Extraction Pipeline:
    Used identically across both enrollment (/api/enroll) and live verification (/api/verify-access).
    1. Runs InsightFace buffalo_l FaceAnalysis (detection + 5-point landmark alignment + ArcFace recognition).
    2. Identifies primary (largest) face by bounding box area.
    3. Normalizes 512-d feature vector: unit_norm = raw_emb / ||raw_emb||.
    Returns:
        (normalized_512d_embedding, best_face_object, face_count)
    """
    if frame is None or frame.size == 0 or face_analysis_app is None:
        return None, None, 0

    try:
        faces = face_analysis_app.get(frame)
    except Exception as e:
        logger.error(f"InsightFace FaceAnalysis extraction error: {e}")
        return None, None, 0

    if not faces:
        return None, None, 0

    # Select primary (largest) face by bounding box area
    best_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    raw_emb = getattr(best_face, "embedding", None)
    if raw_emb is None:
        return None, best_face, len(faces)

    vec = np.asarray(raw_emb, dtype=np.float32).flatten()
    norm = float(np.linalg.norm(vec))
    if norm > 0.0:
        unit_emb = (vec / norm).astype(np.float32)
    else:
        unit_emb = vec.astype(np.float32)

    return unit_emb, best_face, len(faces)


@app.post("/api/enroll")
async def enroll_personnel(payload: EnrollRequest):
    """
    Captures the live camera frame, extracts the 512-d facial embedding via InsightFace buffalo_l,
    and appends the new record non-destructively to backend/mock_employee_db.pkl.
    """
    employee_id = payload.employee_id.strip()
    name = payload.name.strip()
    roll = payload.roll.strip()

    if not employee_id or not name or not roll:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fields 'employee_id', 'name', and 'roll' are required.",
        )

    # 1. Grab current live clean un-annotated frame from requested device worker
    worker = multi_webcam_manager.get_worker(payload.device_id)
    jpeg_bytes = worker.get_latest_jpeg(raw=True)
    if not jpeg_bytes:
        jpeg_bytes = worker.get_latest_jpeg()

    if not jpeg_bytes:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Camera Device {payload.device_id} buffer unavailable.",
        )

    # 2. Decode JPEG to OpenCV image array
    nparr = np.frombuffer(jpeg_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decode live camera frame for biometric extraction.",
        )

    # 3. Process frame through unified feature extraction & normalization pipeline
    if face_analysis_app is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="InsightFace biometric model is not initialized on the server.",
        )

    normalized_embedding, best_face, face_count = extract_face_biometrics(frame)

    # If no face detected on primary device, check alternate devices (e.g. device 1)
    if normalized_embedding is None or face_count == 0:
        for alt_dev in [1, 0, 2]:
            if alt_dev != payload.device_id:
                try:
                    alt_worker = multi_webcam_manager.get_worker(alt_dev)
                    alt_bytes = alt_worker.get_latest_jpeg(raw=True) or alt_worker.get_latest_jpeg()
                    if alt_bytes:
                        alt_frame = cv2.imdecode(np.frombuffer(alt_bytes, np.uint8), cv2.IMREAD_COLOR)
                        if alt_frame is not None and alt_frame.size > 0:
                            alt_emb, alt_best, alt_cnt = extract_face_biometrics(alt_frame)
                            if alt_cnt > 0 and alt_emb is not None:
                                normalized_embedding = alt_emb
                                best_face = alt_best
                                face_count = alt_cnt
                                break
                except Exception as ex:
                    logger.debug(f"Alternate camera enrollment probe error: {ex}")

    if normalized_embedding is None or face_count == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "No face detected in frame"},
        )

    # 4. Persist to mock_employee_db.pkl and sync in-memory BiometricRegistry
    biometric_registry.db_path = MOCK_DB_PATH
    enroll_res = biometric_registry.enroll(
        employee_id=employee_id,
        name=name,
        roll=roll,
        embedding=normalized_embedding,
    )

    face_confidence = float(getattr(best_face, "det_score", 0.95))
    logger.info(f"Enrolled {name} ({roll}) under {employee_id} via Device {payload.device_id}")

    return {
        "status": "success",
        "message": f"Successfully enrolled {name} ({roll}) under {employee_id}.",
        "employee_id": employee_id,
        "name": name,
        "roll": roll,
        "confidence": round(face_confidence * 100, 1),
        "total_enrolled": enroll_res["total_enrolled"],
    }



@app.get("/api/enrolled-users")
def get_enrolled_users():
    """Lists all enrolled personnel in mock_employee_db.pkl (omits raw vectors)."""
    biometric_registry.db_path = MOCK_DB_PATH
    users = biometric_registry.list_enrolled()
    return {"users": users, "count": len(users)}


class VerifyAccessRequest(BaseModel):
    device_id: int = Field(default=0, description="Camera device index to look through (e.g. 0 for Laptop Webcam, 1 for Mobile/Iriun Webcam)")
    employee_id: str = Field(..., description="Scanned badge employee ID (e.g. EMP-1001)")


@app.post("/api/verify-access")
async def verify_access(payload: VerifyAccessRequest):
    """
    Live AI Biometric Verification & 1:N Recognition Retrieval Loop:
    1. Loads/verifies against in-memory BiometricRegistry (backed by mock_employee_db.pkl).
    2. Grabs the clean live camera frame from multi_webcam_manager.get_worker(device_id).get_latest_jpeg(raw=True).
    3. AI Step 1 (YOLO): Runs yolo_model(frame) to count person detections (class == 0).
    4. AI Step 2 (InsightFace ArcFace): Runs face_analysis_app.get(frame) to extract 512-d live facial embedding.
    5. Vector Matching: Computes normalized cosine similarity against registered profiles via BiometricRegistry.
    6. Verdict Logic:
       - If person count > 1: status = 'TAILGATING'
       - Else if face match >= 0.45: status = 'AUTHORIZED'
       - Else: status = 'MISMATCH'
    7. Dispatches real-time identification event to alert_manager.broadcast_sync.
    """
    employee_id = payload.employee_id.strip()
    if not employee_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Employee ID is required"},
        )

    biometric_registry.db_path = MOCK_DB_PATH
    biometric_registry._ensure_fresh()

    # If database file does not exist at all, return 404
    if not biometric_registry.db_path.exists():
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Employee database not found. Please enroll personnel first."},
        )

    is_auto_mode = employee_id.upper() in ["AUTO", "DETECT", "SCAN", "ALL"]

    # Check if explicit employee was requested and exists
    target_rec = None
    if not is_auto_mode:
        target_rec = biometric_registry.get_employee(employee_id)
        if target_rec is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"error": f"Employee ID '{employee_id}' not found in database"},
            )

    # 2. Grab live clean un-annotated frame from camera worker
    worker = multi_webcam_manager.get_worker(payload.device_id)
    jpeg_bytes = worker.get_latest_jpeg(raw=True)
    if not jpeg_bytes:
        jpeg_bytes = worker.get_latest_jpeg()
    if not jpeg_bytes:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": f"Camera Device {payload.device_id} buffer unavailable."},
        )

    nparr = np.frombuffer(jpeg_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "Failed to decode live camera frame"},
        )

    # 3. AI Step 1 (YOLOv8): Person detection / occupancy
    person_count = 0
    if yolo_model is not None:
        try:
            results = yolo_model(frame, verbose=False)
            for r in results:
                if r.boxes is not None:
                    for box in r.boxes:
                        cls_id = int(box.cls[0].item())
                        if cls_id == 0:  # COCO class 0: person
                            person_count += 1
        except Exception as e:
            logger.warning(f"YOLO inference error: {e}")
            person_count = 1
    else:
        person_count = 1

    # 4. AI Step 2 (InsightFace ArcFace): Face embedding extraction & Cosine Similarity
    similarity = 0.0
    faces_detected = 0
    db_name = target_rec.get("name", "Unknown") if target_rec else "Unrecognized"
    db_roll = target_rec.get("roll", "") if target_rec else ""
    matched_id = target_rec.get("employee_id", employee_id) if target_rec else employee_id
    is_authorized = False
    detail_msg = ""

    active_device_id = payload.device_id
    normalized_embedding, best_face, faces_detected = extract_face_biometrics(frame)

    # If no face detected on primary device, check alternate active devices (e.g. Device 1 if user is at laptop)
    if faces_detected == 0 or normalized_embedding is None:
        for alt_dev in [1, 0, 2]:
            if alt_dev != payload.device_id:
                try:
                    alt_worker = multi_webcam_manager.get_worker(alt_dev)
                    alt_bytes = alt_worker.get_latest_jpeg(raw=True) or alt_worker.get_latest_jpeg()
                    if alt_bytes:
                        alt_frame = cv2.imdecode(np.frombuffer(alt_bytes, np.uint8), cv2.IMREAD_COLOR)
                        if alt_frame is not None and alt_frame.size > 0:
                            alt_emb, alt_best, alt_cnt = extract_face_biometrics(alt_frame)
                            if alt_cnt > 0 and alt_emb is not None:
                                frame = alt_frame
                                normalized_embedding = alt_emb
                                best_face = alt_best
                                faces_detected = alt_cnt
                                active_device_id = alt_dev
                                logger.info(f"Auto-switched biometric verification to active feed Device {alt_dev}")
                                break
                except Exception as ex:
                    logger.debug(f"Alternate camera verification probe error: {ex}")

    if faces_detected > 0 and normalized_embedding is not None:
        # A visible face proves at least 1 person is present
        if person_count == 0:
            person_count = max(person_count, faces_detected)

        # Biometric retrieval against in-memory registry using exact normalized embedding
        retrieval_res = biometric_registry.verify_or_identify(
            live_embedding=normalized_embedding,
            employee_id=employee_id if not is_auto_mode else None,
            threshold=0.45,
        )

        similarity = retrieval_res["raw_score"]
        is_authorized = retrieval_res["is_authorized"]
        db_name = retrieval_res["employee_name"]
        db_roll = retrieval_res["roll"]
        matched_id = retrieval_res["employee_id"]
        detail_msg = retrieval_res["detail"]
    else:
        detail_msg = "No facial features acquired in frame. Position face inside camera view."


    # 5. Verdict Logic:
    # - If person count > 1: status = 'TAILGATING'
    # - Else if is_authorized (face similarity >= 0.45): status = 'AUTHORIZED'
    # - Else: status = 'MISMATCH'
    if person_count > 1:
        verdict_status = "TAILGATING"
    elif is_authorized and similarity >= 0.45:
        verdict_status = "AUTHORIZED"
    else:
        verdict_status = "MISMATCH"

    match_score_pct = round(similarity * 100, 1)

    # 6. Dispatch real-time WebSocket event for security logs & command center
    event_type = (
        "TAILGATING_VIOLATION" if verdict_status == "TAILGATING"
        else ("PERSONNEL_IDENTIFIED" if verdict_status == "AUTHORIZED" else "BIOMETRIC_MISMATCH")
    )
    event_severity = (
        "CRITICAL" if verdict_status == "TAILGATING"
        else ("INFO" if verdict_status == "AUTHORIZED" else "WARNING")
    )
    event_payload = {
        "id": f"EVT-AUTH-{uuid.uuid4().hex[:8].upper()}",
        "timestamp": datetime.now(IST).strftime("%H:%M:%S IST"),
        "zone": f"Zone 01 // Device {active_device_id}",
        "type": event_type,
        "severity": event_severity,
        "message": f"Biometric Access [{verdict_status}]: {db_name} ({matched_id}) - {match_score_pct}% ArcFace match",
        "camera_id": f"CAM-DEV-{active_device_id}",
        "metadata": {
            "status": verdict_status,
            "match_score": match_score_pct,
            "employee_id": matched_id,
            "employee_name": db_name,
            "person_count": person_count,
            "faces_detected": faces_detected,
        },
    }
    try:
        alert_manager.broadcast_sync(event_payload)
    except Exception as e:
        logger.debug(f"Alert broadcast notification: {e}")

    logger.info(
        f"Verified {matched_id} ({db_name}): status={verdict_status}, match_score={match_score_pct}%, person_count={person_count}"
    )

    return {
        "status": verdict_status,
        "match_score": match_score_pct,
        "raw_score": round(similarity, 4),
        "person_count": person_count,
        "faces_detected": faces_detected,
        "employee_name": db_name,
        "employee_id": matched_id,
        "roll": db_roll,
        "zone": f"Zone 01 // Device {active_device_id}",
        "detail": detail_msg,
        "timestamp": datetime.now(IST).strftime("%H:%M:%S IST"),
    }



