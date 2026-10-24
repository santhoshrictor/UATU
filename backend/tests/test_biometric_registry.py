import pickle
import numpy as np
import pytest

from backend.app.biometric_registry import BiometricRegistry


@pytest.fixture
def sample_registry(tmp_path):
    db_file = tmp_path / "mock_employee_db.pkl"

    # Create distinct orthogonal-like unit vectors
    v1 = np.zeros(512, dtype=np.float32)
    v1[0:50] = 1.0
    v1 /= np.linalg.norm(v1)

    v2 = np.zeros(512, dtype=np.float32)
    v2[50:100] = 1.0
    v2 /= np.linalg.norm(v2)

    v3 = np.zeros(512, dtype=np.float32)
    v3[100:150] = 1.0
    v3 /= np.linalg.norm(v3)

    data = {
        "EMP-1234": {
            "name": "HARI PRASATH",
            "roll": "32CAT",
            "embedding": v1,
        },
        "EMP-3000": {
            "name": "Sam Taylor",
            "roll": "43CAT",
            "embedding": v2,
        },
        "EMP-5000": {
            "name": "Alex Vance",
            "roll": "55RES",
            "embedding": v3,
        },
    }
    with open(db_file, "wb") as f:
        pickle.dump(data, f)

    reg = BiometricRegistry(db_path=db_file)
    return reg, (v1, v2, v3)


def test_registry_initialization_and_matrix(sample_registry):
    reg, (v1, v2, v3) = sample_registry
    assert len(reg.list_enrolled()) == 3
    assert reg._embedding_matrix is not None
    assert reg._embedding_matrix.shape == (3, 512)


def test_registry_flexible_lookup(sample_registry):
    reg, _ = sample_registry
    # Exact lookup
    assert reg.get_employee("EMP-1234")["name"] == "HARI PRASATH"
    # Case-insensitive lookup
    assert reg.get_employee("emp-1234")["name"] == "HARI PRASATH"
    # Badge suffix lookup
    assert reg.get_employee("1234")["name"] == "HARI PRASATH"
    # Roll lookup
    assert reg.get_employee("32cat")["name"] == "HARI PRASATH"
    # Name lookup
    assert reg.get_employee("hari prasath")["employee_id"] == "EMP-1234"
    # Non-existent
    assert reg.get_employee("EMP-9999") is None


def test_registry_1_to_n_retrieval(sample_registry):
    reg, (v1, v2, v3) = sample_registry

    # Query with slightly noisy v1 (cosine similarity > 0.90)
    noisy_v1 = v1 + np.random.normal(0, 0.01, size=512).astype(np.float32)
    noisy_v1 /= np.linalg.norm(noisy_v1)

    best_rec, best_sim, candidates = reg.find_best_match(noisy_v1, threshold=0.45)
    assert best_rec is not None
    assert best_rec["employee_id"] == "EMP-1234"
    assert best_sim >= 0.85
    assert candidates[0]["employee_id"] == "EMP-1234"


def test_registry_verification_authorized(sample_registry):
    reg, (v1, v2, v3) = sample_registry

    res = reg.verify_or_identify(v1, employee_id="EMP-1234", threshold=0.45)
    assert res["status"] == "AUTHORIZED"
    assert res["is_authorized"] is True
    assert res["employee_name"] == "HARI PRASATH"
    assert res["match_score"] >= 95.0


def test_registry_verification_mismatch(sample_registry):
    reg, (v1, v2, v3) = sample_registry

    # Scan badge EMP-1234, but face is v2 (Sam Taylor)
    res = reg.verify_or_identify(v2, employee_id="EMP-1234", threshold=0.45)
    assert res["status"] == "MISMATCH"
    assert res["is_authorized"] is False
    assert res["employee_id"] == "EMP-1234"
    # Diagnostic detail should note that the live face matched Sam Taylor
    assert "Sam Taylor" in res["detail"] or "EMP-3000" in res["detail"]


def test_registry_auto_identification(sample_registry):
    reg, (v1, v2, v3) = sample_registry

    # No ID supplied or AUTO mode
    res = reg.verify_or_identify(v3, employee_id=None, threshold=0.45)
    assert res["status"] == "AUTHORIZED"
    assert res["auto_identified"] is True
    assert res["employee_id"] == "EMP-5000"
    assert res["employee_name"] == "Alex Vance"


def test_registry_enroll_and_disk_persistence(tmp_path):
    db_file = tmp_path / "mock_employee_db.pkl"
    reg = BiometricRegistry(db_path=db_file)
    assert len(reg.list_enrolled()) == 0

    new_vec = np.ones(512, dtype=np.float32)
    enroll_info = reg.enroll("EMP-9001", "Gordon Freeman", "PHYS-01", new_vec)
    assert enroll_info["total_enrolled"] == 1
    assert len(reg.list_enrolled()) == 1

    # Verify reload from disk
    reg2 = BiometricRegistry(db_path=db_file)
    assert len(reg2.list_enrolled()) == 1
    rec = reg2.get_employee("EMP-9001")
    assert rec["name"] == "Gordon Freeman"
    assert rec["roll"] == "PHYS-01"
