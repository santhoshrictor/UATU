import pickle
from unittest.mock import MagicMock, patch
import cv2
from fastapi.testclient import TestClient
import numpy as np
import pytest

from backend.app.main import app

client = TestClient(app)


@pytest.fixture
def mock_employee_db(tmp_path):
    db_file = tmp_path / "mock_employee_db.pkl"
    # Pre-populate with an enrolled employee
    emb = np.ones(512, dtype=np.float32)
    emb /= np.linalg.norm(emb)
    data = {
        "EMP-TEST-01": {
            "name": "Alice Engineer",
            "roll": "ENG-101",
            "embedding": emb,
        }
    }
    with open(db_file, "wb") as f:
        pickle.dump(data, f)
    return db_file


def test_verify_access_employee_not_found(mock_employee_db):
    with patch("backend.app.main.MOCK_DB_PATH", mock_employee_db):
        resp = client.post("/api/verify-access", json={
            "device_id": 1,
            "employee_id": "EMP-NONEXISTENT",
        })
        assert resp.status_code == 404
        assert "not found in database" in resp.json().get("error", "")


def test_verify_access_authorized(mock_employee_db):
    # Create fake jpeg frame
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", blank)
    jpeg_bytes = buf.tobytes()

    mock_worker = MagicMock()
    mock_worker.get_latest_jpeg.return_value = jpeg_bytes

    # Mock YOLO to return 1 person
    mock_box = MagicMock()
    mock_box.cls = [MagicMock(item=lambda: 0)]  # class 0: person
    mock_res = MagicMock()
    mock_res.boxes = [mock_box]

    mock_yolo = MagicMock(return_value=[mock_res])

    # Mock InsightFace to return a face matching Alice (similarity > 0.50)
    mock_face = MagicMock()
    mock_face.bbox = np.array([50, 50, 200, 200])
    matching_emb = np.ones(512, dtype=np.float32)
    matching_emb /= np.linalg.norm(matching_emb)
    mock_face.embedding = matching_emb

    with patch("backend.app.main.MOCK_DB_PATH", mock_employee_db):
        with patch("backend.app.main.multi_webcam_manager.get_worker", return_value=mock_worker):
            with patch("backend.app.main.yolo_model", mock_yolo):
                with patch("backend.app.main.face_analysis_app.get", return_value=[mock_face]):
                    resp = client.post("/api/verify-access", json={
                        "device_id": 1,
                        "employee_id": "EMP-TEST-01",
                    })
                    assert resp.status_code == 200
                    payload = resp.json()
                    assert payload["status"] == "AUTHORIZED"
                    assert payload["employee_name"] == "Alice Engineer"
                    assert payload["person_count"] == 1
                    assert payload["match_score"] >= 50.0


def test_verify_access_tailgating(mock_employee_db):
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", blank)
    jpeg_bytes = buf.tobytes()

    mock_worker = MagicMock()
    mock_worker.get_latest_jpeg.return_value = jpeg_bytes

    # Mock YOLO to return 2 persons
    box1 = MagicMock()
    box1.cls = [MagicMock(item=lambda: 0)]
    box2 = MagicMock()
    box2.cls = [MagicMock(item=lambda: 0)]
    mock_res = MagicMock()
    mock_res.boxes = [box1, box2]

    mock_yolo = MagicMock(return_value=[mock_res])

    # Even if face matches, person_count > 1 forces TAILGATING
    mock_face = MagicMock()
    mock_face.bbox = np.array([50, 50, 200, 200])
    matching_emb = np.ones(512, dtype=np.float32)
    matching_emb /= np.linalg.norm(matching_emb)
    mock_face.embedding = matching_emb

    with patch("backend.app.main.MOCK_DB_PATH", mock_employee_db):
        with patch("backend.app.main.multi_webcam_manager.get_worker", return_value=mock_worker):
            with patch("backend.app.main.yolo_model", mock_yolo):
                with patch("backend.app.main.face_analysis_app.get", return_value=[mock_face]):
                    resp = client.post("/api/verify-access", json={
                        "device_id": 1,
                        "employee_id": "EMP-TEST-01",
                    })
                    assert resp.status_code == 200
                    payload = resp.json()
                    assert payload["status"] == "TAILGATING"
                    assert payload["person_count"] == 2


def test_verify_access_mismatch(mock_employee_db):
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", blank)
    jpeg_bytes = buf.tobytes()

    mock_worker = MagicMock()
    mock_worker.get_latest_jpeg.return_value = jpeg_bytes

    # 1 person detected
    box1 = MagicMock()
    box1.cls = [MagicMock(item=lambda: 0)]
    mock_res = MagicMock()
    mock_res.boxes = [box1]
    mock_yolo = MagicMock(return_value=[mock_res])

    # Mismatch face embedding (orthogonal/opposite vector)
    mock_face = MagicMock()
    mock_face.bbox = np.array([50, 50, 200, 200])
    mismatch_emb = -np.ones(512, dtype=np.float32)
    mismatch_emb /= np.linalg.norm(mismatch_emb)
    mock_face.embedding = mismatch_emb

    with patch("backend.app.main.MOCK_DB_PATH", mock_employee_db):
        with patch("backend.app.main.multi_webcam_manager.get_worker", return_value=mock_worker):
            with patch("backend.app.main.yolo_model", mock_yolo):
                with patch("backend.app.main.face_analysis_app.get", return_value=[mock_face]):
                    resp = client.post("/api/verify-access", json={
                        "device_id": 1,
                        "employee_id": "EMP-TEST-01",
                    })
                    assert resp.status_code == 200
                    payload = resp.json()
                    assert payload["status"] == "MISMATCH"
                    assert payload["match_score"] < 50.0
