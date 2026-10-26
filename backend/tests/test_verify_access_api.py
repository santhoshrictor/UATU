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


def test_verify_access_specific_target_lookup(tmp_path):
    """
    Verifies that when multiple employees exist in the registry, verify_access
    specifically reads and compares against the exact Employee ID provided in the request
    (e.g., EMP-1234) rather than defaulting to the first or static entry.
    """
    db_file = tmp_path / "mock_employee_db.pkl"

    # Enrolled Employee 1 (first entry in pickle)
    emb_alice = np.zeros(512, dtype=np.float32)
    emb_alice[0] = 1.0

    # Enrolled Employee 2 (target entry in pickle)
    emb_bob = np.zeros(512, dtype=np.float32)
    emb_bob[1] = 1.0

    data = {
        "EMP-001": {
            "name": "Alice First",
            "roll": "ENG-001",
            "embedding": emb_alice,
        },
        "EMP-1234": {
            "name": "Bob Target",
            "roll": "ENG-1234",
            "embedding": emb_bob,
        },
    }
    with open(db_file, "wb") as f:
        pickle.dump(data, f)

    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", blank)
    jpeg_bytes = buf.tobytes()

    mock_worker = MagicMock()
    mock_worker.get_latest_jpeg.return_value = jpeg_bytes

    # 1 person detected
    mock_box = MagicMock()
    mock_box.cls = [MagicMock(item=lambda: 0)]
    mock_res = MagicMock()
    mock_res.boxes = [mock_box]
    mock_yolo = MagicMock(return_value=[mock_res])

    # Live face matches Bob (emb_bob)
    mock_face = MagicMock()
    mock_face.bbox = np.array([50, 50, 200, 200])
    mock_face.embedding = emb_bob.copy()

    with patch("backend.app.main.MOCK_DB_PATH", db_file):
        with patch("backend.app.main.multi_webcam_manager.get_worker", return_value=mock_worker):
            with patch("backend.app.main.yolo_model", mock_yolo):
                with patch("backend.app.main.face_analysis_app.get", return_value=[mock_face]):
                    # 1. Verification explicitly for EMP-1234 should AUTHORIZE Bob
                    resp_bob = client.post("/api/verify-access", json={
                        "device_id": 1,
                        "employee_id": "EMP-1234",
                    })
                    assert resp_bob.status_code == 200
                    data_bob = resp_bob.json()
                    assert data_bob["status"] == "AUTHORIZED"
                    assert data_bob["employee_id"] == "EMP-1234"
                    assert data_bob["employee_name"] == "Bob Target"
                    assert data_bob["match_score"] > 95.0

                    # 2. Verification explicitly for EMP-001 with Bob's face should MISMATCH (not Bob authorized as Alice)
                    resp_alice = client.post("/api/verify-access", json={
                        "device_id": 1,
                        "employee_id": "EMP-001",
                    })
                    assert resp_alice.status_code == 200
                    data_alice = resp_alice.json()
                    assert data_alice["status"] == "MISMATCH"
                    assert data_alice["employee_id"] == "EMP-001"
                    assert data_alice["employee_name"] == "Alice First"
                    assert data_alice["match_score"] < 10.0

