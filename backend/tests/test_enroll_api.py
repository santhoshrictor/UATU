from unittest.mock import MagicMock, patch
import numpy as np
import cv2
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_enroll_api_no_face_detected():
    # Create a synthetic black frame as JPEG
    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    _, buffer = cv2.imencode('.jpg', blank_frame)
    jpeg_bytes = buffer.tobytes()

    mock_worker = MagicMock()
    mock_worker.get_latest_jpeg.return_value = jpeg_bytes

    with patch("backend.app.main.multi_webcam_manager.get_worker", return_value=mock_worker):
        # We also mock face_analysis_app.get to return empty list (no face)
        with patch("backend.app.main.face_analysis_app.get", return_value=[]):
            response = client.post("/api/enroll", json={
                "device_id": 1,
                "employee_id": "EMP-TEST-99",
                "name": "Test Subject",
                "roll": "TEST-01"
            })
            assert response.status_code == 400
            data = response.json()
            assert "No face detected in frame" in data.get("error", "")


def test_enroll_api_success(tmp_path):
    blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    _, buffer = cv2.imencode('.jpg', blank_frame)
    jpeg_bytes = buffer.tobytes()

    mock_worker = MagicMock()
    mock_worker.get_latest_jpeg.return_value = jpeg_bytes

    # Create a mock face object with bbox and embedding
    mock_face = MagicMock()
    mock_face.bbox = np.array([100, 100, 300, 300])
    raw_emb = np.random.randn(512).astype(np.float32)
    mock_face.embedding = raw_emb

    test_db_path = tmp_path / "mock_employee_db.pkl"

    with patch("backend.app.main.multi_webcam_manager.get_worker", return_value=mock_worker):
        with patch("backend.app.main.face_analysis_app.get", return_value=[mock_face]):
            with patch("backend.app.main.MOCK_DB_PATH", test_db_path):
                response = client.post("/api/enroll", json={
                    "device_id": 1,
                    "employee_id": "EMP-GUI-001",
                    "name": "Jane Developer",
                    "roll": "ROL-7721"
                })
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert "Jane Developer" in data["message"]
                assert data["employee_id"] == "EMP-GUI-001"
                assert data["roll"] == "ROL-7721"

                # Check enrolled-users endpoint
                users_resp = client.get("/api/enrolled-users")
                assert users_resp.status_code == 200
                users_data = users_resp.json()
                enrolled_ids = [u["employee_id"] for u in users_data.get("users", [])]
                assert "EMP-GUI-001" in enrolled_ids
