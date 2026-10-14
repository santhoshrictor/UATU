# System Architecture & Technical Design — Stage 1 Foundation

## 1. Executive Architecture Overview

The **Workplace Video Intelligence System** is an on-premise industrial safety, security, and video management platform designed to operate continuously within enterprise facilities without requiring connectivity to public cloud services.

The system is structured across four decoupled processing pipelines to ensure high availability, data integrity, and deterministic latency:

```
[ IP Cameras / RTSP ]
         │
         ├───► Path 1: Dedicated Video Ingest & Recording (VMS/Storage)
         │       └─► Continuous / policy-based raw video retention (filesystem/NVMe)
         │
         ├───► Path 2: Analytics & Vision Inference Workers (Separate Processes)
         │       └─► Substream decoding ──► Object Detection ──► Spatial Rules ──► Structured Events
         │                                                                             │
         │                                                                             ▼
         └───► Path 3: Durable Event Dispatch & Workflow ◄──────────────────────────────┘
                 └─► Transactional Outbox ──► Alarm Routing ──► Escalation Engine ──► Local Alerts
                                                                                       │
[ Browser / Operator ] ◄─── Path 4: FastAPI Core Service ◄─── PostgreSQL (Metadata) ───┘
```

---

## 2. Stage 1 Foundation Components

In Stage 1, the foundational engineering substrate is established:

| Component | Technology | Role & Boundary in Stage 1 |
|---|---|---|
| **Operator Interface** | React 19, TypeScript, Vite | System status dashboard, connection diagnostics, and truthful state rendering. No camera tiles or analytics UI. |
| **Core Business API** | Python 3.12, FastAPI, Pydantic v2 | Configuration validation, structured logging, error handling, `/health/live` and `/health/ready` probes. |
| **Relational Database** | PostgreSQL 16.2 (Local on-premise) | Primary storage for spatial metadata (Sites, Areas), transaction records, and migration state. |
| **Schema Migrations** | Alembic 1.20 | Version-controlled DDL migrations (`create_sites_and_areas_tables`). |
| **Testing Substrate** | Pytest, TestClient, psycopg3 | Isolated test suite validating real PostgreSQL transactions, migrations, and referential integrity against `workplace_test`. |

---

## 3. Why Heavy Pipelines are Decoupled from the Core Web API

A critical design requirement is that video processing, deep learning inference, and background workflow dispatch must **never** run inside the synchronous request loop of the web backend:

### A. Dedicated Video Recording Pipeline (Path 1)
- **Problem:** Video ingestion (RTSP/ONVIF) generates high-throughput continuous I/O (up to 40-80 Mbps for 16-32 cameras). If video frames pass through the web application or share database tables with operational metadata, video recording frames drop during API traffic spikes, and transactional database tables bloat uncontrollably.
- **Architecture Solution:** Media recording runs as an independent media daemon (such as MediaMTX or dedicated VMS storage service) writing directly to segmented storage volumes. The core API only indexes metadata and pointers to recorded video clips.

### B. Machine Learning Inference Workers (Path 2)
- **Problem:** Computer vision models (YOLO object detection, pose estimation, action recognition) consume significant GPU/CPU memory and compute cycles. Running tensor inference inside FastAPI worker threads blocks HTTP event loops, causing health check timeouts, request drops, and system instability.
- **Architecture Solution:** Analytics run in isolated background worker processes (using ONNX Runtime / TensorRT / DeepStream). These workers consume RTSP analytical substreams (e.g., 640x360 at 5-10 fps) independently from the high-resolution recording stream.

### C. Durable Workflow & Event Dispatch (Path 3)
- **Problem:** When an incident occurs (e.g. unauthorized after-hours entry, fire alarm input), notification delivery over SMS, email, or webhook can suffer external network latency or timeouts. Holding web requests or vision workers while waiting for external notifications risks dropping subsequent alarms.
- **Architecture Solution:** Events are durably written to PostgreSQL using a transactional outbox pattern. A dedicated escalation worker handles acknowledgement timeouts and dispatches notifications asynchronously with guaranteed retry policies.

---

## 4. Privacy, Security, and Governance Guardrails

The foundation architecture embeds the privacy boundaries specified in the project requirements:

1. **Ambient Audio Disabled by Default:** Continuous workplace audio recording is strictly prohibited by configuration and code. Microphones are utilized solely for user-initiated push-to-talk voice commands in Stage 8.
2. **Face Recognition Disabled by Default:** Object detection in Stage 4 is strictly anonymous person detection (bounding box / centroid tracking). Biometric identification requires explicit site privacy approval and separate legal basis.
3. **Local Processing Independence:** All authentication, recording, analytics, and alerting functions are engineered to operate during a complete WAN/internet outage.
4. **Credential Redaction in Logs:** All log formatters automatically redact passwords, database credentials, and session tokens before emitting to standard output or logfiles.
