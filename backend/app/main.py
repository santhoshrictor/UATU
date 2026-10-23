import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))

from pathlib import Path
import pickle
import sys
import threading
import time
from typing import Any, AsyncGenerator, Dict, List, Optional
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


# =============================================================================
# SINGLETON THREADED WEBCAM MANAGER (DIRECTSHOW ON WINDOWS)
# =============================================================================


def get_working_camera(preferred_indices=(1, 2, 0)):
    """
    Attempts to initialize physical hardware cameras across multiple indices.
    Prioritizes index 1 and 2 to explicitly bypass virtual webcam drivers (e.g. Iriun, OBS) on index 0.
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
                        f"({test_frame.shape[1]}x{test_frame.shape[0]}). Bypassed virtual driver on index 0."
                    )
                    return cap, idx
                cap.release()
        except Exception as e:
            logger.warning(f"Could not initialize camera index {idx}: {e}")
    return None, None


class CameraDeviceWorker:
    """Thread-safe capture worker for a specific video hardware/virtual device index."""

    def __init__(self, device_id: int):
        self.device_id = device_id
        self.running = False
        self.cap = None
        self.current_jpeg: bytes = generate_offline_frame(
            f"UATU // DEV-{device_id} INITIALIZING",
            f"CONNECTING TO DIRECTSHOW DEVICE {device_id}...",
        )
        self.frame_lock = threading.Lock()
        self.worker_thread = None
        self.is_live = False
        self.tracker = SpatialTracker()
        self.last_crowd_alert_time = 0.0
        self.crowd_alert_cooldown = 15.0
        self.last_fall_alert_time = 0.0
        self.fall_alert_cooldown = 15.0

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
                self.cap = self._open_capture()
                if self.cap is None:
                    self.is_live = False
                    fallback = generate_offline_frame(
                        f"UATU // DEV-{self.device_id} OFFLINE",
                        f"DEVICE INDEX {self.device_id} UNAVAILABLE",
                    )
                    with self.frame_lock:
                        self.current_jpeg = fallback
                    time.sleep(1.0)
                    continue

            ret, frame = self.cap.read()
            if ret and frame is not None:
                consecutive_errors = 0
                self.is_live = True

                # Feature 1-4, 15-17 (ByteTrack, Tripwire, Occupancy HUD, Fall Detection)
                annotated_frame, counts = self.tracker.process_frame(frame)

                # Feature 15 WebSocket Alert Engine: dispatch when is_crowded with 15s cooldown
                if counts.get("is_crowded"):
                    now_ts = time.time()
                    if (now_ts - self.last_crowd_alert_time) >= self.crowd_alert_cooldown:
                        self.last_crowd_alert_time = now_ts
                        alert_payload = {
                            "id": f"EVT-CROWD-{int(now_ts)}",
                            "time": datetime.now(IST).strftime("%H:%M:%S IST"),
                            "zone": "Live Monitoring Zone",
                            "type": "ABNORMAL GATHERING",
                            "level": "CRITICAL",
                            "detail": "Occupancy threshold breached (> 3 persons).",
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
                            "zone": "Live Monitoring Zone",
                            "type": "MAN DOWN / FALL DETECTED",
                            "level": "CRITICAL",
                            "detail": "Worker fall detected based on skeletal pose geometry. Immediate assistance required.",
                            "acknowledged": False,
                        }
                        logger.warning(
                            f"WebSocket Fall Alert Fired from Device {self.device_id}: {fall_payload}"
                        )
                        alert_manager.broadcast_sync(fall_payload)

                _, encoded = cv2.imencode(
                    ".jpg", annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
                )
                jpeg_bytes = encoded.tobytes()
                with self.frame_lock:
                    self.current_jpeg = jpeg_bytes
                time.sleep(0.033)  # ~30 FPS
            else:
                consecutive_errors += 1
                if consecutive_errors > 8:
                    logger.warning(
                        f"Device {self.device_id} repeated frame drop. Re-opening capture."
                    )
                    if self.cap is not None:
                        self.cap.release()
                        self.cap = None
                    self.is_live = False
                fallback = generate_offline_frame(
                    f"UATU // DEV-{self.device_id} OFFLINE",
                    "FRAME ACQUISITION DROPPED",
                )
                with self.frame_lock:
                    self.current_jpeg = fallback
                time.sleep(0.1)

    def start(self):
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(
                target=self._run, daemon=True, name=f"UATU-Worker-Dev{self.device_id}"
            )
            self.worker_thread.start()

    def get_latest_jpeg(self) -> bytes:
        with self.frame_lock:
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
        return multi_webcam_manager.get_worker(1).get_latest_jpeg()

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

    # Warm up device 1 (laptop webcam) on startup
    multi_webcam_manager.get_worker(1)
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}")
    multi_webcam_manager.stop_all()


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


async def generate_file_stream(file_path: Path, overlay_label: str = "FEED"):
    """Streams a video file on a continuous loop with clean resource teardown."""
    cap = None
    try:
        if not file_path.exists():
            offline_bytes = generate_offline_frame(
                "UATU // TEST VIDEO NOT FOUND", f"MISSING {file_path.name}"
            )
            while True:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + offline_bytes + b"\r\n"
                )
                await asyncio.sleep(0.5)

        cap = cv2.VideoCapture(str(file_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        delay = 1.0 / fps if fps and fps > 0 else 0.04
        tracker = SpatialTracker()
        last_fall_alert_time = 0.0
        fall_alert_cooldown = 15.0

        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                # Loop video to beginning
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = cap.read()
                if not ret or frame is None:
                    offline_bytes = generate_offline_frame(
                        "UATU // STREAM DELAY", "WAITING FOR FRAMES"
                    )
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + offline_bytes + b"\r\n"
                    )
                    await asyncio.sleep(0.5)
                    continue

            # 1. Run AI Inference (YOLO11 ByteTrack & Tripwire & Fall Detection)
            counts = {"persons": 0, "vehicles": 0, "entry": 0, "exit": 0, "fall_detected": False}
            try:
                frame, counts = tracker.process_frame(frame)
            except Exception:
                pass  # Fail silently and keep streaming if AI throws an error

            # Feature 17 Fall Detection: check fall_detected with 15s cooldown
            if counts.get("fall_detected"):
                now_ts = time.time()
                if (now_ts - last_fall_alert_time) >= fall_alert_cooldown:
                    last_fall_alert_time = now_ts
                    fall_payload = {
                        "id": f"EVT-FALL-{int(now_ts)}",
                        "time": datetime.now(IST).strftime("%H:%M:%S IST"),
                        "zone": "Live Monitoring Zone",
                        "type": "MAN DOWN / FALL DETECTED",
                        "level": "CRITICAL",
                        "detail": "Worker fall detected based on skeletal pose geometry. Immediate assistance required.",
                        "acknowledged": False,
                    }
                    logger.warning(
                        f"WebSocket Fall Alert Fired from File Stream: {fall_payload}"
                    )
                    alert_manager.broadcast_sync(fall_payload)

            # 2. Encode clean annotated frame directly
            _, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + encoded.tobytes() + b"\r\n"
            )
            await asyncio.sleep(delay)
    except (asyncio.CancelledError, GeneratorExit):
        pass
    finally:
        if cap is not None:
            cap.release()
            logger.info(f"Released video file resources for {file_path.name}")


async def generate_parameterized_webcam_stream(device_id: int):
    """Yields frames from the designated device worker at ~25-30 FPS."""
    worker = multi_webcam_manager.get_worker(device_id)
    try:
        while True:
            frame_bytes = worker.get_latest_jpeg()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
            await asyncio.sleep(0.035)
    except (asyncio.CancelledError, GeneratorExit):
        pass


@app.get("/api/video-stream")
def get_video_stream():
    """Camera 2 / Loop stream: loops test_video.mp4 continuously."""
    video_path = get_test_video_path()
    return StreamingResponse(
        generate_file_stream(video_path, overlay_label="UATU CAM-02 [TEST LOOP]"),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/webcam-stream/{device_id}")
def get_webcam_stream_by_device(device_id: int):
    """Streams from specified hardware camera device index (e.g. 0 for Iriun, 1 for laptop webcam, 2 for HD)."""
    return StreamingResponse(
        generate_parameterized_webcam_stream(device_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/webcam-stream")
def get_webcam_stream(device_id: int = 1):
    """Default webcam stream (defaults to device_id=1 to prioritize physical laptop camera)."""
    return StreamingResponse(
        generate_parameterized_webcam_stream(device_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


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
def get_custom_stream(video_id: str):
    """Streams an uploaded custom video file matching the video_id."""
    matched_files = list(UPLOADS_DIR.glob(f"{video_id}_*"))
    if not matched_files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video stream ID '{video_id}' not found in uploads directory",
        )

    target_video = matched_files[0]
    return StreamingResponse(
        generate_file_stream(
            target_video, overlay_label=f"UATU CUSTOM STREAM [{video_id}]"
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


class EnrollRequest(BaseModel):
    device_id: int = Field(default=1, description="Camera device index (e.g. 0 for Iriun Mobile, 1 for Laptop Webcam)")
    employee_id: str = Field(..., description="Unique employee badge identifier (e.g. EMP-1001)")
    name: str = Field(..., description="Full personnel name")
    roll: str = Field(..., description="Roll number or departmental ID")


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

    # 1. Grab current live frame from requested device worker
    worker = multi_webcam_manager.get_worker(payload.device_id)
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

    # 3. Process frame with InsightFace FaceAnalysis
    if face_analysis_app is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="InsightFace biometric model is not initialized on the server.",
        )

    try:
        faces = face_analysis_app.get(frame)
    except Exception as e:
        logger.error(f"Error executing face analysis on live frame: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Biometric extraction failed: {str(e)}",
        )

    if not faces:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "No face detected in frame"},
        )

    # 4. Extract normalized 512-d embedding from primary (largest) face
    best_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    raw_embedding = best_face.embedding  # 512-dimensional float32 vector
    norm = np.linalg.norm(raw_embedding)
    normalized_embedding = (raw_embedding / norm) if norm > 0 else raw_embedding

    # 5. Persist to backend/mock_employee_db.pkl (preserving previous enrollments)
    db_path = MOCK_DB_PATH
    db: Dict[str, Any] = {}
    if db_path.exists():
        try:
            with open(db_path, "rb") as f:
                loaded = pickle.load(f)
                if isinstance(loaded, dict):
                    db = loaded
        except Exception as e:
            logger.warning(f"Could not load existing employee db: {e}. Starting fresh.")

    db[employee_id] = {
        "name": name,
        "roll": roll,
        "embedding": normalized_embedding,
    }

    try:
        with open(db_path, "wb") as f:
            pickle.dump(db, f)
    except Exception as e:
        logger.error(f"Failed to persist employee database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write to employee database: {str(e)}",
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
        "total_enrolled": len(db),
    }


@app.get("/api/enrolled-users")
def get_enrolled_users():
    """Lists all enrolled personnel in mock_employee_db.pkl (omits raw vectors)."""
    db_path = MOCK_DB_PATH
    if not db_path.exists():
        return {"users": [], "count": 0}

    try:
        with open(db_path, "rb") as f:
            db = pickle.load(f)
            users = [
                {"employee_id": k, "name": v.get("name"), "roll": v.get("roll")}
                for k, v in db.items()
            ]
            return {"users": users, "count": len(users)}
    except Exception as e:
        return {"users": [], "count": 0, "error": str(e)}


class VerifyAccessRequest(BaseModel):
    device_id: int = Field(default=1, description="Camera device index to look through (e.g. 0 for Iriun, 1 for Laptop)")
    employee_id: str = Field(..., description="Scanned badge employee ID (e.g. EMP-1001)")


@app.post("/api/verify-access")
async def verify_access(payload: VerifyAccessRequest):
    """
    Live AI Verification loop:
    1. Loads mock_employee_db.pkl. If employee_id is missing, returns 404 Not Found.
    2. Grabs the live camera frame from multi_webcam_manager.get_worker(device_id).get_latest_jpeg().
    3. AI Step 1 (YOLO): Runs yolo_model(frame) to count detections with class == 0 (person).
    4. AI Step 2 (InsightFace): Runs face_analysis_app.get(frame). Computes Cosine Similarity against enrolled embedding.
    5. Verdict Logic:
       - If person count > 1: status = 'TAILGATING'
       - Else if face similarity >= 0.50: status = 'AUTHORIZED'
       - Else: status = 'MISMATCH'
    6. Returns {"status": status, "match_score": match_score_pct, "person_count": person_count, "employee_name": db_name, ...}
    """
    employee_id = payload.employee_id.strip()
    if not employee_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Employee ID is required"},
        )

    # 1. Load mock_employee_db.pkl
    db_path = MOCK_DB_PATH
    if not db_path.exists():
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Employee database not found. Please enroll personnel first."},
        )

    try:
        with open(db_path, "rb") as f:
            db = pickle.load(f)
    except Exception as e:
        logger.error(f"Failed to read employee db: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": f"Failed to read employee database: {str(e)}"},
        )

    if employee_id not in db:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": f"Employee ID '{employee_id}' not found in database"},
        )

    employee_record = db[employee_id]
    db_name = employee_record.get("name", "Unknown")
    db_roll = employee_record.get("roll", "")
    enrolled_emb = employee_record.get("embedding")

    # 2. Grab live frame from camera worker
    worker = multi_webcam_manager.get_worker(payload.device_id)
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

    # 4. AI Step 2 (InsightFace): Face embedding extraction & Cosine Similarity
    similarity = 0.0
    faces_detected = 0
    if face_analysis_app is not None:
        try:
            faces = face_analysis_app.get(frame)
            faces_detected = len(faces)
            if faces and enrolled_emb is not None:
                # Find largest face
                best_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
                live_emb = best_face.embedding
                live_norm = np.linalg.norm(live_emb)
                live_normed = (live_emb / live_norm) if live_norm > 0 else live_emb

                enrolled_norm = np.linalg.norm(enrolled_emb)
                enrolled_normed = (enrolled_emb / enrolled_norm) if enrolled_norm > 0 else enrolled_emb

                cos_sim = float(np.dot(live_normed, enrolled_normed))
                similarity = max(0.0, min(1.0, cos_sim))
        except Exception as e:
            logger.warning(f"InsightFace verification inference error: {e}")

    # 5. Verdict Logic:
    # - If person count > 1: status = 'TAILGATING'
    # - Else if face similarity >= 0.50: status = 'AUTHORIZED'
    # - Else: status = 'MISMATCH'
    if person_count > 1:
        verdict_status = "TAILGATING"
    elif similarity >= 0.50:
        verdict_status = "AUTHORIZED"
    else:
        verdict_status = "MISMATCH"

    match_score_pct = round(similarity * 100, 1)

    logger.info(
        f"Verified {employee_id} ({db_name}): status={verdict_status}, match_score={match_score_pct}%, person_count={person_count}"
    )

    return {
        "status": verdict_status,
        "match_score": match_score_pct,
        "raw_score": round(similarity, 4),
        "person_count": person_count,
        "faces_detected": faces_detected,
        "employee_name": db_name,
        "employee_id": employee_id,
        "roll": db_roll,
        "zone": f"Zone 01 // Device {payload.device_id}",
        "timestamp": datetime.now(IST).strftime("%H:%M:%S IST"),
    }


