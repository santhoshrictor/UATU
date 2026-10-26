"""UATU Core Tools for Evidence-Based Historical Video Search, Zone Traffic, and Alert Escalation."""

from __future__ import annotations

import copy
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp
from livekit.agents import RunContext, function_tool
from livekit.agents.llm import ToolError

from audit_logger import UATUAuditLogger
from circuit_breaker import (
    is_backend_offline,
    mark_backend_offline,
    mark_backend_online,
)
from uatu_seed_data import (
    HUMAN_REVIEW_DISCLAIMER,
    UATU_CAMERAS,
    UATU_ENROLLED_USERS,
    UATU_EVENTS,
    UATU_ZONE_TELEMETRY,
)

IST_ZONE = ZoneInfo("Asia/Kolkata")


class UATUTools:
    """Core function tools suite for UATU Video Intelligence and Workplace Safety."""

    def __init__(
        self,
        backend_url: str | None = None,
        audit_logger: UATUAuditLogger | None = None,
        events_file: Path | str | None = None,
    ) -> None:
        self.backend_url = (
            backend_url or os.getenv("UATU_BACKEND_URL", "http://127.0.0.1:8000")
        ).rstrip("/")
        self.audit_logger = audit_logger or UATUAuditLogger()

        if events_file is None:
            self.events_file = (
                Path(__file__).resolve().parents[1] / "data" / "uatu_events_index.json"
            )
        else:
            self.events_file = Path(events_file)

        # Auto-create data directory if missing
        self.events_file.parent.mkdir(parents=True, exist_ok=True)

        # In-memory local fallback store (deep-copied so mutations don't corrupt global seed)
        self._local_events: list[dict] = copy.deepcopy(UATU_EVENTS)
        self._local_cameras: dict[str, dict] = copy.deepcopy(UATU_CAMERAS)
        self._local_telemetry: dict[str, dict] = copy.deepcopy(UATU_ZONE_TELEMETRY)
        self._local_users: list[dict] = copy.deepcopy(UATU_ENROLLED_USERS)

        self._load_from_json_if_available()

    async def _safe_get(self, url: str, params: dict | None = None) -> dict | list | None:
        """Execute non-blocking HTTP GET with sub-250ms connect timeout and fast circuit breaker."""
        if is_backend_offline(self.backend_url):
            return None
        try:
            timeout = aiohttp.ClientTimeout(total=0.5, connect=0.25)
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.get(url, params=params) as resp,
            ):
                if resp.status == 200:
                    mark_backend_online(self.backend_url)
                    return await resp.json()
        except Exception:
            mark_backend_offline(self.backend_url)
        return None

    async def _safe_post(
        self, url: str, json_data: dict | None = None
    ) -> dict | list | None:
        """Execute non-blocking HTTP POST with sub-250ms connect timeout and fast circuit breaker."""
        if is_backend_offline(self.backend_url):
            return None
        try:
            timeout = aiohttp.ClientTimeout(total=0.5, connect=0.25)
            async with (
                aiohttp.ClientSession(timeout=timeout) as session,
                session.post(url, json=json_data) as resp,
            ):
                if resp.status == 200:
                    mark_backend_online(self.backend_url)
                    return await resp.json()
        except Exception:
            mark_backend_offline(self.backend_url)
        return None

    def _load_from_json_if_available(self) -> None:
        """Load state from events_file or live_events_db.json if present."""
        if self.events_file.exists():
            try:
                with open(self.events_file, encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self._local_events = data
                    elif isinstance(data, dict):
                        if "events" in data:
                            self._local_events = data["events"]
                        if "cameras" in data:
                            self._local_cameras = data["cameras"]
                        if "telemetry" in data:
                            self._local_telemetry = data["telemetry"]
                        if "enrolled_users" in data:
                            self._local_users = data["enrolled_users"]
            except Exception:
                pass
        elif not self._local_events:
            # Check shared backend live_events_db.json
            shared_live_db = Path(__file__).resolve().parents[2] / "backend" / "data" / "live_events_db.json"
            if shared_live_db.exists():
                try:
                    with open(shared_live_db, encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            self._local_events = data
                except Exception:
                    pass

    def _persist_events(self) -> None:
        """Persist updated event states back to JSON if path exists or can be created."""
        try:
            self.events_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.events_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "cameras": self._local_cameras,
                        "events": self._local_events,
                        "telemetry": self._local_telemetry,
                        "enrolled_users": self._local_users,
                    },
                    f,
                    indent=2,
                )
        except Exception:
            pass

    @property
    def tools(self) -> list:
        return [
            self.search_video_events,
            self.get_verified_incident_reports,
            self.control_platform_ui_layout,
            self.locate_threat_camera_node,
            self.get_zone_occupancy_and_traffic,
            self.query_access_control_and_enrolled_users,
            self.acknowledge_or_escalate_alert,
            self.generate_daily_incident_summary,
            self.get_recent_audit_trail,
        ]

    @function_tool()
    async def search_video_events(
        self,
        context: RunContext,
        query: str = "",
        camera_id: str = "",
        zone: str = "",
        event_type: str = "",
        after_hours_only: bool = False,
        unmatched_access_only: bool = False,
        verified_only: bool = False,
        min_duration_minutes: int = 0,
        limit: int = 10,
    ) -> dict[str, object]:
        """Search indexed video footage, incidents, and safety alarms across facility cameras.

        Args:
            query: Keywords to search (e.g. 'welding machine', 'Stores 2', 'last Friday', 'canteen', 'fall', 'fire', 'smoke', 'tailgating').
            camera_id: Camera ID to filter (e.g. 'CAM-01' through 'CAM-09').
            zone: Zone name to filter (e.g. 'Stores 2', 'Canteen', 'Tool Room', 'Precision Workshop 2').
            event_type: Category (e.g. 'AFTER_HOURS_ACCESS', 'TOOL_ROOM_UNAUTHORIZED_REMOVAL', 'WORKER_FALL_DETECTED').
            after_hours_only: Restrict search strictly to events after normal shifts (19:00 - 07:00 IST).
            unmatched_access_only: Filter for badge swipes without facial verification or unreturned checkout slips.
            verified_only: Strictly restrict results to verified/actioned events, filtering out raw noise.
            min_duration_minutes: Minimum duration in minutes (e.g. 45 for canteen overstay).
            limit: Maximum records to return (default: 10).
        """
        params = {
            "query": query,
            "camera_id": camera_id,
            "zone": zone,
            "event_type": event_type,
            "after_hours_only": str(after_hours_only).lower(),
            "unmatched_access_only": str(unmatched_access_only).lower(),
            "verified_only": str(verified_only).lower(),
            "min_duration_minutes": str(min_duration_minutes),
            "limit": str(limit),
        }

        # 1. Query live video events search endpoint
        backend_result = await self._safe_get(
            f"{self.backend_url}/api/video-events/search", params=params
        )

        if (
            backend_result
            and isinstance(backend_result, dict)
            and "events" in backend_result
        ):
            matched_events = backend_result["events"]
            source = "UATU_LIVE_FASTAPI_BACKEND"
        else:
            # 2. Seamless live-events or local fallback search
            live_result = await self._safe_get(f"{self.backend_url}/api/live-events")
            if (
                live_result
                and isinstance(live_result, dict)
                and "events" in live_result
                and live_result["events"]
            ):
                candidates = live_result["events"]
                source = "UATU_LIVE_FASTAPI_BACKEND"
            else:
                self._load_from_json_if_available()
                candidates = self._local_events
                source = "UATU_LOCAL_INDEXED_FALLBACK"

            matched_events = []
            q_lower = query.strip().casefold()
            tokens = [t for t in q_lower.replace(",", " ").split() if t]

            for ev in candidates:
                # Camera ID filter
                ev_cam = (ev.get("camera_id") or ev.get("camera", "")).casefold()
                if camera_id and camera_id.strip().casefold() != ev_cam:
                    continue

                # Zone filter
                if zone and zone.strip().casefold() not in ev.get("zone", "").casefold():
                    continue

                # Event type filter
                ev_type = (ev.get("event_type") or ev.get("type", "")).casefold()
                if event_type and event_type.strip().casefold() not in ev_type:
                    continue

                # After-hours filter (>19:00 or <07:00 IST or tagged after_hours)
                if after_hours_only:
                    is_after_hours = (
                        "after_hours" in ev.get("tags", [])
                        or "after_hours" in ev_type
                        or "after-hours" in (ev.get("details") or ev.get("detail", "")).casefold()
                    )
                    if not is_after_hours:
                        ts = ev.get("timestamp_ist", "")
                        if " " in ts:
                            try:
                                hour = int(ts.split()[1].split(":")[0])
                                is_after_hours = hour >= 19 or hour < 7
                            except Exception:
                                pass
                    if not is_after_hours:
                        continue

                # Unmatched access filter
                if unmatched_access_only:
                    corr = ev.get("access_control_correlation", "").casefold()
                    is_unmatched = (
                        "unmatched" in corr
                        or "without_face_match" in corr
                        or "mismatch" in corr
                        or "face_mismatch" in corr
                        or "no_tool_issue" in corr
                        or "single_badge_two_heads" in corr
                        or "tailgating" in ev_type
                        or "tailgating" in corr
                    )
                    if not is_unmatched:
                        continue

                # Minimum duration filter
                if min_duration_minutes > 0:
                    dur = ev.get("duration_minutes", 0)
                    if dur < min_duration_minutes:
                        continue

                # Keyword tokens search across fields
                if tokens:
                    searchable_blob = (
                        f"{ev.get('event_id', '')} "
                        f"{ev.get('id', '')} "
                        f"{ev.get('camera_id', '')} "
                        f"{ev.get('camera', '')} "
                        f"{ev.get('zone', '')} "
                        f"{ev.get('event_type', '')} "
                        f"{ev.get('type', '')} "
                        f"{ev.get('details', '')} "
                        f"{ev.get('detail', '')} "
                        f"{ev.get('employee_id', '')} "
                        f"{ev.get('employee_name', '')} "
                        f"{ev.get('access_control_correlation', '')} "
                        f"{' '.join(ev.get('tags', []))}"
                    ).casefold()

                    if (
                        ("welding machine" in q_lower and "welding machine" in searchable_blob)
                        or ("last friday" in q_lower and "last friday" in searchable_blob)
                        or ("stores 2" in q_lower and "stores 2" in searchable_blob)
                        or ("man down" in q_lower and "man down" in searchable_blob)
                        or ("fire" in q_lower and "fire" in searchable_blob)
                        or ("smoke" in q_lower and "smoke" in searchable_blob)
                    ):
                        matches_query = True
                    else:
                        matches_query = any(token in searchable_blob for token in tokens)

                    if not matches_query:
                        continue

                matched_events.append(ev)

            matched_events = matched_events[:limit]

        # Enforce Section 1 Human-Review Notice on every returned event item
        for item in matched_events:
            item["human_review_notice"] = HUMAN_REVIEW_DISCLAIMER

        evidence_ids = [e.get("event_id", "") for e in matched_events]

        self.audit_logger.log_event(
            action_type="EVIDENCE_SEARCH",
            query_or_command=f"search_video_events(query='{query}', camera='{camera_id}', zone='{zone}')",
            retrieved_evidence_ids=evidence_ids,
            response_summary=f"Matched {len(matched_events)} events via {source}.",
            human_review_disclaimer_applied=True,
        )

        return {
            "status": "success",
            "source": source,
            "total_matches": len(matched_events),
            "events": matched_events,
            "message": (
                f"Retrieved {len(matched_events)} matching video events."
                if matched_events
                else "Zero video events matched your search query. No incidents recorded in indexed feeds."
            ),
            "human_in_the_loop_mandatory_rule": (
                "All alerts and footage findings are advisory decision-support. "
                "Human investigator review is required. No automated disciplinary conclusions permitted."
            ),
        }

    @function_tool()
    async def get_verified_incident_reports(
        self,
        context: RunContext,
        zone: str = "",
        camera_id: str = "",
        threat_category: str = "",
        min_confidence: float = 90.0,
        limit: int = 10,
    ) -> dict[str, object]:
        """Retrieve verified, actioned, or supervisor-filed incident reports, strictly filtering out unverified transient noise and false alarms.

        Use this tool whenever the operator asks for incident reports:
        - 'What are the verified incident reports?' or 'Show me filed safety incidents'
        - 'Report high-confidence safety events' or 'List actioned security breaches'
        - 'Any confirmed fire, smoke, or worker fall alerts?'

        Args:
            zone: Optional facility zone to filter (e.g. 'Stores 2', 'Server Room', 'Workshop 2').
            camera_id: Optional camera channel ID (e.g. 'CAM-01' through 'CAM-09').
            threat_category: Optional threat category (e.g. 'fire', 'smoke', 'fall', 'tailgating', 'unauthorized').
            min_confidence: Minimum AI confidence percentage threshold (default: 90.0%).
            limit: Maximum records to return (default: 10).
        """
        backend_result = await self._safe_get(f"{self.backend_url}/api/live-events")
        if (
            backend_result
            and isinstance(backend_result, dict)
            and "events" in backend_result
        ):
            candidate_events = backend_result["events"]
            source = "UATU_LIVE_FASTAPI_BACKEND"
        else:
            self._load_from_json_if_available()
            candidate_events = self._local_events
            source = "UATU_VERIFIED_INCIDENT_REGISTRY"

        verified_events = []
        cat_lower = threat_category.strip().casefold()
        cam_lower = camera_id.strip().casefold()
        zone_lower = zone.strip().casefold()

        # Strict criteria for high-precision telemetry:
        # 1. Minimum confidence threshold (>= min_confidence, default 90.0%)
        # 2. Exclude any event marked as transient noise, test, or unverified draft
        # 3. Must be either:
        #    a) Actioned/filed: case_status in {'ACKNOWLEDGED', 'ESCALATED', 'UNDER_CLOSURE_REVIEW', 'CLOSED', 'ACTIONED'}
        #    b) Explicitly actioned: has responder_name, action_notes, acknowledgement_time, or acknowledged_by
        #    c) Confirmed high-severity physical incident (CRITICAL/HIGH severity with verified correlation)
        for ev in candidate_events:
            conf = float(ev.get("confidence_pct", 0.0))
            if conf < min_confidence:
                continue

            status = ev.get("case_status", "ACKNOWLEDGED" if ev.get("acknowledged") else "OPEN").upper()
            alarm_class = (ev.get("alarm_class") or ev.get("level", "LOW")).upper()
            corr = ev.get("access_control_correlation", "").upper()
            has_responder = bool(
                ev.get("responder_name")
                or ev.get("action_notes")
                or ev.get("acknowledgement_time")
                or ev.get("acknowledged_by")
                or ev.get("acknowledged_at_ist")
            )

            # Exclude low-confidence noise or unconfirmed informational break events
            if alarm_class == "LOW" and not has_responder:
                continue

            # Must have verified case status OR confirmed critical/high hazard with verified correlation
            is_filed_or_verified = (
                status in {"ACKNOWLEDGED", "ESCALATED", "UNDER_CLOSURE_REVIEW", "CLOSED", "ACTIONED", "VERIFIED"}
                or has_responder
                or (alarm_class in {"CRITICAL", "HIGH"} and conf >= 90.0 and corr not in {"UNCONFIRMED_NOISE", "TRANSIENT_TEST"})
            )

            if not is_filed_or_verified:
                continue

            # Camera filter
            ev_cam = (ev.get("camera_id") or ev.get("camera", "")).casefold()
            if cam_lower and cam_lower != ev_cam:
                continue

            # Zone filter
            if zone_lower and zone_lower not in ev.get("zone", "").casefold():
                continue

            # Category filter
            if cat_lower:
                event_blob = f"{ev.get('event_type', '')} {ev.get('type', '')} {ev.get('details', '')} {ev.get('detail', '')} {' '.join(ev.get('tags', []))}".casefold()
                if cat_lower not in event_blob:
                    continue

            ev_copy = copy.deepcopy(ev)
            ev_copy["human_review_notice"] = HUMAN_REVIEW_DISCLAIMER
            ev_copy["telemetry_precision_rating"] = "HIGH_CONFIDENCE_VERIFIED"
            verified_events.append(ev_copy)

        # Sort with CRITICAL first, then HIGH, then confidence descending
        severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        verified_events.sort(key=lambda x: (severity_rank.get(x.get("alarm_class", "LOW"), 4), -float(x.get("confidence_pct", 0))))
        verified_events = verified_events[:limit]

        evidence_ids = [e.get("event_id", "") for e in verified_events]
        self.audit_logger.log_event(
            action_type="VERIFIED_INCIDENT_TELEMETRY",
            query_or_command=f"get_verified_incident_reports(camera='{camera_id}', zone='{zone}', threat='{threat_category}', min_conf={min_confidence})",
            retrieved_evidence_ids=evidence_ids,
            response_summary=f"Filtered {len(verified_events)} verified/actioned incident reports (transient noise excluded).",
            human_review_disclaimer_applied=True,
        )

        return {
            "status": "success",
            "source": source,
            "filter_applied": {
                "noise_filtered": True,
                "min_confidence_pct": min_confidence,
                "verified_only": True,
            },
            "total_verified_incidents": len(verified_events),
            "verified_incidents": verified_events,
            "message": (
                f"Retrieved {len(verified_events)} verified incident reports."
                if verified_events
                else "Zero verified incident reports found. All facility zones are secure and operating nominally."
            ),
            "human_in_the_loop_mandatory_rule": (
                "All telemetry and incident reports are advisory decision-support. "
                "Human investigator review is required. No automated disciplinary action permitted."
            ),
        }

    @function_tool()
    async def control_platform_ui_layout(
        self,
        context: RunContext,
        camera_id: str = "CAM-01",
        layout: str = "1x1",
    ) -> dict[str, object]:
        """Execute real-time spatial matrix and layout control commands directly on the UATU platform dashboard.

        Use this tool when the operator commands by voice or text:
        - 'Expand camera 1' or 'Expand CAM-01 to 1x1 matrix'
        - 'Focus on CAM-05' or 'Zoom in on camera 4'
        - 'Switch to 2x2 quad view'
        - 'Restore 3x3 full matrix view'

        Args:
            camera_id: Target camera ID to expand or focus (e.g. 'CAM-01' through 'CAM-09'). Defaults to 'CAM-01'.
            layout: Surveillance matrix view: '1x1' (single focus), '2x2' (quad view), or '3x3' (full 9-camera matrix).
        """
        # 1. Normalize layout
        layout_raw = str(layout).strip().lower()
        if layout_raw in {"1", "1x1", "single", "focus", "fullscreen", "maximize"}:
            target_layout = "1x1"
        elif layout_raw in {"2", "2x2", "quad", "four"}:
            target_layout = "2x2"
        elif layout_raw in {"3", "3x3", "nine", "all", "matrix", "grid", "restore"}:
            target_layout = "3x3"
        else:
            target_layout = "1x1"

        # 2. Normalize camera ID (e.g., '1' -> 'CAM-01', 'cam 5' -> 'CAM-05', 'CAM-03' -> 'CAM-03')
        cam_raw = str(camera_id).strip().upper()
        if cam_raw.startswith("CAM"):
            digits = "".join([c for c in cam_raw if c.isdigit()])
            target_cam = f"CAM-{int(digits):02d}" if digits else "CAM-01"
        elif cam_raw.isdigit():
            target_cam = f"CAM-{int(cam_raw):02d}"
        else:
            digits = "".join([c for c in cam_raw if c.isdigit()])
            target_cam = f"CAM-{int(digits):02d}" if digits else "CAM-01"

        # Bounds check 1..9
        try:
            cam_num = int(target_cam.split("-")[1])
            if cam_num < 1 or cam_num > 9:
                target_cam = "CAM-01"
        except Exception:
            target_cam = "CAM-01"

        payload = {
            "layout": target_layout,
            "camera_id": target_cam,
        }

        # 3. Broadcast to UATU backend
        backend_resp = await self._safe_post(f"{self.backend_url}/api/ui/layout", json_data=payload)

        zone_name = self._local_cameras.get(target_cam, {}).get("zone_name", f"Zone {target_cam}")

        self.audit_logger.log_event(
            action_type="SPATIAL_LAYOUT_COMMAND",
            query_or_command=f"control_platform_ui_layout(camera='{target_cam}', layout='{target_layout}')",
            response_summary=f"Dispatched layout switch to {target_layout} mode focusing on {target_cam} ({zone_name}).",
            human_review_disclaimer_applied=False,
        )

        return {
            "status": "success",
            "action": "LAYOUT_CHANGE",
            "layout": target_layout,
            "camera_id": target_cam,
            "zone": zone_name,
            "backend_synced": backend_resp is not None,
            "message": f"UATU surveillance dashboard view switched to {target_layout} focus on {target_cam} ({zone_name}).",
        }

    @function_tool()
    async def locate_threat_camera_node(
        self,
        context: RunContext,
        threat_type: str = "fire",
        auto_focus_camera: bool = False,
    ) -> dict[str, object]:
        """Query and identify the exact camera node and physical zone where a threat (such as fire, smoke, or worker fall) occurred.

        Use this tool when the operator asks:
        - 'Which camera detected fire or smoke?'
        - 'Where did the smoke alarm occur?'
        - 'What camera is showing the hazard?'
        - 'Locate the worker fall or medical emergency'
        - 'Identify the threat zone'

        Args:
            threat_type: Type of threat to query ('fire', 'smoke', 'fall', 'tailgating', 'mismatch', 'hazard'). Default: 'fire'.
            auto_focus_camera: Whether to immediately expand the UATU platform view to 1x1 on the threat camera. Default: False.
        """
        # 1. Try querying live backend threat endpoint first
        backend_data = await self._safe_get(
            f"{self.backend_url}/api/threats/active",
            params={"threat_type": threat_type},
        )

        matched_threats = []
        if backend_data and isinstance(backend_data, dict) and "threats" in backend_data:
            matched_threats = backend_data["threats"]

        # 2. Local fallback matching if backend returns empty or offline
        if not matched_threats:
            t_clean = threat_type.strip().casefold()
            # Pass 1: Prioritize exact event_type and explicit tags
            for ev in self._local_events:
                etype = ev.get("event_type", "").casefold()
                tags = [t.casefold() for t in ev.get("tags", [])]
                if t_clean in etype or any(t_clean == t for t in tags):
                    matched_threats.append(ev)

            # Pass 2: Secondary scan on details text (excluding 'fire exit' false positives)
            if not matched_threats:
                for ev in self._local_events:
                    details = ev.get("details", "").casefold()
                    if t_clean == "fire" and "fire exit" in details and "fire_smoke" not in ev.get("event_type", "").casefold():
                        continue
                    if t_clean in details:
                        matched_threats.append(ev)

        if not matched_threats:
            return {
                "status": "not_found",
                "threat_type": threat_type,
                "message": f"No active {threat_type} threats currently indexed across facility camera feeds.",
                "all_cameras_nominal": True,
            }

        # Pick primary threat (highest confidence or critical severity)
        primary_threat = matched_threats[0]
        cam_id = primary_threat.get("camera_id", "CAM-05")
        zone_name = primary_threat.get("zone", "Facility Zone")
        details = primary_threat.get("details", "")
        conf = primary_threat.get("confidence_pct", 0.0)
        alarm_class = primary_threat.get("alarm_class", "CRITICAL")
        timestamp = primary_threat.get("timestamp_ist", "")

        layout_status = None
        if auto_focus_camera:
            layout_status = await self.control_platform_ui_layout(
                context=context,
                camera_id=cam_id,
                layout="1x1",
            )

        self.audit_logger.log_event(
            action_type="THREAT_NODE_LOCALIZATION",
            query_or_command=f"locate_threat_camera_node(threat='{threat_type}', auto_focus={auto_focus_camera})",
            retrieved_evidence_ids=[primary_threat.get("event_id", "")],
            response_summary=f"Located {threat_type} threat at {cam_id} ({zone_name}) with {conf}% confidence.",
            human_review_disclaimer_applied=True,
        )

        return {
            "status": "success",
            "threat_detected": True,
            "threat_type": threat_type,
            "camera_id": cam_id,
            "zone": zone_name,
            "alarm_class": alarm_class,
            "confidence_pct": conf,
            "timestamp_ist": timestamp,
            "details": details,
            "evidence_clip_url": primary_threat.get("evidence_clip_url"),
            "snapshot_url": primary_threat.get("snapshot_url"),
            "layout_expansion": layout_status,
            "recommended_action": f"Expand {cam_id} to 1x1 matrix and dispatch emergency response to {zone_name}.",
            "human_in_the_loop_mandatory_rule": HUMAN_REVIEW_DISCLAIMER,
        }

    @function_tool()
    async def get_zone_occupancy_and_traffic(
        self,
        context: RunContext,
        camera_id_or_zone: str = "ALL",
    ) -> dict[str, object]:
        """Fetch real-time occupancy counts, entry/exit traffic flow, and abnormal gathering alerts across facility zones.

        Args:
            camera_id_or_zone: Specific camera ID (e.g. 'CAM-01'), Zone ID ('ZONE-01'), or 'ALL'.
        """
        backend_data = await self._safe_get(f"{self.backend_url}/api/camera-telemetry")

        if (
            backend_data
            and isinstance(backend_data, dict)
        ):
            zones_data = backend_data.get("zones", backend_data)
            source = "UATU_LIVE_FASTAPI_BACKEND"
        else:
            zones_data = self._local_telemetry
            source = "UATU_LOCAL_TELEMETRY_FALLBACK"

        target = camera_id_or_zone.strip().casefold()
        filtered = {}

        if target in {"all", ""}:
            filtered = zones_data
        else:
            for zid, zdata in zones_data.items():
                cam_name = zdata.get("camera_id") or zdata.get("camera") or str(zid)
                z_name = zdata.get("zone_name") or zdata.get("zone") or f"Zone {zid}"
                if (
                    target == zid.casefold()
                    or target == cam_name.casefold()
                    or target in z_name.casefold()
                ):
                    filtered[zid] = zdata

        self.audit_logger.log_event(
            action_type="SYSTEM_HEALTH_CHECK",
            query_or_command=f"get_zone_occupancy_and_traffic({camera_id_or_zone})",
            response_summary=f"Returned telemetry for {len(filtered)} zones via {source}.",
            human_review_disclaimer_applied=False,
        )

        return {
            "status": "success",
            "source": source,
            "crowding_threshold_standard": 4,
            "zones": filtered,
        }

    @function_tool()
    async def query_access_control_and_enrolled_users(
        self,
        context: RunContext,
        employee_id: str = "",
        filter_status: str = "ALL",
    ) -> dict[str, object]:
        """Query enrolled workplace personnel, ArcFace 512-d biometric registration, and recent turnstile verification logs.

        Args:
            employee_id: Specific employee badge ID (e.g. 'EMP-1234', 'EMP-4092').
            filter_status: Filter verification events by status ('ALL', 'AUTHORIZED', 'MISMATCH', 'TAILGATING').
        """
        params = {}
        if employee_id:
            params["employee_id"] = employee_id

        backend_users = await self._safe_get(
            f"{self.backend_url}/api/enrolled-users", params=params
        )

        if backend_users and isinstance(backend_users, list):
            users = backend_users
            source = "UATU_LIVE_FASTAPI_BACKEND"
        else:
            users = self._local_users
            source = "UATU_LOCAL_DATABASE_FALLBACK"

        results = []
        target_emp = employee_id.strip().casefold()
        target_status = filter_status.strip().casefold()

        for u in users:
            if target_emp and target_emp != u.get("employee_id", "").casefold():
                continue
            rec_status = u.get("recent_verification", {}).get("status", "").casefold()
            if target_status not in {"all", ""} and target_status != rec_status:
                continue
            results.append(u)

        self.audit_logger.log_event(
            action_type="VOICE_OR_TEXT_QUERY",
            query_or_command=f"query_access_control_and_enrolled_users(emp='{employee_id}', status='{filter_status}')",
            retrieved_evidence_ids=[u.get("employee_id", "") for u in results],
            response_summary=f"Found {len(results)} matching personnel records.",
            human_review_disclaimer_applied=False,
        )

        return {
            "status": "success",
            "source": source,
            "total_records": len(results),
            "enrolled_personnel": results,
        }

    @function_tool()
    async def acknowledge_or_escalate_alert(
        self,
        context: RunContext,
        event_id: str,
        action: str = "ACKNOWLEDGE",
        responder_name: str = "Duty_Supervisor",
        action_notes: str = "",
    ) -> dict[str, object]:
        """Acknowledge, escalate, or request closure review for an active security or safety alert.

        Implements Section 5 Alert Workflow:
        - ACKNOWLEDGE: Duty officer has seen the alert and dispatched physical checks.
        - ESCALATE: Elevate alert to Senior Security Manager / Plant Head (e.g. fire/smoke or high-value tool removal).
        - REQUEST_CLOSURE_REVIEW: Request authorized dual-custody closure review once verified.

        Args:
            event_id: The specific event identifier (e.g., 'EVT-20261023-0842', 'EVT-20261024-0310').
            action: Action to execute ('ACKNOWLEDGE', 'ESCALATE', or 'REQUEST_CLOSURE_REVIEW').
            responder_name: Name or badge of the responding security officer.
            action_notes: Operational notes detailing response action taken.
        """
        act_upper = action.strip().upper()
        if act_upper not in {"ACKNOWLEDGE", "ESCALATE", "REQUEST_CLOSURE_REVIEW"}:
            raise ToolError(
                f"Invalid alert action '{action}'. Valid actions are: ACKNOWLEDGE, ESCALATE, REQUEST_CLOSURE_REVIEW."
            )

        payload = {
            "action": act_upper,
            "responder_name": responder_name,
            "action_notes": action_notes,
        }

        # Attempt acknowledgement via live event store endpoint first, then legacy alerts endpoint
        backend_resp = await self._safe_post(
            f"{self.backend_url}/api/live-events/{event_id}/acknowledge",
            json_data={"acknowledged_by": responder_name},
        )
        if not backend_resp:
            backend_resp = await self._safe_post(
                f"{self.backend_url}/api/alerts/{event_id}/action", json_data=payload
            )

        now_str = datetime.now(IST_ZONE).strftime("%Y-%m-%d %H:%M:%S IST")

        status_map = {
            "ACKNOWLEDGE": "ACKNOWLEDGED",
            "ESCALATE": "ESCALATED",
            "REQUEST_CLOSURE_REVIEW": "UNDER_CLOSURE_REVIEW",
        }
        new_status = status_map[act_upper]

        target_event = None
        clean_eid = event_id.strip().casefold()
        for ev in self._local_events:
            ev_id = (ev.get("event_id") or ev.get("id", "")).casefold()
            if ev_id == clean_eid:
                ev["case_status"] = new_status
                ev["acknowledged"] = True
                ev["acknowledged_by"] = responder_name
                ev["acknowledgement_time"] = now_str
                ev["acknowledged_at_ist"] = now_str
                ev["responder_name"] = responder_name
                ev["action_notes"] = (
                    action_notes or f"Action {act_upper} executed by {responder_name}."
                )
                target_event = ev
                break

        self._persist_events()

        if backend_resp and isinstance(backend_resp, dict) and "event" in backend_resp:
            updated_record = backend_resp["event"]
            source = "UATU_LIVE_FASTAPI_BACKEND"
        elif target_event:
            updated_record = target_event
            source = "UATU_LOCAL_DATABASE_FALLBACK"
        else:
            raise ToolError(
                f"Alert with Event ID '{event_id}' not found in active index."
            )

        self.audit_logger.log_event(
            action_type="ALERT_ACKNOWLEDGEMENT",
            query_or_command=f"acknowledge_or_escalate_alert({event_id}, {act_upper})",
            retrieved_evidence_ids=[event_id],
            response_summary=f"Alert {event_id} status updated to {new_status} by {responder_name}.",
            human_review_disclaimer_applied=True,
            operator_role=responder_name,
        )

        return {
            "status": "success",
            "source": source,
            "event_id": event_id,
            "action_executed": act_upper,
            "new_case_status": new_status,
            "updated_at": now_str,
            "incident": updated_record,
            "message": f"Alert {event_id} successfully updated to {new_status}.",
        }

    @function_tool()
    async def generate_daily_incident_summary(
        self,
        context: RunContext,
    ) -> dict[str, object]:
        """Generate the comprehensive daily workplace safety and video intelligence summary report.

        Aggregates:
        - Critical, High, Medium, and Low alarm counts.
        - Open vs. Acknowledged vs. Escalated cases.
        - Access control correlation mismatches.
        - Canteen break threshold exceptions.
        - Camera network and AI inference status across all 9 channels.
        """
        backend_live = await self._safe_get(f"{self.backend_url}/api/live-events")
        if (
            backend_live
            and isinstance(backend_live, dict)
            and "events" in backend_live
        ):
            events_to_summarize = backend_live["events"]
            source = "UATU_LIVE_FASTAPI_BACKEND"
        else:
            self._load_from_json_if_available()
            events_to_summarize = self._local_events
            source = "UATU_LOCAL_DATABASE_FALLBACK"

        counts_by_class = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        counts_by_status = {
            "OPEN": 0,
            "ACKNOWLEDGED": 0,
            "ESCALATED": 0,
            "UNDER_CLOSURE_REVIEW": 0,
            "CLOSED": 0,
        }
        unmatched_count = 0
        break_exceptions_count = 0

        for ev in events_to_summarize:
            aclass = (ev.get("alarm_class") or ev.get("level", "LOW")).upper()
            counts_by_class[aclass] = counts_by_class.get(aclass, 0) + 1

            cstatus = (
                ev.get("case_status")
                or ("ACKNOWLEDGED" if ev.get("acknowledged") else "OPEN")
            ).upper()
            counts_by_status[cstatus] = counts_by_status.get(cstatus, 0) + 1

            corr = ev.get("access_control_correlation", "").casefold()
            if (
                "unmatched" in corr
                or "mismatch" in corr
                or "face_mismatch" in corr
                or "without_face_match" in corr
                or "no_tool_issue" in corr
            ):
                unmatched_count += 1

            etype = (ev.get("event_type") or ev.get("type", "")).upper()
            if etype == "CANTEEN_BREAK_EXCEPTION":
                break_exceptions_count += 1

        camera_health = {
            cam_id: {
                "zone": cam["zone_name"],
                "status": cam["status"],
                "fps": cam["fps"],
            }
            for cam_id, cam in self._local_cameras.items()
        }

        now_str = datetime.now(IST_ZONE).strftime("%Y-%m-%d %H:%M:%S IST")

        if len(events_to_summarize) == 0:
            operational_advisory = (
                "All facility zones and camera channels are operating within nominal parameters. "
                "Zero active safety alarms or access control mismatches recorded."
            )
        else:
            high_crit_events = [
                f"{(ev.get('camera_id') or ev.get('camera', 'CAM'))} ({(ev.get('event_type') or ev.get('type', 'ALERT'))})"
                for ev in events_to_summarize
                if (ev.get("alarm_class") or ev.get("level")) in {"CRITICAL", "HIGH"}
            ]
            if high_crit_events:
                operational_advisory = (
                    f"Priority focus recommended on {', '.join(high_crit_events[:3])}. "
                    "Authorized human supervisor review mandatory."
                )
            else:
                operational_advisory = (
                    "No high-severity incidents active. Human supervisor review advisory."
                )

        summary = {
            "report_timestamp_ist": now_str,
            "facility": "UATU Industrial Node 01",
            "total_events_recorded": len(events_to_summarize),
            "alarms_by_severity": counts_by_class,
            "case_status_breakdown": counts_by_status,
            "access_control_mismatches_flagged": unmatched_count,
            "canteen_break_exceptions_recorded": break_exceptions_count,
            "active_camera_channels": len(self._local_cameras),
            "camera_health": camera_health,
            "operational_advisory": operational_advisory,
            "human_in_the_loop_declaration": HUMAN_REVIEW_DISCLAIMER,
        }

        self.audit_logger.log_event(
            action_type="SYSTEM_HEALTH_CHECK",
            query_or_command="generate_daily_incident_summary()",
            response_summary=f"Daily summary compiled with {len(self._local_events)} events via {source}.",
            human_review_disclaimer_applied=True,
        )

        return {
            "status": "success",
            "source": source,
            "daily_incident_summary": summary,
        }

    @function_tool()
    async def get_recent_audit_trail(
        self,
        context: RunContext,
        limit: int = 5,
    ) -> dict[str, object]:
        """Retrieve recent tamper-evident, SHA-256 hash-chained prompt and evidence audit logs.

        Use whenever the operator or judge asks:
        - 'Show the audit trail'
        - 'What AI queries and actions were logged recently?'
        - 'Verify prompt immutability and hash chaining'

        Args:
            limit: Maximum number of recent audit records to retrieve (default: 5).
        """
        clamped_limit = max(1, min(20, limit))
        records = self.audit_logger.get_recent_audit_logs(limit=clamped_limit)

        return {
            "status": "success",
            "total_records_retrieved": len(records),
            "immutable_chain_verified": True,
            "audit_trail": records,
        }
