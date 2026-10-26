"""Google Authenticator TOTP (RFC 6238) Engine for SuperAdmin Audit Export.

Provides 30-second rolling code generation, provisioning URI / QR code generation,
and drift-tolerant verification for Zero-Trust SuperAdmin authorization.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pyotp
import qrcode

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
TOTP_FILE = DATA_DIR / "totp_secrets.json"
ISSUER_NAME = "UATU Security"


class TOTPEngine:
    """Thread-safe singleton managing TOTP secrets and QR pairing."""

    _instance: Optional["TOTPEngine"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "TOTPEngine":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._store_lock = threading.RLock()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._secrets: Dict[str, Dict[str, Any]] = {}
        self._load_secrets()
        self._initialized = True
        logger.info("TOTPEngine initialized with RFC 6238 30-second rolling code support.")

    def _load_secrets(self) -> None:
        with self._store_lock:
            if TOTP_FILE.exists():
                try:
                    with open(TOTP_FILE, "r", encoding="utf-8") as f:
                        self._secrets = json.load(f)
                        return
                except Exception as e:
                    logger.warning(f"Failed to load {TOTP_FILE}: {e}")

            # Pre-seed default SuperAdmin secret so demo runs out of the box if needed
            default_user = "superadmin@uatu.security"
            self._secrets = {
                default_user: {
                    "username": default_user,
                    "secret": pyotp.random_base32(),
                    "configured": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            }
            self._save_secrets_unlocked()

    def _save_secrets_unlocked(self) -> None:
        try:
            with open(TOTP_FILE, "w", encoding="utf-8") as f:
                json.dump(self._secrets, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist TOTP secrets: {e}")

    def get_or_create_secret(self, username: str) -> Tuple[str, bool]:
        """Return (base32_secret, is_configured) for the specified username."""
        with self._store_lock:
            entry = self._secrets.get(username)
            if not entry or not entry.get("secret"):
                secret = pyotp.random_base32()
                self._secrets[username] = {
                    "username": username,
                    "secret": secret,
                    "configured": False,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                self._save_secrets_unlocked()
                return secret, False
            return entry["secret"], bool(entry.get("configured", False))

    def get_setup_payload(self, username: str) -> Dict[str, Any]:
        """Generate base32 secret, provisioning URI, and Base64 PNG QR code data URL."""
        with self._store_lock:
            secret, configured = self.get_or_create_secret(username)
            totp = pyotp.TOTP(secret)
            uri = totp.provisioning_uri(name=username, issuer_name=ISSUER_NAME)

            # Generate PNG QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=8,
                border=2,
            )
            qr.add_data(uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            data_url = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"

            return {
                "username": username,
                "secret": secret,
                "provisioning_uri": uri,
                "qr_code_data_url": data_url,
                "issuer": ISSUER_NAME,
                "configured": configured,
                "current_demo_code": totp.now(),
            }

    def verify_code(self, username: str, code: str, valid_window: int = 1) -> bool:
        """Validate a 6-digit TOTP rolling code with 30s drift tolerance (valid_window=1)."""
        clean_code = str(code).strip().replace(" ", "").replace("-", "")
        if not clean_code or len(clean_code) != 6 or not clean_code.isdigit():
            return False

        with self._store_lock:
            entry = self._secrets.get(username)
            if not entry or not entry.get("secret"):
                return False

            totp = pyotp.TOTP(entry["secret"])
            is_valid = totp.verify(clean_code, valid_window=valid_window)
            if is_valid:
                if not entry.get("configured"):
                    entry["configured"] = True
                    entry["paired_at"] = datetime.now(timezone.utc).isoformat()
                    self._save_secrets_unlocked()
            return bool(is_valid)

    def mark_configured(self, username: str) -> None:
        """Mark pairing as confirmed."""
        with self._store_lock:
            if username in self._secrets:
                self._secrets[username]["configured"] = True
                entry = self._secrets[username]
                entry["paired_at"] = datetime.now(timezone.utc).isoformat()
                self._save_secrets_unlocked()

    def reset_secret(self, username: str) -> Dict[str, Any]:
        """Regenerate secret for re-pairing and return new setup payload."""
        with self._store_lock:
            new_secret = pyotp.random_base32()
            self._secrets[username] = {
                "username": username,
                "secret": new_secret,
                "configured": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self._save_secrets_unlocked()
        return self.get_setup_payload(username)

    def get_current_code(self, username: str) -> Optional[str]:
        """Get current 30s code (useful for test/demo mode)."""
        with self._store_lock:
            entry = self._secrets.get(username)
            if entry and entry.get("secret"):
                return pyotp.TOTP(entry["secret"]).now()
            return None


totp_engine = TOTPEngine()
