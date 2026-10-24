"""
UATU Biometric Embedding Registry & Vector Retrieval Engine
===========================================================
Maintains an in-memory, thread-safe cache of enrolled personnel ArcFace embeddings.

Capabilities:
1. High-Performance In-Memory Embedding Cache:
   - Loads mock_employee_db.pkl on startup.
   - Monitors file modification timestamp (_mtime) to automatically re-sync with disk.
   - Normalizes and stacks 512-d feature vectors into a contiguous numpy matrix for instant vectorized computation.
2. 1:N Biometric Retrieval & Matching (ArcFace Cosine Similarity):
   - Fast matrix dot-product: similarity_scores = Matrix @ query_vector
   - Sub-millisecond similarity retrieval across thousands of enrolled identities.
3. 1:1 Credential Verification:
   - Flexible lookup: exact ID, case-insensitive ID, badge number, roll number, or personnel name.
   - Computes normalized cosine similarity against the specified profile.
4. Autonomous Identity Discovery:
   - If ID is unspecified, placeholder ('EMP-1001'), or 'AUTO', searches memory to identify who is in front of the camera.
   - Calibrated ArcFace threshold: 0.45 (45.0% cosine similarity) for high-confidence biometric authorization.
"""

import logging
import os
import pickle
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("workplace_intelligence.biometric_registry")

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "mock_employee_db.pkl"


class BiometricRegistry:
    """Thread-safe, in-memory repository for ArcFace 512-dimensional facial embeddings."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self._lock = threading.RLock()
        self._db: Dict[str, Dict[str, Any]] = {}
        self._id_list: List[str] = []
        self._embedding_matrix: Optional[np.ndarray] = None
        self._last_mtime: float = 0.0

        # Initial load into memory
        self.reload()

    def reload(self) -> int:
        """
        Loads embeddings from the pickle database into RAM.
        Pre-computes normalized 512-d unit vectors and builds the search matrix.
        """
        with self._lock:
            if not self.db_path.exists():
                self._db = {}
                self._id_list = []
                self._embedding_matrix = None
                self._last_mtime = 0.0
                return 0

            try:
                mtime = os.path.getmtime(self.db_path)
                with open(self.db_path, "rb") as f:
                    data = pickle.load(f)

                if not isinstance(data, dict):
                    logger.warning(f"Employee db at {self.db_path} is not a dict. Starting fresh.")
                    data = {}

                cleaned_db: Dict[str, Dict[str, Any]] = {}
                ids: List[str] = []
                vectors: List[np.ndarray] = []

                for emp_id, rec in data.items():
                    if not isinstance(rec, dict):
                        continue
                    name = str(rec.get("name", "Unknown")).strip()
                    roll = str(rec.get("roll", "")).strip()
                    raw_emb = rec.get("embedding")
                    if raw_emb is None:
                        continue

                    vec = np.asarray(raw_emb, dtype=np.float32).flatten()
                    if vec.shape != (512,):
                        logger.warning(f"Skipping {emp_id}: invalid embedding shape {vec.shape}")
                        continue

                    # Guarantee unit-norm for cosine similarity
                    norm = np.linalg.norm(vec)
                    unit_vec = (vec / norm) if norm > 0 else vec

                    record = {
                        "employee_id": str(emp_id).strip(),
                        "name": name,
                        "roll": roll,
                        "embedding": unit_vec,
                    }
                    cleaned_db[str(emp_id).strip()] = record
                    ids.append(str(emp_id).strip())
                    vectors.append(unit_vec)

                self._db = cleaned_db
                self._id_list = ids
                if vectors:
                    self._embedding_matrix = np.vstack(vectors).astype(np.float32)
                else:
                    self._embedding_matrix = None

                self._last_mtime = mtime
                logger.info(
                    f"BiometricRegistry: Loaded {len(self._db)} enrolled personnel embeddings into memory."
                )
                return len(self._db)
            except Exception as e:
                logger.error(f"BiometricRegistry reload error: {e}")
                return len(self._db)

    def _ensure_fresh(self) -> None:
        """Checks if the backing pickle file has changed on disk; reloads if so."""
        if not self.db_path.exists():
            return
        try:
            mtime = os.path.getmtime(self.db_path)
            if mtime > self._last_mtime:
                self.reload()
        except OSError:
            pass

    @staticmethod
    def normalize_vector(vec: np.ndarray) -> np.ndarray:
        """Converts vector to a 512-d float32 unit-norm array."""
        v = np.asarray(vec, dtype=np.float32).flatten()
        norm = np.linalg.norm(v)
        return (v / norm) if norm > 0 else v

    @staticmethod
    def compute_cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Computes cosine similarity between two 512-d feature vectors, clipped to [0, 1]."""
        v1 = BiometricRegistry.normalize_vector(vec1)
        v2 = BiometricRegistry.normalize_vector(vec2)
        dot = float(np.dot(v1, v2))
        return float(np.clip(dot, 0.0, 1.0))

    def get_employee(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Flexible personnel profile lookup.
        Matches exact ID, case-insensitive ID, roll number, or personnel name.
        """
        self._ensure_fresh()
        with self._lock:
            q = query.strip()
            if not q:
                return None

            # 1. Exact match on ID
            if q in self._db:
                return self._db[q]

            # 2. Case-insensitive ID match
            q_upper = q.upper()
            for emp_id, rec in self._db.items():
                if emp_id.upper() == q_upper:
                    return rec

            # 3. Numeric badge suffix (e.g. '1234' matches 'EMP-1234')
            for emp_id, rec in self._db.items():
                suffix = emp_id.split("-")[-1] if "-" in emp_id else emp_id
                if suffix == q or suffix.upper() == q_upper:
                    return rec

            # 4. Roll number match
            for rec in self._db.values():
                if rec.get("roll", "").upper() == q_upper:
                    return rec

            # 5. Full name match
            for rec in self._db.values():
                if rec.get("name", "").upper() == q_upper:
                    return rec

            return None

    def find_best_match(
        self, live_embedding: np.ndarray, threshold: float = 0.45
    ) -> Tuple[Optional[Dict[str, Any]], float, List[Dict[str, Any]]]:
        """
        1:N Biometric Vector Retrieval:
        Compares live 512-d embedding against all enrolled profiles in memory.
        Returns:
            (best_record, best_similarity, ranked_candidates)
        """
        self._ensure_fresh()
        with self._lock:
            if self._embedding_matrix is None or len(self._id_list) == 0:
                return None, 0.0, []

            query_vec = self.normalize_vector(live_embedding)
            # 1-to-N cosine similarity via matrix-vector product
            sims = np.dot(self._embedding_matrix, query_vec)
            sims = np.clip(sims, 0.0, 1.0)

            ranked_indices = np.argsort(-sims)
            candidates: List[Dict[str, Any]] = []

            for idx in ranked_indices:
                emp_id = self._id_list[idx]
                score = float(sims[idx])
                rec = self._db.get(emp_id, {})
                candidates.append({
                    "employee_id": emp_id,
                    "name": rec.get("name", "Unknown"),
                    "roll": rec.get("roll", ""),
                    "score": round(score, 4),
                    "score_pct": round(score * 100, 1),
                })

            top_idx = int(ranked_indices[0])
            best_score = float(sims[top_idx])
            best_id = self._id_list[top_idx]
            best_record = self._db.get(best_id)

            return best_record, best_score, candidates

    def verify_or_identify(
        self,
        live_embedding: np.ndarray,
        employee_id: Optional[str] = None,
        threshold: float = 0.45,
    ) -> Dict[str, Any]:
        """
        Comprehensive Biometric Recognition Retrieval:
        - If employee_id is specified and registered, verifies 1:1 against the credential.
        - If employee_id is missing, unknown, 'AUTO', or mismatch, checks 1:N in-memory retrieval.
        - Returns structured verification telemetry.
        """
        self._ensure_fresh()
        with self._lock:
            total_enrolled = len(self._db)
            if total_enrolled == 0:
                return {
                    "status": "MISMATCH",
                    "match_score": 0.0,
                    "raw_score": 0.0,
                    "employee_id": employee_id or "UNKNOWN",
                    "employee_name": "No Enrolled Personnel",
                    "roll": "",
                    "is_authorized": False,
                    "auto_identified": False,
                    "detail": "Biometric database is empty. Please enroll personnel first.",
                    "total_enrolled": 0,
                    "candidates": [],
                }

            best_record, best_score, candidates = self.find_best_match(
                live_embedding, threshold=threshold
            )

            # Check if a specific target credential was requested
            req_emp = None
            if employee_id:
                req_emp = self.get_employee(employee_id)

            # -------------------------------------------------------------
            # Case 1: Specific registered credential requested
            # -------------------------------------------------------------
            if req_emp is not None:
                target_id = req_emp["employee_id"]
                target_name = req_emp["name"]
                target_roll = req_emp.get("roll", "")
                enrolled_vec = req_emp["embedding"]

                cred_similarity = self.compute_cosine_similarity(live_embedding, enrolled_vec)
                cred_score_pct = round(cred_similarity * 100, 1)

                if cred_similarity >= threshold:
                    return {
                        "status": "AUTHORIZED",
                        "match_score": cred_score_pct,
                        "raw_score": round(cred_similarity, 4),
                        "employee_id": target_id,
                        "employee_name": target_name,
                        "roll": target_roll,
                        "is_authorized": True,
                        "auto_identified": False,
                        "detail": f"Biometric verification successful: {cred_score_pct}% match against {target_id} ({target_name}).",
                        "total_enrolled": total_enrolled,
                        "candidates": candidates[:3],
                    }
                else:
                    # Mismatch with specified badge. Check if someone else was recognized
                    alt_info = ""
                    if best_record and best_score >= threshold and best_record["employee_id"] != target_id:
                        alt_info = f" Live subject matched {best_record['employee_id']} ({best_record['name']}) with {round(best_score * 100, 1)}% similarity."

                    return {
                        "status": "MISMATCH",
                        "match_score": cred_score_pct,
                        "raw_score": round(cred_similarity, 4),
                        "employee_id": target_id,
                        "employee_name": target_name,
                        "roll": target_roll,
                        "is_authorized": False,
                        "auto_identified": False,
                        "detail": f"Biometric mismatch: Scanned badge {target_id} scored {cred_score_pct}% (threshold: {round(threshold * 100, 1)}%).{alt_info}",
                        "total_enrolled": total_enrolled,
                        "candidates": candidates[:3],
                    }

            # -------------------------------------------------------------
            # Case 2: Auto-identification / 1:N retrieval (Badge not specified or not found)
            # -------------------------------------------------------------
            if best_record and best_score >= threshold:
                matched_id = best_record["employee_id"]
                matched_name = best_record["name"]
                matched_roll = best_record.get("roll", "")
                score_pct = round(best_score * 100, 1)

                return {
                    "status": "AUTHORIZED",
                    "match_score": score_pct,
                    "raw_score": round(best_score, 4),
                    "employee_id": matched_id,
                    "employee_name": matched_name,
                    "roll": matched_roll,
                    "is_authorized": True,
                    "auto_identified": True,
                    "detail": f"Biometric 1:N retrieval recognized {matched_id} ({matched_name}) with {score_pct}% similarity.",
                    "total_enrolled": total_enrolled,
                    "candidates": candidates[:3],
                }

            # No registered face reached the recognition threshold
            top_score_pct = round(best_score * 100, 1) if best_record else 0.0
            return {
                "status": "MISMATCH",
                "match_score": top_score_pct,
                "raw_score": round(best_score, 4) if best_record else 0.0,
                "employee_id": employee_id or "UNRECOGNIZED",
                "employee_name": "Unrecognized Subject",
                "roll": "",
                "is_authorized": False,
                "auto_identified": False,
                "detail": f"Unrecognized personnel: Highest candidate match scored {top_score_pct}% (threshold: {round(threshold * 100, 1)}%).",
                "total_enrolled": total_enrolled,
                "candidates": candidates[:3],
            }

    def enroll(
        self,
        employee_id: str,
        name: str,
        roll: str,
        embedding: np.ndarray,
    ) -> Dict[str, Any]:
        """
        Appends or updates personnel in the in-memory cache and non-destructively persists to disk.
        """
        with self._lock:
            emp_id = str(employee_id).strip()
            full_name = str(name).strip()
            roll_num = str(roll).strip()
            unit_vec = self.normalize_vector(embedding)

            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Load latest disk state first to avoid overwriting outside writes
            disk_db: Dict[str, Any] = {}
            if self.db_path.exists():
                try:
                    with open(self.db_path, "rb") as f:
                        loaded = pickle.load(f)
                        if isinstance(loaded, dict):
                            disk_db = loaded
                except Exception as e:
                    logger.warning(f"Could not load existing db on enrollment: {e}")

            disk_db[emp_id] = {
                "name": full_name,
                "roll": roll_num,
                "embedding": unit_vec,
            }

            # Save to disk
            with open(self.db_path, "wb") as f:
                pickle.dump(disk_db, f)

            # Refresh in-memory registry
            self.reload()

            logger.info(f"BiometricRegistry: Enrolled {full_name} under {emp_id} (RAM cache updated).")
            return {
                "employee_id": emp_id,
                "name": full_name,
                "roll": roll_num,
                "total_enrolled": len(self._db),
            }

    def list_enrolled(self) -> List[Dict[str, Any]]:
        """Returns clean list of all enrolled personnel in memory (omitting raw float vectors)."""
        self._ensure_fresh()
        with self._lock:
            results = []
            for emp_id, rec in self._db.items():
                results.append({
                    "employee_id": emp_id,
                    "name": rec.get("name", "Unknown"),
                    "roll": rec.get("roll", ""),
                })
            return sorted(results, key=lambda x: x["employee_id"])


# Global singleton instance
biometric_registry = BiometricRegistry()
