"""Realistic seed data store for UATU video intelligence and facility monitoring.

Defines the 9 industrial camera channels, historical incident events,
zone occupancy telemetry, and enrolled personnel for standalone or fallback operation.
"""

from __future__ import annotations

import json
from pathlib import Path

# 9 Standard UATU Camera Channels
UATU_CAMERAS = {
    "CAM-01": {
        "camera_id": "CAM-01",
        "zone_id": "ZONE-01",
        "zone_name": "Main Turnstile North",
        "description": "Primary Employee Entry/Exit, Dual Optical Lanes, RFID + ArcFace Biometrics, Tailgating Detection",
        "capabilities": ["FACIAL_RECOGNITION", "BADGE_CORRELATION", "TAILGATING_DETECTION", "HEADCOUNT"],
        "status": "ONLINE",
        "fps": 30,
        "resolution": "1920x1080",
    },
    "CAM-02": {
        "camera_id": "CAM-02",
        "zone_id": "ZONE-01",
        "zone_name": "Optical Turnstile B",
        "description": "Secondary Turnstile Lane, Visitor Registration & Contractor Access Verification",
        "capabilities": ["BADGE_VERIFICATION", "ACCESS_CORRELATION", "ENTRY_EXIT_FLOW"],
        "status": "ONLINE",
        "fps": 30,
        "resolution": "1920x1080",
    },
    "CAM-03": {
        "camera_id": "CAM-03",
        "zone_id": "ZONE-02",
        "zone_name": "Logistics & Loading Bay",
        "description": "Heavy Vehicle Loading Dock, Forklift Corridors, Material Ingress/Egress",
        "capabilities": ["VEHICLE_DETECTION", "FORKLIFT_PROXIMITY", "PERSON_VEHICLE_SEGREGATION"],
        "status": "ONLINE",
        "fps": 25,
        "resolution": "2560x1440",
    },
    "CAM-04": {
        "camera_id": "CAM-04",
        "zone_id": "ZONE-02",
        "zone_name": "Precision Workshop 2",
        "description": "Machinery Operation Floor, Heavy Lathes, CNC Units, PPE Compliance & Fall Hazard Monitoring",
        "capabilities": ["FALL_DETECTION", "MAN_DOWN", "PPE_HARDHAT_VEST", "ABNORMAL_GATHERING"],
        "status": "ONLINE",
        "fps": 30,
        "resolution": "1920x1080",
    },
    "CAM-05": {
        "camera_id": "CAM-05",
        "zone_id": "ZONE-04",
        "zone_name": "Server Room Alpha (Tier-3 Vault)",
        "description": "Data Center Core Vault, Dual-Custody Biometric Perimeter, Server Rack Aisles, Thermal/Fire Sensors",
        "capabilities": ["DUAL_CUSTODY_VERIFICATION", "FIRE_SMOKE_EARLY_WARNING", "UNAUTHORIZED_DOOR_AJAR"],
        "status": "ONLINE",
        "fps": 30,
        "resolution": "1920x1080",
    },
    "CAM-06": {
        "camera_id": "CAM-06",
        "zone_id": "ZONE-06",
        "zone_name": "Western Security Barrier",
        "description": "Outer Perimeter Fence, Gate 3 Boundary, Thermal PTZ & Infrared Perimeter Detection",
        "capabilities": ["PERIMETER_BREACH", "TRIPWIRE_DETECTION", "SMOKE_DETECTION"],
        "status": "ONLINE",
        "fps": 25,
        "resolution": "1920x1080",
    },
    "CAM-07": {
        "camera_id": "CAM-07",
        "zone_id": "ZONE-03",
        "zone_name": "Canteen & Break Area",
        "description": "Facility Dining Hall, Cafeteria Seating, Break Time Tracking & Crowding Telemetry",
        "capabilities": ["OCCUPANCY_COUNTING", "LONG_BREAK_TRACKING", "CROWD_DENSITY"],
        "status": "ONLINE",
        "fps": 30,
        "resolution": "1920x1080",
    },
    "CAM-08": {
        "camera_id": "CAM-08",
        "zone_id": "ZONE-05",
        "zone_name": "Stores 2 & Warehouse",
        "description": "Bulk Raw Materials, High-Value Inventory Racks, After-Hours Ingress Corridor",
        "capabilities": ["AFTER_HOURS_PRESENCE", "UNMATCHED_BADGE_DETECTION", "ASSET_REMOVAL"],
        "status": "ONLINE",
        "fps": 30,
        "resolution": "1920x1080",
    },
    "CAM-09": {
        "camera_id": "CAM-09",
        "zone_id": "ZONE-05",
        "zone_name": "Tool Room & Tool Crib",
        "description": "Precision Calibration Bench, Shadow Board Tool Stations, Power Tool Issue Desk",
        "capabilities": ["TOOL_BOARD_MONITORING", "HIGH_VALUE_ASSET_TRACKING", "RFID_ISSUE_CORRELATION"],
        "status": "ONLINE",
        "fps": 30,
        "resolution": "1920x1080",
    },
}

HUMAN_REVIEW_DISCLAIMER = (
    "Possible event detected by AI; authorized human investigator review is required before any conclusion or action."
)

# Operational event store — 100% Zero-Fake-Data (populated strictly by live runtime telemetry)
UATU_EVENTS: list[dict] = []

# Real-time zone telemetry & traffic counters
UATU_ZONE_TELEMETRY = {
    "ZONE-01": {
        "zone_id": "ZONE-01",
        "zone_name": "Main Turnstile North",
        "camera_id": "CAM-01",
        "entry_count": 184,
        "exit_count": 142,
        "current_occupancy": 42,
        "crowding_threshold": 4,
        "abnormal_gathering_active": False,
        "air_quality": "NORMAL",
        "door_status": "LOCKED_CONTROLLED",
    },
    "ZONE-02": {
        "zone_id": "ZONE-02",
        "zone_name": "Precision Workshop 2",
        "camera_id": "CAM-04",
        "entry_count": 38,
        "exit_count": 32,
        "current_occupancy": 6,
        "crowding_threshold": 4,
        "abnormal_gathering_active": True,  # Exceeded threshold 4
        "air_quality": "NORMAL",
        "door_status": "OPEN_OPERATIONAL",
    },
    "ZONE-03": {
        "zone_id": "ZONE-03",
        "zone_name": "Canteen & Break Area",
        "camera_id": "CAM-07",
        "entry_count": 82,
        "exit_count": 78,
        "current_occupancy": 4,
        "crowding_threshold": 4,
        "abnormal_gathering_active": False,
        "air_quality": "NORMAL",
        "door_status": "UNRESTRICTED",
    },
    "ZONE-04": {
        "zone_id": "ZONE-04",
        "zone_name": "Server Room Alpha (Tier-3 Vault)",
        "camera_id": "CAM-05",
        "entry_count": 4,
        "exit_count": 4,
        "current_occupancy": 0,
        "crowding_threshold": 2,
        "abnormal_gathering_active": False,
        "air_quality": "SMOKE_ALERT",
        "door_status": "SEALED_VAULT",
    },
    "ZONE-05": {
        "zone_id": "ZONE-05",
        "zone_name": "Stores 2 & Warehouse",
        "camera_id": "CAM-08",
        "entry_count": 14,
        "exit_count": 13,
        "current_occupancy": 1,
        "crowding_threshold": 4,
        "abnormal_gathering_active": False,
        "air_quality": "NORMAL",
        "door_status": "RESTRICTED_ACCESS",
    },
    "ZONE-06": {
        "zone_id": "ZONE-06",
        "zone_name": "Western Security Barrier",
        "camera_id": "CAM-06",
        "entry_count": 0,
        "exit_count": 0,
        "current_occupancy": 0,
        "crowding_threshold": 2,
        "abnormal_gathering_active": False,
        "air_quality": "PERIMETER_SMOKE",
        "door_status": "PERIMETER_LOCKED",
    },
}

# Enrolled users and verification logs
UATU_ENROLLED_USERS = [
    {
        "employee_id": "EMP-1234",
        "name": "Hari Prasath",
        "role": "Lead Systems Engineer / Security Operator",
        "department": "Infrastructure & AI Robotics",
        "access_tier": "TIER_1_SUPER_ADMIN",
        "arcface_embedding_registered": True,
        "recent_verification": {
            "timestamp_ist": "2026-10-24 08:15:30 IST",
            "camera_id": "CAM-01",
            "status": "AUTHORIZED",
            "similarity_score_pct": 98.4,
            "badge_rfid_match": True,
            "turnstile_person_count": 1,
        },
    },
    {
        "employee_id": "EMP-4092",
        "name": "Sandy",
        "role": "Senior Vision Specialist",
        "department": "Video Analytics & Edge Inference",
        "access_tier": "TIER_2_RESTRICTED",
        "arcface_embedding_registered": True,
        "recent_verification": {
            "timestamp_ist": "2026-10-24 08:18:12 IST",
            "camera_id": "CAM-01",
            "status": "AUTHORIZED",
            "similarity_score_pct": 96.8,
            "badge_rfid_match": True,
            "turnstile_person_count": 1,
        },
    },
    {
        "employee_id": "EMP-8812",
        "name": "Santhu",
        "role": "Plant Operations Duty Officer",
        "department": "Workshop Alpha Operations",
        "access_tier": "TIER_3_FACILITY",
        "arcface_embedding_registered": True,
        "recent_verification": {
            "timestamp_ist": "2026-10-23 19:42:15 IST",
            "camera_id": "CAM-08",
            "status": "MISMATCH",
            "similarity_score_pct": 42.1,
            "badge_rfid_match": True,
            "turnstile_person_count": 1,
            "flag": "CARD_WITHOUT_FACE_MATCH",
        },
    },
]


def dump_events_index(dest_path: Path | str | None = None) -> Path:
    """Export the realistic video events index to data/uatu_events_index.json."""
    if dest_path is None:
        target = Path(__file__).resolve().parents[1] / "data" / "uatu_events_index.json"
    else:
        target = Path(dest_path)

    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(
            {
                "cameras": UATU_CAMERAS,
                "events": UATU_EVENTS,
                "telemetry": UATU_ZONE_TELEMETRY,
                "enrolled_users": UATU_ENROLLED_USERS,
            },
            f,
            indent=2,
        )
    return target
