"""
UATU AI Access Control & Biometric Correlation Engine
=====================================================
Acts as the intelligence layer for the UATU Access Control & Biometric Correlation
UI panel, processing physical RFID badge scans alongside visual surveillance frames from OpenCV.

Capabilities:
1. GPU-Accelerated Model Initialization:
   - YOLOv8/11: Person detection (COCO class 0) and spatial bounding box extraction.
   - InsightFace / ArcFace: 512-dimensional facial embedding extraction and cosine matching.
   - Explicit CUDA configuration (`device='cuda:0'`, `CUDAExecutionProvider`) with CPU fallback.
2. Core Correlation Engine (`evaluate_entry_event`):
   - Multi-person occupancy analysis with instant TAILGATING breach escalation.
   - Biometric cosine similarity comparison against enrolled credential vectors.
   - Structured JSON-serializable telemetry payload with bounding coordinates.
3. Fallback / Simulation Mode:
   - Safe development fallback when physical weights (.pth/.onnx) or heavy ML libraries
     are not yet staged in `backend/models/`, preventing server crashes.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("workplace_intelligence.access_engine")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] workplace_intelligence (access_engine.py): %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Base models directory path
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"


class AccessCorrelationEngine:
    """
    Hardware-accelerated biometric verification and multi-person occupancy detector.
    Coordinates YOLO (spatial person detection) and ArcFace (facial vector extraction).
    """

    def __init__(self, models_dir: Optional[Path] = None):
        self.models_dir = models_dir or MODELS_DIR
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.cuda_available: bool = False
        self.pytorch_device: str = "cpu"
        self.onnx_providers: List[str] = ["CPUExecutionProvider"]
        self.device_info: str = "CPU"
        self.is_simulated: bool = False

        self.yolo_model: Any = None
        self.face_analyzer: Any = None

        self._detect_hardware_capabilities()
        self._initialize_models()

    def _detect_hardware_capabilities(self) -> None:
        """Detects NVIDIA CUDA availability across PyTorch and ONNX Runtime."""
        try:
            import torch

            if torch.cuda.is_available():
                self.cuda_available = True
                self.pytorch_device = "cuda:0"
                gpu_name = torch.cuda.get_device_name(0)
                self.device_info = f"CUDA (GPU: {gpu_name})"
                logger.info(f"CUDA hardware detected: {gpu_name}. Configured primary device: cuda:0")
            else:
                self.pytorch_device = "cpu"
                self.device_info = "CPU (CUDA unavailable)"
                logger.info("CUDA hardware not detected. PyTorch configured to CPU fallback.")
        except ImportError:
            self.pytorch_device = "cpu"
            self.device_info = "CPU (PyTorch not installed)"

        # Configure ONNX Runtime execution providers
        try:
            import onnxruntime as ort

            available_providers = ort.get_available_providers()
            if "CUDAExecutionProvider" in available_providers and self.cuda_available:
                self.onnx_providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
                logger.info("ONNX Runtime configured with CUDAExecutionProvider.")
            else:
                self.onnx_providers = ["CPUExecutionProvider"]
                logger.info("ONNX Runtime configured with CPUExecutionProvider.")
        except ImportError:
            self.onnx_providers = ["CPUExecutionProvider"]

    def _initialize_models(self) -> None:
        """
        Attempts to load physical weights for YOLO and InsightFace from backend/models/.
        Falls back safely to simulation mode if weights or dependencies are missing.
        """
        yolo_loaded = False
        face_loaded = False

        # 1. Attempt YOLO Initialization (Person Detection)
        yolo_weight_candidates = [
            self.models_dir / "yolo11n.pt",
            self.models_dir / "yolov8n.pt",
            self.models_dir / "yolov8s.pt",
        ]
        target_yolo = next((p for p in yolo_weight_candidates if p.exists()), None)

        try:
            from ultralytics import YOLO

            if target_yolo and target_yolo.exists():
                logger.info(f"Loading YOLO model from {target_yolo.name} on {self.pytorch_device}...")
                self.yolo_model = YOLO(str(target_yolo))
                self.yolo_model.to(self.pytorch_device)
                yolo_loaded = True
                logger.info(f"YOLO person detector initialized successfully on {self.pytorch_device}.")
            else:
                logger.warning(
                    f"Physical YOLO weights not found in {self.models_dir}. "
                    "Expected yolov8n.pt or yolo11n.pt."
                )
        except Exception as e:
            logger.warning(f"Could not initialize physical YOLO model: {e}")

        # 2. Attempt InsightFace / ArcFace Initialization (512-d Facial Embedding)
        try:
            from insightface.app import FaceAnalysis

            candidate_roots = [
                self.models_dir / "insightface",
                self.models_dir,
            ]
            root_dir = next(
                (p for p in candidate_roots if (p / "models" / "buffalo_l").exists() or (p / "buffalo_l").exists()),
                self.models_dir,
            )
            logger.info(f"Initializing InsightFace (buffalo_l) from root: {root_dir} with providers: {self.onnx_providers}...")
            ctx_id = 0 if self.cuda_available else -1
            self.face_analyzer = FaceAnalysis(
                name="buffalo_l",
                root=str(root_dir),
                providers=self.onnx_providers,
            )
            self.face_analyzer.prepare(ctx_id=ctx_id, det_size=(640, 640))
            face_loaded = True
            logger.info("InsightFace biometric analyzer initialized successfully.")
        except Exception as e:
            logger.warning(f"Could not initialize physical InsightFace analyzer: {e}")

        # Determine Operational Mode
        if yolo_loaded and face_loaded:
            self.is_simulated = False
            logger.info(f"UATU AI Access Engine running in LIVE INFERENCE mode ({self.device_info}).")
        else:
            self.is_simulated = True
            logger.warning(
                "====================================================================\n"
                "UATU AI Engine Warning: Physical weights or ML packages not present.\n"
                f"Models directory: {self.models_dir}\n"
                "Activating GPU Fallback / Simulation Mode for development safety.\n"
                "API endpoints and UI correlation telemetry will function without crash.\n"
                "===================================================================="
            )

    @staticmethod
    def compute_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Computes cosine similarity between two 512-dimensional facial feature vectors.
        Returns a float between 0.0 and 1.0.
        """
        v1 = np.asarray(vec1, dtype=np.float32).flatten()
        v2 = np.asarray(vec2, dtype=np.float32).flatten()

        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        dot_product = float(np.dot(v1, v2))
        similarity = dot_product / (norm1 * norm2)
        # Cosine similarity is in [-1, 1]; clip to [0, 1] for confidence representation
        return float(np.clip(similarity, 0.0, 1.0))

    async def evaluate_entry_event(
        self,
        video_frame: Optional[np.ndarray],
        scanned_rfid: str,
        expected_face_vector: Optional[np.ndarray] = None,
        simulated_person_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Core logic engine evaluating physical RFID access against live camera frames.

        Parameters:
        - video_frame: np.ndarray image matrix (H, W, C) from OpenCV camera capture.
        - scanned_rfid: Keycard/badge credential string (e.g. 'EMP-4092').
        - expected_face_vector: Enrolled 512-d biometric embedding for credential owner.
        - simulated_person_count: Optional test override for unit tests and simulation mocks.

        Returns:
        JSON-serializable dictionary with access verdict, confidence score,
        occupancy count, and spatial bounding boxes.
        """
        # Fallback to simulation if models are not loaded, frame is missing, or forced simulation count
        if self.is_simulated or self.yolo_model is None or video_frame is None or simulated_person_count is not None:
            return self._evaluate_simulated_event(
                video_frame=video_frame,
                scanned_rfid=scanned_rfid,
                expected_face_vector=expected_face_vector,
                forced_count=simulated_person_count,
            )

        # ---------------------------------------------------------------------
        # STEP 1: Person Detection via YOLO (COCO Class 0 = Person)
        # ---------------------------------------------------------------------
        bounding_boxes: List[Dict[str, Any]] = []
        person_count = 0

        if simulated_person_count is not None:
            person_count = simulated_person_count
        else:
            try:
                results = self.yolo_model(video_frame, classes=[0], verbose=False)
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        if conf >= 0.35:  # Confidence threshold for human presence
                            person_count += 1
                            bounding_boxes.append(
                                {
                                    "x1": round(x1, 1),
                                    "y1": round(y1, 1),
                                    "x2": round(x2, 1),
                                    "y2": round(y2, 1),
                                    "confidence": round(conf, 3),
                                    "label": "person",
                                }
                            )
            except Exception as e:
                logger.error(f"Error during YOLO person detection inference: {e}")
                person_count = 1

        # Check for TAILGATING breach: Multiple individuals in turnstile zone
        if person_count > 1:
            return {
                "status": "TAILGATING",
                "match_score_pct": 0.0,
                "person_count": person_count,
                "bounding_boxes": bounding_boxes,
                "scanned_rfid": scanned_rfid,
                "detail": f"Physical breach detected: {person_count} persons detected traversing optical turnstile on single badge scan ({scanned_rfid}).",
                "execution_device": self.device_info,
                "simulated": False,
            }

        # Check if portal is empty
        if person_count == 0:
            return {
                "status": "MISMATCH",
                "match_score_pct": 0.0,
                "person_count": 0,
                "bounding_boxes": [],
                "scanned_rfid": scanned_rfid,
                "detail": f"Optical portal vacant: Badge ({scanned_rfid}) scanned without subject present.",
                "execution_device": self.device_info,
                "simulated": False,
            }

        # ---------------------------------------------------------------------
        # STEP 2: Biometric Facial Embedding Extraction via ArcFace / InsightFace
        # ---------------------------------------------------------------------
        match_score = 0.0
        face_detected = False

        if self.face_analyzer is not None:
            try:
                faces = self.face_analyzer.get(video_frame)
                if faces:
                    face_detected = True
                    # Select largest face by bounding box area
                    best_face = max(
                        faces,
                        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
                    )
                    live_embedding = best_face.embedding  # 512-dimensional float vector

                    # Append face bounding box
                    fx1, fy1, fx2, fy2 = best_face.bbox.tolist()
                    bounding_boxes.append(
                        {
                            "x1": round(fx1, 1),
                            "y1": round(fy1, 1),
                            "x2": round(fx2, 1),
                            "y2": round(fy2, 1),
                            "confidence": round(float(getattr(best_face, "det_score", 0.95)), 3),
                            "label": "face",
                        }
                    )

                    # Compute cosine similarity against enrolled profile vector
                    if expected_face_vector is not None:
                        match_score = self.compute_cosine_similarity(
                            live_embedding, expected_face_vector
                        )
                    else:
                        # Attempt biometric retrieval from in-memory registry
                        try:
                            from backend.app.biometric_registry import biometric_registry
                            rec = biometric_registry.get_employee(scanned_rfid)
                            if rec and "embedding" in rec:
                                match_score = self.compute_cosine_similarity(
                                    live_embedding, rec["embedding"]
                                )
                            else:
                                best_rec, best_sim, _ = biometric_registry.find_best_match(live_embedding)
                                match_score = best_sim if best_rec else 0.0
                        except Exception as e:
                            logger.debug(f"Biometric retrieval lookup in access_engine: {e}")
                            match_score = 0.0
            except Exception as e:
                logger.error(f"Error during InsightFace facial vector extraction: {e}")
                match_score = 0.0

        # ---------------------------------------------------------------------
        # STEP 3: Verdict Determination (Calibrated ArcFace Threshold: 0.45)
        # ---------------------------------------------------------------------
        threshold = 0.45
        status = "AUTHORIZED" if match_score >= threshold else "MISMATCH"
        match_score_pct = round(match_score * 100, 2)

        return {
            "status": status,
            "match_score_pct": match_score_pct,
            "person_count": person_count,
            "bounding_boxes": bounding_boxes,
            "scanned_rfid": scanned_rfid,
            "detail": (
                f"Biometric verification successful: {match_score_pct}% cosine match against enrolled credential."
                if status == "AUTHORIZED"
                else (
                    f"Facial verification mismatch: Live subject returned {match_score_pct}% match (threshold: {round(threshold * 100, 1)}%)."
                    if face_detected
                    else f"Facial acquisition failed: No visible face located in camera frame for badge ({scanned_rfid})."
                )
            ),
            "execution_device": self.device_info,
            "simulated": False,
        }


    def _evaluate_simulated_event(
        self,
        video_frame: Optional[np.ndarray],
        scanned_rfid: str,
        expected_face_vector: Optional[np.ndarray],
        forced_count: Optional[int],
    ) -> Dict[str, Any]:
        """Deterministic simulation for local testing when weights are not present."""
        # Calculate image dimensions if frame is provided
        h, w = (480, 640) if video_frame is None else video_frame.shape[:2]

        person_count = forced_count if forced_count is not None else 1

        # Check for simulated tailgating
        if person_count > 1:
            boxes = [
                {"x1": int(w * 0.15), "y1": int(h * 0.1), "x2": int(w * 0.5), "y2": int(h * 0.9), "confidence": 0.94, "label": "person"},
                {"x1": int(w * 0.55), "y1": int(h * 0.15), "x2": int(w * 0.88), "y2": int(h * 0.92), "confidence": 0.91, "label": "person"},
            ]
            return {
                "status": "TAILGATING",
                "match_score_pct": 0.0,
                "person_count": person_count,
                "bounding_boxes": boxes,
                "scanned_rfid": scanned_rfid,
                "detail": f"[SIMULATION] Physical breach: {person_count} persons in portal on single badge ({scanned_rfid}).",
                "execution_device": f"{self.device_info} (SIMULATED)",
                "simulated": True,
            }

        # Simulated single person
        boxes = [
            {"x1": int(w * 0.25), "y1": int(h * 0.15), "x2": int(w * 0.75), "y2": int(h * 0.88), "confidence": 0.96, "label": "person"},
            {"x1": int(w * 0.4), "y1": int(h * 0.2), "x2": int(w * 0.6), "y2": int(h * 0.45), "confidence": 0.98, "label": "face"},
        ]

        # Use expected vector if provided, else assign based on RFID
        if expected_face_vector is not None:
            # Deterministic similarity based on vector norm
            norm = float(np.linalg.norm(expected_face_vector))
            match_score = min(0.96, max(0.42, norm / 10.0 if norm > 0 else 0.94))
        elif "REVOKED" in scanned_rfid.upper() or "MISMATCH" in scanned_rfid.upper():
            match_score = 0.418
        else:
            match_score = 0.962

        status = "AUTHORIZED" if match_score >= 0.85 else "MISMATCH"
        match_score_pct = round(match_score * 100, 2)

        return {
            "status": status,
            "match_score_pct": match_score_pct,
            "person_count": person_count,
            "bounding_boxes": boxes,
            "scanned_rfid": scanned_rfid,
            "detail": (
                f"[SIMULATION] Biometric verification {status}: Scanned credential {scanned_rfid} returned {match_score_pct}% cosine match."
            ),
            "execution_device": f"{self.device_info} (SIMULATED)",
            "simulated": True,
        }


# Singleton access engine instance
access_engine = AccessCorrelationEngine()


async def evaluate_entry_event(
    video_frame: Optional[np.ndarray],
    scanned_rfid: str,
    expected_face_vector: Optional[np.ndarray] = None,
    simulated_person_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Module-level helper evaluating physical badge swipe alongside OpenCV camera feed."""
    return await access_engine.evaluate_entry_event(
        video_frame=video_frame,
        scanned_rfid=scanned_rfid,
        expected_face_vector=expected_face_vector,
        simulated_person_count=simulated_person_count,
    )
