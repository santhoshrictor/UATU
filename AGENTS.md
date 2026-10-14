# Antigravity Operating Rules — Workplace Video Intelligence

These persistent instructions govern all AI agent work on this repository across all sessions.

## 1. Authorized Scope Boundary
- **Current Authorized Scope:** Stage 1 — Foundation Only.
- Work only on the currently authorized stage.
- Do not implement, partially implement, or scaffold later stages (such as live RTSP streaming, AI model inference, model training, notification dispatch, or external integrations) until explicitly authorized in writing by the user.
- Stop at the stage handover; do not start the next stage automatically.

## 2. Session Handover & State Tracking
- Always read [STATUS.md](file:///c:/Users/sandy/Desktop/Workplace-Intelligence-V2/STATUS.md) and [NEXT_STEPS.md](file:///c:/Users/sandy/Desktop/Workplace-Intelligence-V2/NEXT_STEPS.md) when resuming work or beginning a new turn.
- Keep all 91 catalogued requirements tracked in [REQUIREMENTS.md](file:///c:/Users/sandy/Desktop/Workplace-Intelligence-V2/REQUIREMENTS.md).
- Update status metrics honestly:
  1. Foundation Acceptance: passed checks out of 8.
  2. Verified Feature Coverage: count of verified features out of 91.
  3. Production Acceptance: separate outstanding physical and operational gates.

## 3. Truthfulness & Integrity
- **No Fabricated Operational Data:** Never inject fake operational cameras, synthetic incidents, mocked uptime metrics, artificial model confidence scores, or simulated live video into operational views.
- **No Unsupported Readiness Claims:** Never declare a feature "complete", "production ready", or "industry ready" merely because a directory, schema, interface, endpoint stub, or mocked test exists.
- **Honest States:** Maintain honest empty, disconnected, unavailable, and degraded states in both API responses and user interfaces.
- If a downstream dependency (database, camera, sensor, gateway) is down, report truthful failure rather than suppressing errors or faking success.

## 4. Data Safety & Privacy
- Preserve user data and any existing projects. Never overwrite or delete user files without explicit consent.
- Keep credentials, database passwords, tokens, private keys, and private footage strictly out of source control, scripts, and logs.
- Respect camera privacy rules: ambient audio and face recognition remain disabled by default.

## 5. Verification & Testing
- Record tests actually executed, including exact commands, outputs, and any failures encountered.
- Real integration tests must execute against real services (e.g., real PostgreSQL, not mocked SQLite disguised as PostgreSQL).
- If an environment restriction blocks a test or check, identify the exact missing dependency and keep the check marked as unverified.
