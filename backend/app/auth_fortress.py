"""Fortress Zero-Trust Authentication & Contextual OTP Engine.

Provides SuperAdmin credential verification, cryptographically bound 6-digit OTPs,
device/network fingerprinting, and Trust Score evaluation for audit log export.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
CREDENTIALS_FILE = DATA_DIR / "fortress_credentials.json"

# Trust Score Threshold
TRUST_SCORE_PASS_THRESHOLD = 80
OTP_VALIDITY_SECONDS = 300  # 5 minutes


def _hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hash a password using PBKDF2-HMAC-SHA256 with 100,000 iterations."""
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return key.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify password against stored hash in constant time."""
    computed_key, _ = _hash_password(password, salt)
    return secrets.compare_digest(computed_key, stored_hash)


def compute_device_fingerprint(
    user_agent: str, accept_language: str = "en-US", tz: str = "UTC"
) -> str:
    """Compute SHA-256 fingerprint hash from device context."""
    raw = f"{user_agent.strip()}|{accept_language.strip()}|{tz.strip()}".lower()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_subnet_prefix(ip_str: str) -> str:
    """Extract /24 (IPv4) or /48 (IPv6) subnet prefix for network consistency checks."""
    try:
        ip = ipaddress.ip_address(ip_str.strip())
        if ip.version == 4:
            net = ipaddress.ip_network(f"{ip}/24", strict=False)
            return str(net.network_address)
        else:
            net = ipaddress.ip_network(f"{ip}/48", strict=False)
            return str(net.network_address)
    except Exception:
        return ip_str.strip()


class FortressEngine:
    """Zero-Trust SuperAdmin verification, contextual OTP dispatch, and Trust Score validator."""

    _instance: Optional["FortressEngine"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "FortressEngine":
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

        # In-memory stores
        self._superadmins: Dict[str, Dict[str, Any]] = {}
        self._active_otps: Dict[str, Dict[str, Any]] = {}  # session_token -> OTP details
        self._temp_tickets: Dict[str, Dict[str, Any]] = {}  # ticket -> credential session

        self._init_default_credentials()
        self._initialized = True
        logger.info("FortressEngine initialized with Zero-Trust OTP verification.")

    def _init_default_credentials(self) -> None:
        """Seed default SuperAdmin accounts if credentials file does not exist."""
        with self._store_lock:
            if CREDENTIALS_FILE.exists():
                try:
                    with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                        self._superadmins = json.load(f)
                        return
                except Exception as e:
                    logger.warning(f"Could not load {CREDENTIALS_FILE}: {e}")

            # Defaults:
            # 1. superadmin@uatu.security / SuperAdmin@2026!
            # 2. admin / UatuAdmin#2026
            h1, s1 = _hash_password("SuperAdmin@2026!")
            h2, s2 = _hash_password("UatuAdmin#2026")

            self._superadmins = {
                "superadmin@uatu.security": {
                    "username": "superadmin@uatu.security",
                    "display_name": "Chief Security Architect (SuperAdmin)",
                    "role": "SUPERADMIN",
                    "hash": h1,
                    "salt": s1,
                    "created_at": datetime.now(UTC).isoformat(),
                },
                "admin": {
                    "username": "admin",
                    "display_name": "System Administrator",
                    "role": "SUPERADMIN",
                    "hash": h2,
                    "salt": s2,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            }

            try:
                with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
                    json.dump(self._superadmins, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to persist {CREDENTIALS_FILE}: {e}")

    def verify_superadmin_credentials(
        self, username_or_email: str, password: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Verify username/email and password against stored SuperAdmin hashes."""
        clean_user = username_or_email.strip().lower()
        with self._store_lock:
            target = None
            for key, user in self._superadmins.items():
                if key.lower() == clean_user or user.get("username", "").lower() == clean_user:
                    target = user
                    break

            if not target:
                return False, "Invalid SuperAdmin username or email.", None

            stored_hash = target.get("hash", "")
            salt = target.get("salt", "")
            if not _verify_password(password, stored_hash, salt):
                return False, "Invalid password credentials.", None

            # Generate temporary pre-OTP session ticket valid for 10 minutes
            ticket = f"TKT-{secrets.token_urlsafe(24)}"
            self._temp_tickets[ticket] = {
                "username": target["username"],
                "display_name": target.get("display_name", "SuperAdmin"),
                "role": target.get("role", "SUPERADMIN"),
                "created_at": time.time(),
                "expires_at": time.time() + 600,
            }

            return True, None, {
                "ticket": ticket,
                "username": target["username"],
                "display_name": target.get("display_name", "SuperAdmin"),
            }

    def request_fortress_otp(
        self,
        ticket: str,
        client_ip: str,
        user_agent: str,
        accept_language: str = "en-US",
        timezone_str: str = "Asia/Kolkata",
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Generate and cryptographically bind a 6-digit OTP to IP, subnet, and device fingerprint."""
        with self._store_lock:
            ticket_data = self._temp_tickets.get(ticket)
            if not ticket_data:
                return False, "Invalid or expired authorization ticket. Please authenticate again.", None

            if time.time() > ticket_data.get("expires_at", 0):
                self._temp_tickets.pop(ticket, None)
                return False, "Session ticket has expired. Please authenticate again.", None

            # Generate random 6-digit numeric OTP (e.g. "847291")
            otp_code = f"{secrets.randbelow(900000) + 100000}"
            session_id = f"FTS-{secrets.token_hex(16)}"

            device_fp = compute_device_fingerprint(user_agent, accept_language, timezone_str)
            subnet = get_subnet_prefix(client_ip)

            otp_record = {
                "session_id": session_id,
                "username": ticket_data["username"],
                "display_name": ticket_data["display_name"],
                "otp_code": otp_code,
                "bound_ip": client_ip,
                "bound_subnet": subnet,
                "bound_fingerprint": device_fp,
                "user_agent": user_agent,
                "accept_language": accept_language,
                "timezone": timezone_str,
                "issued_at": time.time(),
                "expires_at": time.time() + OTP_VALIDITY_SECONDS,
                "failed_attempts": 0,
            }

            self._active_otps[session_id] = otp_record

            logger.info(
                f"Fortress OTP dispatched for {ticket_data['username']} [Session: {session_id}]. Code: {otp_code} (Expires in 300s)"
            )

            # Masked OTP display for security demonstration (e.g. "84****")
            masked_otp = f"{otp_code[:2]}****"

            return True, None, {
                "session_id": session_id,
                "username": ticket_data["username"],
                "expires_in_seconds": OTP_VALIDITY_SECONDS,
                "masked_otp": masked_otp,
                # In development/hackathon demo mode, we expose the OTP in response for testing convenience:
                "demo_otp_hint": otp_code,
                "bound_subnet": subnet,
                "device_fingerprint_short": device_fp[:12],
            }

    def evaluate_trust_score(
        self,
        otp_record: Dict[str, Any],
        presented_ip: str,
        presented_ua: str,
        presented_lang: str,
        presented_tz: str,
        simulate_hacker: bool = False,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Evaluate Trust Score (0-100) based on contextual security telemetry.
        Target threshold >= 80 to pass.
        """
        score = 100
        breakdown: List[Dict[str, Any]] = []

        # 1. Subnet & Network Check (Weight: 30)
        presented_subnet = get_subnet_prefix(presented_ip)
        if presented_subnet == otp_record["bound_subnet"]:
            breakdown.append({
                "factor": "Network Subnet Consistency",
                "status": "PASS",
                "delta": 0,
                "detail": f"Matched issuing subnet ({presented_subnet})",
            })
        else:
            score -= 30
            breakdown.append({
                "factor": "Network Subnet Consistency",
                "status": "FAIL",
                "delta": -30,
                "detail": f"Subnet mismatch (Bound: {otp_record['bound_subnet']}, Presented: {presented_subnet})",
            })

        # 2. Device Fingerprint Check (Weight: 40)
        presented_fp = compute_device_fingerprint(presented_ua, presented_lang, presented_tz)
        if secrets.compare_digest(presented_fp, otp_record["bound_fingerprint"]):
            breakdown.append({
                "factor": "Device Cryptographic Fingerprint",
                "status": "PASS",
                "delta": 0,
                "detail": f"Matched client device fingerprint ({presented_fp[:10]}...)",
            })
        else:
            score -= 40
            breakdown.append({
                "factor": "Device Cryptographic Fingerprint",
                "status": "FAIL",
                "delta": -40,
                "detail": "Device fingerprint mismatch (User-Agent or Timezone altered)",
            })

        # 3. Failed Attempts Penalty (10 pts per failure)
        failures = otp_record.get("failed_attempts", 0)
        if failures > 0:
            penalty = min(30, failures * 10)
            score -= penalty
            breakdown.append({
                "factor": "Authentication Retries Penalty",
                "status": "WARN",
                "delta": -penalty,
                "detail": f"{failures} prior failed attempt(s) recorded",
            })

        # 4. Hackathon Demo Mode: Artificial Zero-Trust Security Breach Simulation
        if simulate_hacker:
            score -= 55
            breakdown.append({
                "factor": "Zero-Trust Threat Simulator (Demo Mode)",
                "status": "BREACH",
                "delta": -55,
                "detail": "Simulated Session Hijacking / MITM Proxy / Rogue Device Signature detected",
            })

        clamped_score = max(0, min(100, score))
        return clamped_score, breakdown

    def verify_and_authorize_export(
        self,
        session_id: str,
        presented_otp: str,
        client_ip: str,
        user_agent: str,
        accept_language: str = "en-US",
        timezone_str: str = "Asia/Kolkata",
        simulate_hacker: bool = False,
    ) -> Tuple[bool, int, List[Dict[str, Any]], Optional[str], Optional[Dict[str, Any]]]:
        """
        Verify OTP code and evaluate Trust Score against threshold >= 80.
        Returns: (is_authorized, trust_score, breakdown, error_message, context)
        """
        with self._store_lock:
            otp_record = self._active_otps.get(session_id)
            if not otp_record:
                return (
                    False,
                    0,
                    [{"factor": "Session Validity", "status": "FAIL", "delta": -100, "detail": "Invalid or expired Fortress session."}],
                    "Invalid or expired Fortress session. Please request a new OTP.",
                    None,
                )

            # Check expiration
            if time.time() > otp_record["expires_at"]:
                self._active_otps.pop(session_id, None)
                return (
                    False,
                    0,
                    [{"factor": "Time-to-Live Expiry", "status": "FAIL", "delta": -100, "detail": "OTP validity window (300s) has expired."}],
                    "The OTP has expired. Please request a fresh OTP.",
                    None,
                )

            # Evaluate Trust Score
            trust_score, breakdown = self.evaluate_trust_score(
                otp_record=otp_record,
                presented_ip=client_ip,
                presented_ua=user_agent,
                presented_lang=accept_language,
                presented_tz=timezone_str,
                simulate_hacker=simulate_hacker,
            )

            # Verify OTP Code
            clean_otp = presented_otp.strip()
            if not secrets.compare_digest(clean_otp, otp_record["otp_code"]):
                otp_record["failed_attempts"] += 1
                return (
                    False,
                    max(0, trust_score - 10),
                    breakdown,
                    "Invalid 6-digit OTP code.",
                    {"username": otp_record["username"], "failed_attempts": otp_record["failed_attempts"]},
                )

            # Check Trust Score Threshold >= 80
            if trust_score < TRUST_SCORE_PASS_THRESHOLD:
                return (
                    False,
                    trust_score,
                    breakdown,
                    f"Zero-Trust Security Block: Trust score ({trust_score}/100) below threshold ({TRUST_SCORE_PASS_THRESHOLD}/100).",
                    {"username": otp_record["username"], "trust_score": trust_score},
                )

            # Success! Consume the OTP (single use)
            user_info = {
                "username": otp_record["username"],
                "display_name": otp_record["display_name"],
                "authorized_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
                "trust_score": trust_score,
            }
            self._active_otps.pop(session_id, None)

            return True, trust_score, breakdown, None, user_info


# Global Singleton Instance
fortress_engine = FortressEngine()
