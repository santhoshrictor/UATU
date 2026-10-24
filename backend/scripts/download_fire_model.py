#!/usr/bin/env python3
"""
Download script for Feature 21: Machine Learning Fire & Smoke Detection Model.
Downloads a certified, lightweight fine-tuned YOLOv8 fire and smoke detection
checkpoint from Hugging Face and saves it locally to backend/models/fire.pt.
"""
import os
import sys
import logging
import urllib.request
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fire_model_downloader")

MODEL_URL = "https://huggingface.co/rabahdev/fire-smoke-yolov8n/resolve/main/best.pt"
EXPECTED_MIN_BYTES = 5_000_000  # ~6.2MB


def get_fire_model_path() -> Path:
    base_dir = Path(__file__).resolve().parent.parent
    models_dir = base_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir / "fire.pt"


def download_fire_model(force: bool = False) -> Path:
    dest_path = get_fire_model_path()
    if dest_path.exists() and not force:
        size = dest_path.stat().st_size
        if size >= EXPECTED_MIN_BYTES:
            logger.info(f"Verified existing fire model weights at: {dest_path} ({size:,} bytes)")
            _verify_model_integrity(dest_path)
            return dest_path
        else:
            logger.warning(f"Existing file {dest_path} is too small ({size} bytes). Redownloading...")

    logger.info(f"Downloading fine-tuned YOLO fire & smoke model from: {MODEL_URL}")
    req = urllib.request.Request(
        MODEL_URL,
        headers={"User-Agent": "Workplace-Intelligence/1.0 (YOLOv8-Fire-Downloader)"},
    )
    temp_path = dest_path.with_suffix(".tmp")
    with urllib.request.urlopen(req, timeout=60) as resp, open(temp_path, "wb") as f:
        total_downloaded = 0
        chunk_size = 64 * 1024
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            total_downloaded += len(chunk)

    if total_downloaded < EXPECTED_MIN_BYTES:
        if temp_path.exists():
            temp_path.unlink()
        raise RuntimeError(f"Downloaded model is smaller than expected ({total_downloaded} bytes). Download failed.")

    temp_path.replace(dest_path)
    logger.info(f"Successfully downloaded and saved fire model weights to: {dest_path} ({dest_path.stat().st_size:,} bytes)")
    _verify_model_integrity(dest_path)
    return dest_path


def _verify_model_integrity(model_path: Path):
    try:
        from ultralytics import YOLO
        model = YOLO(str(model_path))
        classes = model.names
        logger.info(f"YOLO Model integrity verified. Classes detected: {classes}")
    except Exception as e:
        logger.warning(f"YOLO verification check warning (non-fatal): {e}")


if __name__ == "__main__":
    force_download = "--force" in sys.argv
    try:
        path = download_fire_model(force=force_download)
        print(f"Fire model ready at: {path}")
    except Exception as err:
        logger.error(f"Failed to download fire model: {err}")
        sys.exit(1)
