# Workplace Video Intelligence — Professional Build Plan

Prepared 13 October 2026. A fresh-build engineering roadmap based on the supplied seven-page requirements specification and the primary technical sources linked below.

This document plans a new implementation. It does not assume that previous application code is complete or production ready. Technology selections, implementation details, and additional verification methods are engineering recommendations; the PDF remains the requirements authority. Product documentation establishes capabilities, not performance on your hardware or compliance at your site.

**The first release objective**

Build one dependable workflow: a real camera records footage; a configured boundary crossing creates an incident; available before-and-after evidence is preserved; an authorized responder receives and acknowledges the alert; the incident can be investigated, closed, exported, and found later. Demonstrate that this workflow recovers from disconnections and restarts before expanding the feature count.

The full product must then cover recording, analytics, access and asset correlations, fire/safety inputs, incident response, evidence search, speech, health monitoring, security, installation, and ongoing operation. A model demonstration or a completed dashboard cannot establish production readiness by itself.

**How to use this plan**

Follow stages 1–24 in order for the main implementation. Each stage has deliverables and an exit gate. Data collection, security review, hardware procurement, and integration discussions begin early and continue alongside implementation. A gate means evidence exists that the stage works; it is not merely a checkbox saying the code was written.

Keep feature status as: Not started → Implemented → Lab tested → Site tested → Accepted. Add Blocked on equipment/data where appropriate. Features that require unavailable equipment remain explicitly unaccepted. Tests may use labeled fixtures; operational screens must accurately distinguish live inputs, recorded replay, and test signals.

**Requirements and measurable targets**

The following targets come from sections 1, 12, and 14 of the supplied PDF. The proposed measurement definitions need agreement before formal acceptance.

| Requirement | PDF target | Measurement to specify |
|---|---|---|
| Initial deployment | 8–16 cameras; recommended initial pilot is eight | Exact camera models, streams, resolutions, enabled analytics, concurrent users |
| Expansion | At least 32 cameras without replacing the core architecture | Same interfaces and data model; capacity additions allowed |
| LAN live view | Normally less than 2–5 seconds | Agree a precise target within that range and percentile; measure scene-to-screen delay |
| Standard AI alert | Normally less than 10 seconds from detected event | Record event onset, rule confirmation, incident persistence, and screen-display times separately |
| Camera/video-loss notification | Within 60 seconds or tighter where feasible | Inject loss and measure until the authorized monitoring screen reports it |
| Indexed historical search | Normally within 30 seconds for standard queries over 30 days | Define representative queries, index size, user concurrency, warm/cold conditions |
| Playback start | Normally within five seconds on LAN for standard clips | Request-to-first-playable-frame measurement |
| Availability | At least 99.5%, excluding planned maintenance | Agree services, measurement window, partial outages, and maintenance exclusions |
| AI quality | Separate false-positive and false-negative measures per use case | Define event matching, scene conditions, samples, and acceptable limits |
| Evidence | Watermarked, auditable exports with source and reviewer context | Verify authorization, timestamps, manifest, playback, and audit history |
| Critical response | Alert, acknowledgement, escalation, delivery log, closure demonstrated | Test the complete workflow with real configured recipients and authorized test inputs |
| Pilot | Eight cameras, 30-day retention, review after 30–60 days | Review coverage, false alerts, storage, GPU load, response, and limitations |

For context, 99.5% over a 30-day period permits about 3.6 hours of unplanned downtime if the full period is eligible. Define availability separately for recording, alerting, and interactive use so one healthy homepage cannot hide a failed recorder. This calculation is explanatory, not a replacement for the acceptance agreement.

**Recommended architecture and starting technology choices**

Start with one repository and a modular business application. Run video, inference, and background work as independently supervised processes. This preserves a manageable codebase while isolating resource-heavy and failure-prone components.

| Layer | Proposed starting choice | Reason and boundary |
|---|---|---|
| Operator interface | React with TypeScript; a small consistent component system | Appropriate for camera layouts, forms, timelines, and incident workflows; frontend framework is replaceable |
| Business API | Python/FastAPI with schema validation | Shares a language with analytics; keep video processing outside request handlers |
| Metadata | PostgreSQL with managed schema migrations | Transactions, concurrency, indexes, reporting, and recoverable operational records |
| Identity | Local OIDC identity provider such as Keycloak | Central login and MFA; application still owns camera/action authorization |
| Media routing | Evaluate MediaMTX behind authenticated application access | RTSP ingress and browser-facing delivery; it is a media component, not the entire incident product |
| Recording | Existing approved VMS/NVR adapter where available; otherwise a dedicated recorder using mature media components | One authoritative recording inventory and retention policy; avoid competing retention owners |
| Media processing | FFmpeg; evaluate GStreamer when pipeline control warrants it | Remuxing, clipping, probing, transcoding; retain exact build and license information |
| Initial inference | ONNX Runtime with explicitly verified CPU/GPU provider | Portable model runtime; selecting CUDA in configuration does not prove GPU execution |
| Higher-scale inference | Evaluate NVIDIA DeepStream after benchmarking the first pipeline | Candidate for efficient multi-stream NVIDIA deployment; pin the supported platform combination |
| Work dispatch | PostgreSQL transactional outbox initially; RabbitMQ when worker routing/load warrants it | Durable event-to-work handoff; retries must be safe regardless of broker |
| Video storage | Dedicated recording filesystem/storage appliance; separate metadata and evidence policies | Avoid putting large video blobs inside transactional tables |
| Service monitoring | Prometheus plus an operator metrics view; OpenTelemetry where tracing helps | Infrastructure monitoring complements the application's incident workflow |
| Local language/speech | Pluggable local model service; evaluate faster-whisper for transcription | Models loaded locally, bounded resource use, full license inventory |
| Deployment | Pinned services/containers on supported Ubuntu Server LTS for the production AI host | Matches PDF preference; Windows remains usable for development and selected VMS components |

MediaMTX documents routing, recording, playback, and authentication. Codec compatibility still requires testing; changing transport does not automatically re-encode an unsupported codec. [MediaMTX introduction](https://mediamtx.org/docs/kickoff/introduction), [authentication](https://mediamtx.org/docs/features/authentication)

FastAPI distinguishes ordinary background tasks from heavier processing that may need separate workers. PostgreSQL provides documented recovery facilities. These support the choices above; they do not remove the need for application-level durability and recovery tests. [FastAPI background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/), [PostgreSQL recovery](https://www.postgresql.org/docs/current/continuous-archiving.html)

Keep three processing paths distinct:

1. Camera main stream → recorder → retained original media → evidence/playback.
2. Camera analytic stream → detector/tracker → rules → durable events → incidents/alerts.
3. Authorized question → constrained query → permitted metadata/evidence → grounded answer.

External alarms enter the event/incident path directly. They must not wait for an AI model, chatbot, or clip encoder. Do not send full video frames through the ordinary incident message queue.

**Stage 1 — Define the product contract**

1. Create one requirement record per capability, linked to the PDF section and the feature catalog in the appendix.
2. For each, specify actor, inputs, behavior, output, permissions, degraded behavior, and acceptance scenario.
3. Establish a role matrix: administrator, security operator, safety officer, investigator, supervisor, maintenance technician, and restricted attendance reviewer as needed.
4. Define site vocabulary: cameras, areas, doors, zones, shifts, assets, alarm priorities, case outcomes, and exempt situations.
5. Resolve ambiguous terms such as abnormal gathering, unsafe behavior, acceptable break duration, and unauthorized presence.
6. Establish release scope: foundation; operational pilot; complete required analytics/search; accepted integrations; optional enhancements.
7. Record unresolved site decisions with an owner and deadline. Do not silently choose a policy that could affect employment or incident response.

Deliver: requirements register, role matrix, use-case definitions, acceptance plan, assumption/decision log.

Exit gate: every required behavior has an observable test and a defined owner. Optional work cannot obscure an unfinished mandatory feature.

**Stage 2 — Establish site, hardware, data, and integration prerequisites**

1. Plan the actual areas, fields of view, camera heights, illumination, blind spots, coverage overlap, cables, PoE budget, and network segmentation.
2. Identify a real camera for development and a second model for interoperability testing. Borrowing suitable equipment is sufficient for initial development; production procurement follows measurement.
3. Request authorized representative footage covering daylight, night, empty scenes, occlusion, crowded scenes, and legitimate activities that resemble incidents.
4. Obtain interface documentation and a safe test arrangement for the actual access controller, alarm gateway, inventory system, and messaging provider.
5. Identify who approves camera placement, data handling, recording policies, and field alarm tests.
6. Build a hardware/software bill of quantities with license, support, and warranty fields.
7. Begin dataset annotation and integration contract work now. These are common dependencies that cannot be solved by a final week of programming.

Your earlier hardware inspection found approximately 4 GB GPU memory and 11.7 GB usable RAM. Treat this as a development constraint and re-check before implementation. Run components selectively; use small models and modest analytic input rates. Do not infer production camera capacity from this machine. The PDF lists 64 GB minimum RAM and a 24 GB pilot GPU, with larger recommended production equipment; those are source specifications, not a new purchasing recommendation.

Exit gate: a documented lab plan, approved data sources, equipment access plan, and external-system contacts exist. Physical site acceptance remains blocked until actual devices are available.

**Stage 3 — Make architecture and licensing decisions**

1. Choose the supported initial deployment: one on-premise site with multiple users and cameras. Keep site identifiers in records for later extension without implementing unnecessary multi-tenant billing or cloud infrastructure.
2. Decide whether an existing VMS/NVR is the recorder. Define a recorder adapter so the rest of the product requests recordings by camera and time regardless of vendor.
3. Specify service boundaries, storage ownership, time semantics, and degraded modes.
4. Choose supported versions as a tested compatibility set: OS, driver, CUDA libraries if used, inference runtime, model export format, recorder, database, browser codecs.
5. Inventory licenses for application dependencies, model code, weights, training data, fonts, icons, codecs, and distribution binaries.
6. Keep a short architecture decision record explaining each important choice and its rejected alternatives.

Ultralytics offers AGPL-3.0 and Enterprise licensing paths; review the applicable terms before using its components in a proprietary product. RT-DETR's original repository is another candidate to evaluate, not an automatic performance or licensing clearance for every weight/dataset. FFmpeg licensing depends on the build and enabled components. [Ultralytics licensing](https://www.ultralytics.com/license), [RT-DETR](https://github.com/lyuwenyu/RT-DETR), [FFmpeg licensing](https://ffmpeg.org/legal.html)

Exit gate: the architecture can support all required data flows; the chosen component versions and licensing path are recorded.

**Stage 4 — Create the development and release foundation**

1. Create the repository, coding conventions, review process, and clean installation instructions.
2. Suggested directories: web, api, workers/video, workers/analytics, workers/workflow, adapters, shared/contracts, migrations, tests, deployment, docs, and model-manifests. These are proposed modules, not an instruction to create one independently deployed service per folder.
3. Create development, automated-test, staging, and production configurations. Keep secrets out of source control and logs.
4. Pin dependencies and container images; record checksums for models and installers.
5. Build automated checks for formatting, types, unit tests, integration tests, secret scanning, dependency checks, and production build generation.
6. Add schema migrations and test upgrades from the previously released schema.
7. Define a release manifest containing code revision, migrations, configuration schema, model versions, and compatible drivers/runtime.
8. Produce a software bill of materials and third-party notices for releases.

NIST SSDF is a useful reference for organizing secure development and vulnerability response throughout the lifecycle. This plan does not claim SSDF certification. [NIST SSDF](https://csrc.nist.gov/pubs/sp/800/218/final)

Exit gate: another developer can reproduce a clean build and run meaningful tests without manually reconstructing your computer.

For a fresh Windows development setup, install Git, VS Code, a supported Python version compatible with the chosen inference runtime, a supported Node.js LTS version for the frontend, and PostgreSQL. Use either native services or a tested WSL2/container setup; avoid maintaining both without a reason. Install the selected media binaries and GPU runtime only after confirming compatibility. Create separate frontend and Python dependency lockfiles, a sample configuration without secrets, and one documented startup procedure. On the limited-memory laptop, run a reduced development profile; the full deployment profile belongs on a suitably sized test host. Do not install every advanced model or infrastructure service before the first recording workflow works.

**Stage 5 — Design the data model and durable workflows**

Create entities for:

| Area | Principal records |
|---|---|
| Organization | Sites, areas, cameras, stream profiles, devices |
| Configuration | Zones, lines, rule versions, schedules, exceptions, camera mappings |
| Identity/access | Users or identity references, roles, camera scopes, access policies |
| Video | Recording segments, media time ranges, coverage gaps, evidence objects |
| Analytics | Observations, track summaries, analytic events, model/rule provenance |
| Cases | Incidents, event links, assignments, acknowledgements, notes, dispositions, approvals |
| Integrations | Source devices, external messages, correlation links, connection health |
| Notifications | Routing policy, delivery attempts, provider receipts, escalation deadlines |
| Operations | Faults, maintenance tasks, retention holds, exports, audit records |
| Search | Query audit, retrieved references, generated answers, index coverage |

1. Separate a raw observation, analytic event, and incident. Repeated observations can support one incident; one incident may involve several cameras and sensors.
2. Store UTC timestamps plus the original source timestamp, receive time, time quality, and site timezone as needed. Do not silently overwrite uncertain source time.
3. Preserve camera stream-session identity so a tracker ID reused after restart does not identify the same person.
4. Version zones and rules so an old event can be interpreted using the settings active at that time.
5. Index common searches by site, camera, time, event type, and status. Bound retention for high-volume observations; do not persist every bounding box forever by default.
6. Persist an event and its pending work in one database transaction using an outbox. Retry publication and processing safely.
7. Add idempotency keys, worker leases, bounded retries, failed-job inspection, and reconciliation jobs for database/media inconsistencies.
8. Define archive and deletion behavior for linked records before implementing cleanup.

Define database-outage behavior as well: recording should continue with a locally reconcilable inventory; gateways/workers that must preserve events need a bounded durable local spool and explicit overflow alarms. An in-memory queue cannot guarantee event survival. Reconcile spooled events after recovery without presenting delayed historical events as newly occurring emergencies. If required alarm handling cannot remain available during a database outage, the design needs an independent alarm path or appropriate high availability; document and test the chosen boundary.

Example minimum event fields: event_id, site_id, camera_id or device_id, source_kind, source_event_id, event_type, observed_at, received_at, rule_confirmed_at, rule_version, model_version, zone_version, severity, confidence or not_applicable, time_quality, evidence_status, and correlation_status.

Exit gate: duplicate inputs, retrying jobs, and worker crashes produce consistent records without duplicate case actions.

**Stage 6 — Implement identity, authorization, privacy, and audit**

1. Integrate local authentication and MFA. Use an established identity component; keep initial setup controlled, and provide an audited account-recovery procedure.
2. Enforce administrator and remote-user MFA as required by the PDF. Define ordinary local-user requirements explicitly.
3. Apply camera/site/action authorization to every API, search, count, thumbnail, live stream, playback request, export, and background job.
4. Implement secure browser sessions, CSRF protection where applicable, rate limits, logout, revocation, session expiry, and security headers.
5. Issue short-lived, narrowly scoped media access credentials. Do not make the underlying media server or recording directory an unauthenticated bypass.
6. Protect recordings, databases, temporary media, backups, and credentials at rest. Define key rotation and recovery; encryption with unrecoverable keys is not a backup plan.
7. Use TLS for supported paths. Inventory camera/field protocols that cannot encrypt and document the approved isolated-network exception or replacement requirement; VLAN separation alone is not encryption.
8. Protect audit records using restricted append operations and independent storage/checkpoints as appropriate. Hash chaining alone does not prevent an administrator from deleting the entire local history.
9. Disable ambient audio and face recognition by default. Prohibited camera locations remain prohibited regardless of masking.
10. Preserve automated urgent alerts while reserving high-impact findings and final actions for authorized human review.

The identity provider handles identity; application permissions still require explicit implementation. Use OWASP ASVS to derive security tests rather than treating a login screen as sufficient. [Keycloak application security overview](https://www.keycloak.org/securing-apps/overview), [OWASP ASVS](https://github.com/OWASP/ASVS)

Exit gate: adversarial tests cannot retrieve a restricted camera's footage, metadata, counts, or generated answers through another interface.

**Stage 7 — Implement camera ingestion and trustworthy time**

1. Build camera registration, editing, credential updates, disablement, area assignment, and capability inspection.
2. Implement supported RTSP/ONVIF connections and configured reconnect behavior. Validate allowed network destinations so camera setup cannot become arbitrary server-side network access.
3. Separate recording/main-stream and analytic/substream profiles where the camera supports them. Confirm each analytic still has adequate image detail.
4. Share stream ingestion where appropriate instead of opening one camera connection per browser viewer.
5. Synchronize cameras, server, recorder, access system, and gateways using the approved local time source.
6. Preserve mapping between media presentation timestamps and wall-clock time; detect drift, discontinuity, camera reboot, and corrected clocks.
7. Report connecting, online, stale, degraded, offline, and recovering states, with last successful frame time.
8. Test packet loss, wrong credentials, changed camera addresses, camera reboot, and repeated interruptions.

Use the official ONVIF product registry to verify the exact model and firmware. Evaluate Profile T for streaming, G for recording retrieval, and M for available analytics metadata; a profile does not imply every optional analytic exists. [ONVIF registry](https://www.onvif.org/conformant-products/), [Profile T](https://www.onvif.org/profiles/profile-t/), [Profile G](https://www.onvif.org/profiles/profile-g/), [Profile M](https://www.onvif.org/profiles/profile-m/)

Exit gate: physical supported cameras reconnect automatically and maintain explainable timestamps and status.

**Stage 8 — Implement recording, retention, and playback**

1. Record compressed video using mature media tooling; remux without re-encoding where compatible and appropriate.
2. Write bounded segments with recoverable finalization. Index only finalized/verified segments, and reconcile orphan files after crashes.
3. Implement continuous and configured recording schedules. Keep recording independent of browser sessions and inference.
4. Build a coverage-aware playback API: camera, requested interval, available intervals, missing intervals, and authorized media access.
5. Handle keyframe boundaries and codec changes. A stream-copy clip may not cut at an arbitrary frame; a precise derivative may require decoding and encoding.
6. Implement retention for ordinary footage, incident evidence, snapshots, exports, and temporary files separately.
7. Make hold creation and retention deletion race-safe. Preserve evidence while a case is active according to policy.
8. Define full-storage behavior: remove only eligible content, preserve holds, alert early, and disclose any recording loss.
9. Test broken segments, storage disconnection, process termination, and restart recovery.

Exit gate: recordings survive service restarts; timeline gaps are visible; held evidence survives routine cleanup; ordinary expired footage is actually removed.

**Stage 9 — Build the operator interface and real live delivery**

1. Create consistent navigation for overview, live/playback, incidents, search, access/break exceptions, assets, health, and administration.
2. Implement required camera layouts of 1, 4, 9, 16, and 25, camera groups, individual views, and responsive internal mobile access.
3. Use browser-compatible live transport, evaluating WebRTC for latency and an appropriate fallback. Validate codecs on the browsers actually supported.
4. Use lower-cost streams for small tiles and switch quality intentionally for focused viewing.
5. Show separate connection, recording, and analytics states. Display stale timestamps visibly.
6. Build normalized-coordinate line/zone editing, schedule forms, validation, and versioned changes.
7. Deliver incidents using a resumable event channel or polling with a durable cursor. Reconnect must fetch missed alerts, not only the newest few records.
8. Test keyboard access, readable contrast, loading/error states, long lists, empty states, and confirmation for consequential actions.
9. Test audible alerts after browser autoplay restrictions, tab suspension, screen lock, and reconnect. A closed browser is not a dependable audible alarm device.

Exit gate: operators can use live video and handle alerts on supported devices under the agreed concurrent viewing load.

**Stage 10 — Add observability and fault handling early**

1. Instrument per-camera frame age, receive bitrate, decode errors, recording gap duration, and analytics lag.
2. Track service readiness, job age, failed jobs, disk latency, storage usage, CPU/GPU/RAM, and supported temperature/fan metrics.
3. Integrate PoE/network/UPS telemetry only where interfaces provide it; distinguish unsupported metrics from normal values.
4. Create faults and maintenance tasks with first/last detection, duration, technician, corrective action, and closure.
5. Prioritize faults in gates, secure stores, tool rooms, perimeter, and fire-sensitive locations.
6. Add resource exhaustion limits and degradation rules: pause optional batch analysis or summaries before affecting recording and emergency response.
7. Monitor the monitoring path from an independent process/device where necessary so total server failure is observable.
8. Start collecting measurements needed for monthly health and incident-response reports.

Prometheus provides infrastructure alerting concepts; its alerts do not replace your human incident acknowledgement and closure workflow. OpenTelemetry can correlate service activity when debugging cross-process delays. [Prometheus alerting](https://prometheus.io/docs/alerting/latest/overview/), [OpenTelemetry](https://opentelemetry.io/docs/concepts/)

Exit gate: deliberately injected camera, disk, process, and network failures create accurate faults and recovery updates.

**Stage 11 — Implement basic detection, tracking, and rules**

1. Establish a labeled evaluation set before selecting a winning detector. Include real site negatives and difficult scenes.
2. Evaluate compact person/vehicle detector candidates using the intended input resolution, hardware, and license constraints.
3. Add short-term tracking; ByteTrack is one documented candidate. Track IDs remain anonymous and camera/session-specific.
4. Implement directional crossing using trajectory history, a dead band near the line, and a debounce policy.
5. Implement restricted-zone intrusion and basic after-hours rules with minimum persistence and explicit exemptions.
6. Keep live processing bounded: discard obsolete analytic frames when overloaded and report reduced coverage. Preserve the independent recording path.
7. Add batch analysis of recorded intervals through the same observation schema, tagged as historical processing. Do not send an old historical event as a new live emergency without an explicit policy.
8. Record model checksums, preprocessing, runtime provider, threshold, rule version, and test results.
9. Verify actual GPU execution and profile end-to-end latency, including decoding and tracking.

Treat model imports as privileged deployment operations. Accept only approved formats and manifests, validate hashes and size/resource limits, and isolate model loading. Do not deserialize arbitrary uploaded training checkpoints or execute unreviewed model repository code inside the production API process.

ONNX Runtime's CUDA support requires a compatible runtime/library combination. NVIDIA's DeepStream benchmark settings may disable rendering and other work; do not transfer headline benchmark numbers into your full application capacity claim. [ONNX CUDA provider](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html), [ByteTrack](https://github.com/FoundationVision/ByteTrack), [DeepStream performance](https://docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_Performance.html)

Exit gate: person/vehicle observations and configured entry/intrusion events have measured event-level results and documented failure cases.

**Stage 12 — Complete evidence and investigation**

1. Persist an incident immediately; do not wait for a post-event clip before notifying.
2. Reserve the relevant recording intervals so retention cannot delete them while evidence is being prepared.
3. Create snapshots and configurable pre/post clips. Mark pending, complete, partial, missing, or failed evidence accurately.
4. Preserve original media separately from watermarked or resized derivatives.
5. Implement assignment, acknowledgement, investigation, resolution, closure approval, reopening, and notes according to permissions.
6. Use transaction-safe case updates so simultaneous reviewers do not overwrite each other's actions.
7. Build exports containing the derivative clip, relevant snapshot, source/time context, reviewer history, and an integrity manifest.
8. Track exporter identity and export time. If signing manifests, define signing-key trust and recovery; a hash alone does not establish who created a package.
9. Add retention holds, authorized hold release, and audit records for playback, export, and deletion.

Exit gate: one physical-camera incident can be handled from observation through review and verified export without a developer manipulating the database.

**Stage 13 — Implement durable notifications, escalation, and safety inputs**

1. Create Critical/High/Medium/Low policy and routing by event type, area, shift, and business hours.
2. Persist assignment and escalation deadlines; restart must resume overdue work.
3. Separate notification workers from clip generation and model inference.
4. Implement provider adapters with bounded retries, idempotency where supported, failure visibility, and recipient permissions.
5. Distinguish sent, provider-accepted, delivered where known, failed, and human-acknowledged. A transport acknowledgement is not a human response.
6. Create a gateway contract with source identity, message ID, timestamp, sequence/state, authentication, replay protection, heartbeat, and fault reporting.
7. Implement the actual approved fire/gas/door/panic/etc. adapter. The PDF lists interface alternatives; implementing a generic webhook is not proof of Modbus/BACnet/OPC UA or dry-contact integration.
8. Map sources to cameras and preserve the emergency alarm even when those cameras are offline.
9. Support local pop-up and audible notification without internet; commission physical outputs only under the agreed cause-and-effect design.
10. Preserve independent fire and life-safety functions. Do not let the chatbot silence alarms or operate emergency shutdown equipment.

If using RabbitMQ, configure and test publisher confirms and consumer acknowledgements. Connection recovery can redeliver messages, so application deduplication remains necessary. [RabbitMQ reliability](https://www.rabbitmq.com/docs/reliability)

Exit gate: an authorized physical test input completes the full alert/acknowledgement/escalation/closure workflow. External messaging failure is visible and local response continues.

**Stage 14 — Build indexed search and deterministic reporting**

1. Search by time, camera, location, event, priority, status, duration, reviewer, and integration correlation.
2. Index metadata as recording/analytics progresses. Track recording coverage separately from analytics coverage.
3. Add saved filters, pagination, sorting, and stable links to evidence.
4. Make empty results distinguish no matching events from missing camera/analytics coverage.
5. Build daily incident reports and monthly health/response reports using deterministic counts and defined formulas.
6. Apply authorization to result totals, snippets, thumbnails, downloads, and scheduled recipients.
7. Benchmark representative searches over the required 30-day metadata volume under concurrent recording and live load.
8. Provide a separate, resource-limited historical-analysis job for unindexed footage; do not claim indexed-search response times for a new scan of raw video.

Exit gate: structured searches return correct evidence and counts within the agreed load/latency targets.

**Stage 15 — Implement access-control correlation and attendance support**

1. Import actual access events with stable external IDs, source timestamps, reader/door identifiers, and necessary credential mapping.
2. Map readers to camera views, lines, and passage direction.
3. Define matching windows, allowed group/visitor entry, passage capacity, clock uncertainty, and late-arrival grace periods.
4. Correlate both directions: visible passage without a matching access event and access event without a visible passage.
5. Preserve matched, unmatched, ambiguous, late, and source-unavailable outcomes. Re-evaluate provisional matches when delayed records arrive, with audit history.
6. Add tailgating hypotheses using passage counts, door context, and site policy.
7. Produce first-entry/last-exit and exception reports using only supported identity associations.
8. Allow authorized correction and final review; keep the official attendance/payroll system authoritative.

Exit gate: group entries, duplicate credentials, delayed messages, outages, and ambiguous matches do not become unsupported named accusations.

**Stage 16 — Complete presence, occupancy, schedules, and breaks**

1. Add shifts, overnight shifts, holidays, overtime, grace periods, and exemptions.
2. Implement observed zone occupancy, crowding, dwell/loitering, after-hours presence, and perimeter rules.
3. Define abnormal gathering using explicit location/count/duration/schedule criteria.
4. Configure break zones, permitted durations, and escalation policies. The PDF's 45-minute query is an example, not a universal default.
5. Estimate presence intervals with documented behavior for occlusion, exits, re-entry, and tracker loss.
6. Use named employee results only when a permitted and sufficiently reliable identity link exists. Otherwise provide anonymous observations.
7. Implement evidence-linked break searches and reports, including missing-coverage uncertainty.

Exit gate: each schedule-based behavior works across midnight and exceptions; approximate durations remain labeled approximate.

**Stage 17 — Implement asset, material, and tool workflows**

1. Register protected shelves, tool boards, assets, loading zones, and controlled movement routes.
2. Define authorized baseline changes and distinguish inventory changes from camera movement or occlusion.
3. Implement removal, return, and left-behind events with persistence and evidence context.
4. Add material movement rules by direction, schedule, and zone.
5. Integrate the actual tool issue/return or ERP interface where required.
6. Select RFID, QR/barcode, BLE/UWB, smart-cabinet, or tool-vending support according to the identity problem. The PDF does not require every technology simultaneously.
7. Build named-tool recognition only with appropriate data and camera detail; similar serialized tools may require tags.
8. Add searches for last observation, removal candidates, nearby access events, and recorded investigator findings.

Exit gate: shadows, rearrangement, occlusion, and legitimate issue/return are included in testing; an image change is never silently promoted to proof of theft.

**Stage 18 — Develop and validate advanced analytics**

Implement these as separate measurable capabilities, not as labels in a generic object detector.

| Analytic | Candidate approach to evaluate | Critical negative examples/limitations |
|---|---|---|
| Fall/prone person | Person/pose trajectory plus temporal action analysis | Bending, kneeling, floor work, assisted movement, occlusion |
| Possible fight | Temporal interaction/action model | Handshakes, physical teamwork, animated gestures, assistance |
| Running | Calibrated motion and/or temporal action model | Perspective, camera movement, dropped frames; pixel speed is not physical speed |
| PPE | Appropriate equipment detector linked to person/zone | Hidden or too-small equipment, overlapping workers, task-specific exemptions |
| Visual smoke/flame | Scene-specific temporal visual model | Welding, reflections, dust, steam, night lighting |
| Named tool | Object recognition plus location/business identity context | Near-identical objects, tiny image size, concealed movement |
| Camera obstruction/defocus/movement | Quality metrics and scene-reference comparison | Lighting changes, darkness, legitimate maintenance |
| Other unsafe behavior | Precisely defined custom temporal rule/model | Undefined behavior cannot be reliably accepted |

For each model: define the event; obtain permitted data; annotate positives and difficult negatives; split data by camera/session/site as appropriate; train or configure; lock an independent evaluation set; measure event precision/recall and false alerts per camera-hour; analyze scene-specific failures; run in shadow mode; release only after agreed thresholds are met.

Record sample counts and uncertainty. A few successful staged events are insufficient to establish rare-event reliability. Review a sample of uneventful footage to estimate missed events; reviewing alerts alone cannot measure recall. Preserve a model card with intended use, excluded conditions, data provenance, runtime, thresholds, limitations, and rollback version. NIST AI RMF provides a useful governance and measurement structure. [NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)

Exit gate: every enabled analytic has its own site evaluation and operating limits. Required models remain outstanding deliverables until accepted; experimental status does not satisfy the full requirement.

**Stage 19 — Add evidence-grounded conversational search**

1. Define an allowlisted query schema: dates, timezone, cameras, areas, event types, durations, priorities, case status, and correlation state.
2. Translate English into that schema and validate it before execution. Show interpreted filters; clarify material ambiguity.
3. Execute authorized, parameterized searches. Do not grant the language model arbitrary SQL, filesystem, or camera administration access.
4. Generate answers only from retrieved records; link each material event claim to its evidence.
5. Compute totals and durations deterministically. Explain incomplete recording or analytic coverage.
6. Support follow-up filters while rechecking current permissions on every request.
7. Separate detector hypotheses, sensor records, and approved investigator conclusions; attribute a finding to its reviewer.
8. Treat camera names, notes, imported records, and retrieved text as untrusted data, never as instructions to the assistant.
9. Log prompt, interpreted query, authorized retrieval references, answer, model version, and any approved action; apply retention and access controls to these logs.
10. Maintain a regression set of ordinary, ambiguous, adversarial, empty-result, and permission-restricted queries.

Retrieval does not eliminate prompt injection. Restricting capabilities and enforcing permissions outside the model are necessary design controls. [OWASP prompt injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)

Exit gate: answers are supported by accessible evidence; unsupported requests are explained; malicious retrieved text cannot expand access or trigger operations.

**Stage 20 — Add voice, Tamil, and polished reports**

1. Implement push-to-talk English commands with a visible recording indicator and transcript correction.
2. Evaluate local speech recognition against actual workplace noise, accents, camera names, and terminology.
3. Pass the transcript through exactly the same authorization and query pipeline as typed requests.
4. Add optional spoken responses, with controls for sensitive details in shared spaces.
5. Define command-audio retention separately from ambient workplace audio, which stays disabled by default.
6. Add Tamil and mixed-language support at the agreed later milestone. The PDF has inconsistent phase numbering for Tamil; resolve that in the release scope.
7. Test localized dates, timezones, names, report labels, and fonts.
8. Keep deterministic report facts distinct from generated summaries and reviewer conclusions.

Faster-whisper is one local transcription candidate; its documented hardware/runtime requirements and model performance must be verified for the chosen deployment. [faster-whisper](https://github.com/SYSTRAN/faster-whisper)

Exit gate: voice commands preserve meaning, permissions, evidence references, and acceptable response time on the target hardware.

**Stage 21 — Size and harden for the target camera count**

1. Benchmark 1 → 4 → 8 → 16 → 32 streams, preserving the same architecture and recording actual configuration.
2. Include camera decode, tracking, all enabled models, recording, live viewers, playback, exports, and search in the workload.
3. Measure p50/p95/p99 latency, peak and sustained resources, dropped analytic frames, recording gaps, and queue age.
4. Add workers based on bottlenecks. Reserve capacity for critical rules; limit batch analysis, exports, and language models.
5. Measure main and substream bandwidth, browser fan-out, storage reads/writes, and recovery traffic.
6. Partition large tables or introduce additional search infrastructure only when measurements justify it.
7. Verify service supervision, restart limits, file descriptor limits, bounded logs, and disk reserve.
8. Determine whether the availability target requires a standby recorder/database or additional node. Multi-node failover needs single-writer ownership and split-brain prevention.

Storage calculation in decimal units:

`GB/day = camera_count × average_Mbps × 10.8`

At 4 Mbps average per camera, eight cameras require about 345.6 GB/day, 16 need 691.2 GB/day, and 32 need 1,382.4 GB/day. Thirty days are approximately 10.37 TB, 20.74 TB, and 41.47 TB respectively, before overhead, evidence, reserve, and RAID parity. Illustratively, dividing the 16-camera raw requirement by 0.8 to retain 20% free capacity gives 25.92 TB usable before extra copies/overhead; raw purchased disk capacity must also account for redundancy. Average bitrate changes with scene, codec, quality, and motion: measure it.

Do not promise 32 streams because a detector processes a certain number of small images per second. Decode, memory transfers, other models, recording, clients, and reliability overhead also consume resources.

Exit gate: measured peak and sustained workloads meet accepted targets with documented headroom and overload behavior.

**Stage 22 — Package deployment, backup, recovery, and upgrades**

1. Build an offline-installable release bundle with required images, packages, models, assets, checksums, and license notices.
2. Configure local identity, DNS/time dependencies, certificates, service startup, and firewall rules. Document allowed traffic between camera, application, storage, operator, and management networks.
3. Use unique device credentials and least-privilege service accounts. Protect control APIs and diagnostic endpoints.
4. Implement secure backups for database, configuration, approved evidence, model manifests, audit records, and encryption-key recovery material.
5. Decide whether ordinary continuous footage is backed up separately, replicated, or protected through another agreed mechanism; a metadata backup does not back up video.
6. Define recovery time objective (how soon service returns) and recovery point objective (how much data loss is acceptable) per component.
7. Restore onto a clean host and verify references, permissions, media decryptability, timelines, and audit continuity.
8. Use versioned migrations and tested rollback/recovery. Keep old models available for rollback; evaluate model upgrades separately from ordinary UI changes.
9. Integrate UPS runtime, orderly shutdown, and restart sequence across switches, cameras, storage, servers, firewall, and gateways.
10. Disconnect public internet and verify local login, recording, inference, response, and dashboard. Report unavailable external notification routes honestly.

PostgreSQL point-in-time recovery requires a compatible base backup and the necessary continuous WAL sequence. It does not recover your separately stored media or manually managed configuration automatically. [PostgreSQL PITR](https://www.postgresql.org/docs/current/continuous-archiving.html)

Exit gate: a clean recovery and a failed-upgrade recovery have both been performed successfully with recorded timings.

**Stage 23 — Complete formal qualification**

1. Run requirement-linked functional tests for every required and contracted conditional feature.
2. Run cross-role and cross-camera authorization tests across all media, searches, reports, and exports.
3. Conduct security review and appropriate independent penetration testing; resolve release-blocking findings.
4. Validate every analytic on unseen site-representative data and publish separate miss/false-alert measurements.
5. Run concurrency and long-duration endurance tests at target camera and user load.
6. Inject camera loss, network interruption, corrupt media, clock drift, full storage, database/broker outage, GPU-worker failure, notification-provider failure, and reboot.
7. Verify durable deadlines and retry behavior: worker termination after a send but before acknowledgement is a particularly important duplicate-action scenario.
8. Test retention while evidence jobs, exports, and holds are active.
9. Verify alarms still appear with missing video and recording continues with failed analytics.
10. Repeat required recovery, offline-operation, and upgrade tests on the release candidate.
11. Record known limitations and rejected operating conditions. A failure is not erased by removing its test from the report.

Exit gate: the release candidate has a complete test report, reproducible configuration, accepted limits, and no unresolved release-blocking defect.

**Stage 24 — Commission the eight-camera pilot, accept, and operate**

1. Follow the PDF's proposed allocation: two entry/exit, two workshop, one canteen, two stores/tool-room, and one loading/outdoor camera, adjusted through site design approval.
2. Verify each camera's view, time, recording, retention, zones, quality, privacy boundaries, and network access.
3. Start new AI alerts in shadow/review mode while keeping independent safety systems operational. Approved sensor integration may have a different commissioning sequence agreed by the site team.
4. Train operators using actual acknowledgement, investigation, escalation, evidence, and fault workflows.
5. Run the 30–60-day review cycle from the PDF. Measure false alerts, misses through sampling, response delays, camera angles, storage consumption, and GPU load.
6. Tune thresholds and coverage, then re-test changes on held-out data. Do not repeatedly tune against the final acceptance set.
7. Perform witnessed Site Acceptance Tests for hardware-dependent functions and sign off each requirement.
8. Deliver as-built drawings, inventory/BOQ, API documentation, licenses, model limitations, manuals, security configuration, backups/recovery procedures, and training records.
9. Assign ongoing owners for incidents, infrastructure faults, security patches, firmware, certificates, backups, model drift, and support escalation.
10. Expand to 16/32 cameras only after capacity and operational acceptance remain satisfied.

Exit gate: the deployment is accepted for a defined site, scope, configuration, and operating envelope. Industry readiness is maintained through support and controlled changes, not awarded permanently by finishing a feature list.

**Testing detail: the minimum scenario catalog**

| Scenario | Required observable outcome |
|---|---|
| Camera disconnects | Loss detected within target; recording gap visible; reconnection automatic |
| Live view works but disk writes fail | Recording-specific fault; live status does not hide lost evidence |
| AI worker crashes | Recording continues; analytics marked degraded; worker recovery does not duplicate incidents |
| Event occurs near a segment boundary | Correct evidence interval assembled or precise missing coverage reported |
| Storage fills with held evidence | No unauthorized deletion; visible critical fault and defined degradation |
| Event export during retention cleanup | Consistent authorized evidence, no silent partial package |
| Two operators acknowledge together | Consistent case state and clear audit history |
| Notification worker restarts | Deadlines resume; bounded retry; duplicate effects controlled |
| Badge feed stops | Source-unavailable state instead of mass unauthorized-entry accusations |
| Camera clock moves backward | Source time preserved, uncertainty reported, intervals not silently merged |
| User loses camera permission | Active/new playback and search access revoked according to defined session policy |
| Malicious text appears in a note | Search treats it as evidence data; no permission expansion or action |
| Question has no indexed coverage | Answer explains lack of coverage rather than asserting no incident occurred |
| Database restored before media state | Reconciliation identifies missing/orphan media and prevents false completeness |
| Internet is disconnected | Required local functions continue; external delivery failures shown |
| Full server fails | Independent monitoring detects it; documented recovery/failover starts |
| Model update worsens one scene | Regression catches it or monitored rollback restores the accepted version |

**How to evaluate AI without misleading accuracy numbers**

Define an event matching window and count duplicates consistently. Precision is confirmed correct alerts divided by all evaluated alerts. Recall is detected reference events divided by all reference events. Report false alerts per camera-hour and detection delay alongside these. For occupancy, measure count error; for duration, measure interval error and coverage; for tracking, measure ID fragmentation/switches where relevant. Keep metrics by use case and scene type.

Do not infer recall from incident reviews alone: reviewers only see what alerted. Use independent annotation of representative footage and controlled scenarios. Include confidence intervals or at least sample sizes and uncertainty. A detector score is not a calibrated probability of an incident, and neither is a probability of wrongdoing. Sensor alarms may have no AI confidence at all.

**Professional API and configuration expectations**

Use versioned endpoints and typed contracts for cameras, zones, schedules, incidents, acknowledgements, evidence, exports, searches, health, and integrations. Long operations return a job identifier and observable progress/error state. Use cursor pagination, request identifiers, validated timestamps, idempotency for retried actions, and consistent error responses. Protect diagnostics and redact credentials. Document supported API versions and connector compatibility.

Configuration changes should validate before activation, produce audit history, retain the previous version, and expose whether they have reached workers. Moving a camera invalidates existing zone calibration and possibly AI validation; require rechecking rather than silently continuing with an obsolete layout.

**What to begin with: the first 15 development tickets**

1. Create the requirement register and acceptance target definitions.
2. Create the new repository and reproducible development configuration.
3. Record the initial architecture and component/license decisions.
4. Create PostgreSQL schema migrations for sites, cameras, users/scopes, and audit.
5. Implement local login, MFA policy, and server-side camera authorization.
6. Create the camera inventory and configuration interface.
7. Connect a recorded test source, clearly labeled, and one real camera when available.
8. Record and index segments independently of the web application.
9. Implement authorized playback with visible gaps.
10. Add camera/recorder health and automatic reconnection.
11. Implement zone/line configuration and versioning.
12. Add an evaluated person detector, tracker, and directional crossing rule.
13. Create the incident, evidence reservation, snapshot, and clip jobs.
14. Add assignment, acknowledgement, durable escalation, review, and export.
15. Test the complete workflow, restarts, outages, permissions, and retention before adding more detectors.

**People, time, and budget planning**

Assign ownership for product/site requirements, backend/data, frontend/video UX, video/inference, infrastructure/security, QA, and field integrations. One person may cover several roles during development, but field wiring and safety-system commissioning need the responsible qualified personnel. Independent security/acceptance review is valuable even if the core team is small.

The full scope is a multi-month engineering and field-validation program, not a defensible fixed number of days based on the PDF alone. A delivery date requires team capacity, procurement lead times, model/data readiness, and actual integration interfaces. Estimate stages after the first complete camera-to-case workflow and revise using measured throughput. The PDF itself calls for a 30–60-day pilot review; that observation period cannot be established by a short demo.

Budget separately for cameras and installation; PoE/network/VPN/UPS; recording disks and backups; inference hardware; model and software licenses; gateway/connector work; data labeling; test equipment; security testing; training; and ongoing support. Obtain current quotes after site sizing. Do not allocate the entire budget to the GPU and discover later that retention, field installation, and maintenance are unfunded.

**Research sources and interpretation**

The supplied PDF is the requirements authority. The earlier complete analysis is a convenience catalog containing 91 consolidated capabilities; those identifiers are analytical labels, not official PDF requirement IDs. This document's architecture, schema, sequencing, and verification details are proposed engineering decisions.

Primary documentation consulted includes ONVIF profiles and its conformant product registry; MediaMTX routing/authentication documentation; FFmpeg licensing; ONNX Runtime CUDA support; NVIDIA DeepStream performance documentation; original ByteTrack and RT-DETR repositories; Ultralytics licensing; FastAPI worker guidance; PostgreSQL recovery; RabbitMQ reliability; Keycloak application integration; Prometheus/OpenTelemetry; faster-whisper; OWASP ASVS and prompt-injection guidance; and NIST SSDF/AI RMF. Links appear beside the relevant decisions. Specifications and product docs do not constitute an independent benchmark, a procurement quote, a legal determination, or a promise of detection accuracy.

The remaining site-specific decisions are camera availability, camera placement, accepted error rates, notification policy, retention/hold periods, recovery objectives, permitted identity associations, actual gateway protocols, Tamil delivery milestone, supported browsers, exact workload, and final support arrangements. Development can start while these are recorded and resolved; production acceptance cannot bypass them.


**Complete feature-to-stage traceability — all 91 capabilities**

The IDs match the earlier requirements analysis. The table preserves its requirement classifications. Stages 23 and 24 verify/accept all applicable features in addition to the implementation stages shown. Shared security, data, and monitoring controls apply throughout.

| ID | Capability and requirement classification | Build stages |
|---|---|---|
| A01 | Multi-camera live dashboard - Required | 9, 21 |
| A02 | Camera organization by location - Required | 5, 7, 9 |
| A03 | Continuous and policy-based recording - Required | 8 |
| A04 | Shared time synchronization - Required | 7 |
| A05 | Timeline playback with event markers - Required | 8, 9 |
| A06 | Pre-event and post-event clips - Required | 12 |
| A07 | Snapshots and evidence context - Required | 12 |
| A08 | Evidence retention and incident preservation - Required | 8, 12 |
| A09 | Controlled evidence export - Required | 6, 12 |
| A10 | Secure local web and mobile-compatible access - Required | 6, 9, 22 |
| B01 | Person and vehicle detection - Required | 11 |
| B02 | Directional entry/exit line crossing - Required | 11 |
| B03 | Access-control record integration - Conditional | 15 |
| B04 | Tailgating detection - Required; integration-dependent when using access records | 15 |
| B05 | Visible person with no matching credential event - Conditional on access integration | 15 |
| B06 | Credential event with no visible person - Conditional on access integration | 15 |
| B07 | Unauthorized and after-hours entry - Required | 11, 15, 16 |
| B08 | First-entry, last-exit and attendance exception reports - Required | 15 |
| B09 | Break and shift rule configuration - Required | 16 |
| B10 | Approximate long-break detection - Required | 16 |
| B11 | Break-exception evidence search - Required | 14, 16, 19 |
| B12 | Occupancy and presence visibility - Required at the stated areas | 16 |
| C01 | Potential fighting or aggressive physical interaction - Required | 18 |
| C02 | Falls and people lying on the floor - Required | 18 |
| C03 | Running in prohibited areas - Required | 18 |
| C04 | Crowding detection - Required | 16 |
| C05 | Abnormal gathering detection - Required, but underdefined | 16, 18 |
| C06 | Loitering detection - Required | 16 |
| C07 | After-hours presence monitoring - Required | 16 |
| C08 | Restricted-zone and safety-exclusion intrusion - Required | 11 |
| C09 | Perimeter breach detection - Required | 16 |
| C10 | PPE compliance - Conditional / Advanced | 18 |
| C11 | Other unsafe-behavior rules - Required as a scope category, not a defined universal detector | 1, 18 |
| C12 | Incident evidence and review record - Required | 12 |
| D01 | Protected shelf, rack and tool-board monitoring - Required | 17 |
| D02 | Object removal detection - Required | 17 |
| D03 | Tool or asset return events - Required in tool-room scope | 17 |
| D04 | Object left behind - Required | 17 |
| D05 | Unusual asset, material and loading movement - Required, with site-defined rules | 17 |
| D06 | Asset movement correlation with business records - Conditional / Advanced integrations | 17 |
| D07 | Named tools and unique asset identification - Advanced / Conditional | 17, 18 |
| D08 | Theft investigation search - Required | 14, 17, 19 |
| E01 | Fire-panel or gateway integration - Required | 13 |
| E02 | Alarm-to-camera mapping and emergency display - Required | 9, 13 |
| E03 | External safety and security signal integration - Required support; actual connections depend on site equipment | 13 |
| E04 | Visual smoke/flame early warning - Conditional | 18 |
| E05 | Emergency evidence capture - Required | 12, 13 |
| E06 | Local audible and physical notification - Required local alert; physical relay conditional | 9, 13 |
| E07 | External messaging and optional mobile push - Conditional channels / Optional push | 13 |
| F01 | Typed English commands - Required | 19 |
| F02 | Spoken English commands and transcription - Required in full scope | 20 |
| F03 | Video metadata and event indexing - Required | 5, 14 |
| F04 | Historical evidence search - Required | 11, 14 |
| F05 | Evidence-grounded answer cards - Required | 19 |
| F06 | Follow-up conversation - Required | 19 |
| F07 | Summaries and daily incident reports - Required | 14, 19, 20 |
| F08 | Text and voice responses - Required in full scope | 19, 20 |
| F09 | Tamil and mixed English/Tamil support - Optional / later phase | 20 |
| F10 | Query audit, uncertainty and authorized conclusions - Required | 6, 19 |
| G01 | Four-level alarm classification - Required | 13 |
| G02 | Complete alert record - Required | 5, 12 |
| G03 | Assignment and acknowledgement - Required | 12 |
| G04 | Timed automatic escalation - Required for unacknowledged Critical alerts; also configurable for other classes | 13 |
| G05 | Configurable routing rules - Required | 13 |
| G06 | Incident investigation and approved closure - Required | 12 |
| G07 | Daily operational alarm dashboard - Required | 9, 14 |
| G08 | Delivery tracking and maintenance-ticket integration - Required delivery visibility / Conditional ticket connection | 10, 13 |
| H01 | Camera online, stream and recording continuity - Required | 7, 8, 10 |
| H02 | Visual camera degradation and tampering - Required | 10, 18 |
| H03 | Camera power, network and stream telemetry - Required where data is available | 10 |
| H04 | Server, AI service and hardware health - Required | 10 |
| H05 | Storage capacity warnings - Required | 8, 10 |
| H06 | Maintenance workflow and critical-zone urgency - Required | 10 |
| H07 | Monthly health and incident-response reports - Required | 10, 14 |
| I01 | Role-based permissions - Required | 6 |
| I02 | MFA, VPN and unique credentials - Required | 6, 22 |
| I03 | Encryption and secure communications - Required | 6, 22 |
| I04 | Protected audit records - Required | 6 |
| I05 | Privacy-sensitive camera placement - Required | 2, 6, 24 |
| I06 | Ambient audio disabled by default - Required | 6, 20 |
| I07 | Face recognition disabled by default - Required control; activation conditional | 6 |
| I08 | Human review before high-impact decisions - Required | 1, 6, 12, 19 |
| I09 | Secure backup and disaster recovery - Required | 22 |
| I10 | Patching, firmware and retention administration - Required | 6, 8, 22, 24 |
| J01 | Local processing and internet-outage operation - Required | 3, 22, 23 |
| J02 | Segregated camera/AI network - Required | 2, 22 |
| J03 | Camera and video-system interoperability - Required baseline; enhanced support recommended | 3, 7 |
| J04 | Expansion to at least 32 cameras - Required | 3, 21 |
| J05 | Resilient recording and separated storage roles - Required architecture; hardware details as specified | 3, 8, 21, 22 |
| J06 | Power continuity - Required | 2, 22, 24 |
| J07 | Integration interfaces and extensibility - Required | 3, 5, 13, 15, 17 |
