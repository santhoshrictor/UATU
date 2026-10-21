import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import sys
import threading
import time
from typing import AsyncGenerator
import uuid

import cv2
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import numpy as np
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.api.v1.api import api_router
from backend.app.core.config import settings
from backend.app.core.logging import logger

# Base directory for uploads and video assets
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BACKEND_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

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
                now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
                label = f"UATU DEV-{self.device_id} [LIVE] {now_str}"
                cv2.putText(
                    frame,
                    label,
                    (16, 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (16, 185, 129),
                    2,
                )
                _, encoded = cv2.imencode(
                    ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75]
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

            # Overlay subtle telemetry header
            now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
            cv2.putText(
                frame,
                f"{overlay_label} // {now_str}",
                (16, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (16, 185, 129),
                2,
            )

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
