"""
UATU Biometric Enrollment Utility
=================================
Interactive face enrollment CLI supporting:
1. Dynamic camera hardware selection (Index 0 for Iriun/Mobile, Index 1 for Laptop).
2. Live OpenCV viewport with biometric capture guides (SPACE to capture, ESC to exit).
3. 512-dimensional facial embedding extraction via InsightFace (buffalo_l ArcFace).
4. Non-destructive database persistence in `backend/mock_employee_db.pkl`.
"""

import argparse
import os
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np

# Path resolution
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
MODELS_DIR = BACKEND_DIR / "models"
DB_PATH = BACKEND_DIR / "mock_employee_db.pkl"


def load_insightface_app() -> Any:
    """Initializes the InsightFace FaceAnalysis pipeline using local buffalo_l models."""
    try:
        from insightface.app import FaceAnalysis

        candidate_roots = [
            MODELS_DIR / "insightface",
            MODELS_DIR,
        ]
        root_dir = next(
            (p for p in candidate_roots if (p / "models" / "buffalo_l").exists() or (p / "buffalo_l").exists()),
            MODELS_DIR,
        )

        app = FaceAnalysis(name="buffalo_l", root=str(root_dir))
        try:
            import torch
            ctx_id = 0 if torch.cuda.is_available() else -1
        except Exception:
            ctx_id = -1

        app.prepare(ctx_id=ctx_id, det_size=(640, 640))
        return app
    except Exception as e:
        print(f"[ERROR] Could not load InsightFace model: {e}", flush=True)
        print("[HINT] Run: python backend/scripts/download_models.py to install buffalo_l weights.", flush=True)
        return None


def enroll_identity(
    employee_id: str,
    full_name: str,
    roll_number: str,
    embedding: np.ndarray,
    db_path: Path = DB_PATH,
) -> Dict[str, Any]:
    """
    Appends or updates an employee biometric profile in the pickle database file.
    Preserves all existing teammate enrollments.
    """
    db: Dict[str, Any] = {}
    if db_path.exists():
        try:
            with open(db_path, "rb") as f:
                loaded = pickle.load(f)
                if isinstance(loaded, dict):
                    db = loaded
                    print(f"Loaded existing database with {len(db)} enrolled identities.", flush=True)
        except Exception as e:
            print(f"[WARNING] Existing database could not be loaded ({e}). Initializing new database.", flush=True)

    # Normalize embedding vector
    norm = np.linalg.norm(embedding)
    normalized_embedding = (embedding / norm) if norm > 0 else embedding

    # Store entry matching required technical schema
    db[employee_id] = {
        "name": full_name,
        "roll": roll_number,
        "embedding": normalized_embedding,
    }

    # Atomically save updated database
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with open(db_path, "wb") as f:
        pickle.dump(db, f)

    print(f"[SUCCESS] Enrolled {full_name} ({roll_number}) under {employee_id}.", flush=True)
    print(f"Database now contains {len(db)} registered identities.", flush=True)
    return db[employee_id]


def capture_and_enroll(
    camera_index: int,
    employee_id: str,
    full_name: str,
    roll_number: str,
    face_app: Any,
    db_path: Path = DB_PATH,
) -> bool:
    """Opens live camera stream, renders HUD overlay, and captures on SPACE key."""
    if sys.platform.startswith("win"):
        cap = cv2.VideoCapture(int(camera_index), cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(int(camera_index))

    if not cap.isOpened():
        print(f"[ERROR] Unable to open camera on device index {camera_index}.", flush=True)
        print("[HINT] Verify camera connection or select index 0 / 1.", flush=True)
        return False

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    window_name = f"UATU Face Enrollment — {employee_id}"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    print("\n=======================================================", flush=True)
    print(f" Camera Feed Open for: {full_name} ({employee_id})")
    print(" Position face in the center of the viewport.")
    print(" Press [SPACE] to capture biometric embedding.")
    print(" Press [ESC] or [Q] to cancel.")
    print("=======================================================\n", flush=True)

    enrolled = False
    status_message = "Ready: Press SPACE to Capture"
    status_color = (16, 185, 129)  # Emerald green

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("[WARNING] Frame drop from camera. Retrying...", flush=True)
            cv2.waitKey(30)
            continue

        display = frame.copy()
        h, w = display.shape[:2]

        # Draw biometric viewfinder guides
        cx, cy = w // 2, h // 2
        box_w, box_h = int(w * 0.45), int(h * 0.6)
        x1, y1 = cx - box_w // 2, cy - box_h // 2
        x2, y2 = cx + box_w // 2, cy + box_h // 2

        # Viewport target box
        cv2.rectangle(display, (x1, y1), (x2, y2), (75, 85, 99), 1)
        # Corner reticles
        reticle_len = 20
        cv2.line(display, (x1, y1), (x1 + reticle_len, y1), (16, 185, 129), 2)
        cv2.line(display, (x1, y1), (x1, y1 + reticle_len), (16, 185, 129), 2)
        cv2.line(display, (x2, y1), (x2 - reticle_len, y1), (16, 185, 129), 2)
        cv2.line(display, (x2, y1), (x2, y1 + reticle_len), (16, 185, 129), 2)
        cv2.line(display, (x1, y2), (x1 + reticle_len, y2), (16, 185, 129), 2)
        cv2.line(display, (x1, y2), (x1, y2 - reticle_len), (16, 185, 129), 2)
        cv2.line(display, (x2, y2), (x2 - reticle_len, y2), (16, 185, 129), 2)
        cv2.line(display, (x2, y2), (x2, y2 - reticle_len), (16, 185, 129), 2)

        # HUD Top Banner
        cv2.rectangle(display, (0, 0), (w, 55), (15, 23, 42), -1)
        cv2.putText(
            display,
            f"ENROLL: {full_name} | ID: {employee_id} | ROLL: {roll_number}",
            (15, 22),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (248, 250, 252),
            1,
        )
        cv2.putText(
            display,
            status_message,
            (15, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            status_color,
            1,
        )

        # HUD Bottom Controls
        cv2.rectangle(display, (0, h - 30), (w, h), (15, 23, 42), -1)
        cv2.putText(
            display,
            "[SPACE] Capture & Enroll  |  [ESC/Q] Cancel",
            (15, h - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (148, 163, 184),
            1,
        )

        cv2.imshow(window_name, display)
        key = cv2.waitKey(1) & 0xFF

        # SPACE Key -> Trigger Face Embedding Extraction
        if key == 32:
            status_message = "Analyzing facial geometry..."
            status_color = (245, 158, 11)  # Amber
            cv2.imshow(window_name, display)
            cv2.waitKey(10)

            faces = face_app.get(frame) if face_app is not None else []
            if not faces:
                status_message = "ERROR: No face located. Please reposition and press SPACE."
                status_color = (239, 68, 68)  # Red
                print("[WARNING] No face detected in captured frame. Reposition and press SPACE.", flush=True)
                continue

            # Select most prominent face
            best_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
            embedding = best_face.embedding  # 512-d float32 array

            # Visual confirmation
            fx1, fy1, fx2, fy2 = [int(v) for v in best_face.bbox]
            cv2.rectangle(display, (fx1, fy1), (fx2, fy2), (16, 185, 129), 2)
            cv2.putText(
                display,
                "512-D EMBEDDING EXTRACTED",
                (fx1, max(20, fy1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (16, 185, 129),
                2,
            )
            cv2.imshow(window_name, display)
            cv2.waitKey(600)

            enroll_identity(
                employee_id=employee_id,
                full_name=full_name,
                roll_number=roll_number,
                embedding=embedding,
                db_path=db_path,
            )
            enrolled = True
            break

        # ESC or Q -> Cancel
        if key in (27, ord("q"), ord("Q")):
            print("\n[INFO] Enrollment cancelled by user.", flush=True)
            break

    cap.release()
    cv2.destroyAllWindows()
    return enrolled


def main() -> None:
    """Interactive entry point for terminal enrollment."""
    print("=======================================================", flush=True)
    print("  UATU BIOMETRIC ACCESS CONTROL // FACE ENROLLMENT")
    print("=======================================================", flush=True)

    # 1. Interactive Terminal Prompts
    try:
        raw_cam = input("Camera Index (0 for Iriun/Mobile, 1 for Laptop) [default 0]: ").strip()
        camera_index = int(raw_cam) if raw_cam else 0

        employee_id = input("Employee ID (e.g., EMP-1001): ").strip()
        while not employee_id:
            print("Employee ID cannot be empty.")
            employee_id = input("Employee ID (e.g., EMP-1001): ").strip()

        full_name = input("Full Name: ").strip()
        while not full_name:
            print("Full Name cannot be empty.")
            full_name = input("Full Name: ").strip()

        roll_number = input("Roll Number: ").strip()
        while not roll_number:
            print("Roll Number cannot be empty.")
            roll_number = input("Roll Number: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n[INFO] Enrollment aborted.", flush=True)
        sys.exit(0)

    # 2. Load InsightFace Model
    print("\n[INFO] Initializing InsightFace buffalo_l ArcFace engine...", flush=True)
    face_app = load_insightface_app()
    if face_app is None:
        print("[ERROR] Failed to load biometric model. Aborting.", flush=True)
        sys.exit(1)

    # 3. Capture & Enroll
    success = capture_and_enroll(
        camera_index=camera_index,
        employee_id=employee_id,
        full_name=full_name,
        roll_number=roll_number,
        face_app=face_app,
    )

    if success:
        print(f"\n[DONE] Enrollment pipeline completed for {full_name}.", flush=True)
    else:
        print("\n[ABORTED] No biometric record was saved.", flush=True)


if __name__ == "__main__":
    main()
