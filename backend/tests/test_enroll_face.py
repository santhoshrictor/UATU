import pickle
from pathlib import Path
import numpy as np
import pytest

from backend.scripts.enroll_face import enroll_identity


def test_enroll_identity_single_and_multiple(tmp_path: Path):
    db_file = tmp_path / "test_employee_db.pkl"

    # 1. Enroll First Employee
    vec1 = np.random.randn(512).astype(np.float32)
    entry1 = enroll_identity(
        employee_id="EMP-1001",
        full_name="Sandy Admin",
        roll_number="R-2026-001",
        embedding=vec1,
        db_path=db_file,
    )

    assert entry1["name"] == "Sandy Admin"
    assert entry1["roll"] == "R-2026-001"
    assert entry1["embedding"].shape == (512,)
    # Verify unit normalization
    assert pytest.approx(np.linalg.norm(entry1["embedding"]), 0.001) == 1.0

    # 2. Verify file written and reloaded
    with open(db_file, "rb") as f:
        db = pickle.load(f)
    assert len(db) == 1
    assert "EMP-1001" in db

    # 3. Enroll Second Employee (Preserve Previous)
    vec2 = np.random.randn(512).astype(np.float32)
    entry2 = enroll_identity(
        employee_id="EMP-1002",
        full_name="Teammate Alex",
        roll_number="R-2026-002",
        embedding=vec2,
        db_path=db_file,
    )

    with open(db_file, "rb") as f:
        db_updated = pickle.load(f)

    # Must contain both entries
    assert len(db_updated) == 2
    assert "EMP-1001" in db_updated
    assert "EMP-1002" in db_updated
    assert db_updated["EMP-1001"]["name"] == "Sandy Admin"
    assert db_updated["EMP-1002"]["name"] == "Teammate Alex"
    assert db_updated["EMP-1002"]["roll"] == "R-2026-002"
