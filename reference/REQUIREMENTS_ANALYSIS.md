# AI Video Intelligence & Workplace Safety
## Complete feature analysis and hackathon planning report

Prepared 12 October 2026 | Analysis of the supplied seven-page requirements specification

This report explains the complete requested system, groups repeated requirements into individual capabilities, identifies their dependencies and limitations, and proposes a practical hackathon demonstration. It is an analysis of the supplied document, not a claim that the system has been built or tested.

## 1. Executive assessment

The problem is to turn workplace camera footage and safety-system signals into timely, searchable, reviewable evidence. The requested product combines a video management system, configurable camera analytics, access and asset-record integrations, emergency alert handling, incident management, system-health monitoring, and an evidence-grounded conversational assistant.

The central workflow is: observe an event, preserve its evidence, correlate relevant records, notify an authorized responder, escalate if necessary, investigate, and close the case with a documented human decision. The AI assistant makes the same evidence easier to find; it must not invent incidents, identities, or accusations.

The deployment is primarily on company premises. Recording, monitoring, analytics, local alerts, and the dashboard must continue during an internet outage. The design must grow from 8-16 cameras to at least 32 without replacing the core architecture. This is a production system specification, including equipment, installation, testing, documentation, training, and support, rather than merely a request for an AI model or chatbot. [Source: cover; sections 1, 7, 11-15, pp. 1-2, 4-7.]

The most consequential boundaries are explicit: camera analytics support official attendance rather than replacing payroll; visual suspicion is not proof of theft; approved fire and life-safety systems remain independent; face recognition and ambient audio recording are disabled by default; and significant HR, security, safety, and disciplinary decisions require authorized human review. [Source: sections 3.2, 3.4-3.5, 4, 10.]

### How to read the feature catalog

- **Required:** an explicit baseline capability or control in the source. Some requirements still need site-specific settings.
- **Conditional:** specified when an integration, approval, camera capability, or suitable site condition exists. It is not automatically enabled everywhere.
- **Advanced:** explicitly placed in a later implementation phase or described as custom functionality.
- **Optional:** explicitly optional in the source.
- **Proposed:** this report's implementation, testing, or hackathon advice. It is not an additional organizer requirement.

Each catalog entry explains the feature's behavior, expected output, dependencies, and an important limitation. Feature IDs are this report's tracking labels, not IDs from the original PDF. Repeated mentions are consolidated. Hardware and delivery obligations are covered separately because they are requirements but are not all user-facing software features. References use the original PDF's printed page and section numbers.

### What this analysis does and does not assume

The only requirements authority used here is the supplied PDF. Its final instruction to a technical team is treated as part of the scope to analyze, not as an instruction to purchase, install, or submit anything on your behalf. No hackathon duration, team size, budget, judging rubric, available GPU, available footage, or site jurisdiction was supplied. The demo scope is therefore a proposed priority order, not a promise about delivery time or competition scoring. Hardware figures below reproduce the source; they are not a current procurement recommendation or independently verified performance guarantee.

## 2. Users, areas, and the product they need

### Proposed user roles

The source requires authorized users, responders, reviewers, administrators, and technicians, but does not prescribe a complete role matrix. A practical starting point is:

| Role | Main work | Permission boundary to define |
| --- | --- | --- |
| Security operator | Watch cameras, acknowledge alarms, investigate access and asset events | Assigned cameras and cases; export only if granted |
| Safety officer | Review safety events and emergency response | Relevant safety zones, escalation and closure authority |
| Operations supervisor | Review occupancy, break exceptions and daily activity | Approved operational views; no automatic employee penalties |
| Investigator or authorized manager | Review evidence, add findings, approve final disposition | Sensitive footage and conclusion privileges explicitly granted |
| Maintenance technician | Repair camera, recording, network and storage faults | Health data and assigned work; video access only when needed |
| Administrator | Manage users, integrations, rules and system configuration | MFA and protected audit trail; administrator access is not a reason to bypass audit |
| HR or attendance reviewer | Reconcile approved attendance exceptions | Official attendance remains authoritative; identity linkage must be justified |

### Complete area-to-feature mapping

| Area from the PDF | Features expected in that area |
| --- | --- |
| Entry and exit | Person/vehicle detection; directional crossing; tailgating; access-record correlation; unauthorized access; attendance support |
| Workshop/work areas | Presence; configured PPE; restricted zones; falls; potential aggression; crowding; defined unsafe behavior |
| Offices/corridors | Occupancy/security; after-hours presence; intrusion; loitering; camera health |
| Canteen/break areas | Occupancy; crowding; approximate long-break exceptions; potential fights and falls |
| Stores/warehouse | After-hours access; removal and left-behind objects; material movement; theft investigation support |
| Tool room/tool crib | Tool-board monitoring; removal/return; unusual movement; custom tool recognition and asset-system correlation |
| Loading/parking/external yard | Vehicles and people; loading activity; intrusion; configured safety events |
| Secure/restricted rooms | Unauthorized entry; door-event correlation; after-hours presence; tamper alerts |

Every camera needs configurable lines, directions, and zones, including restricted areas, tool racks, safety-exclusion areas, breaks, emergency routes, and loading/unloading areas. Defining an emergency-route zone does not, by itself, specify an automatic blocked-exit detector. Such a detector would need an additional agreed rule. [Source: section 2, p. 2.]

## 3. Complete feature catalog

### A. Viewing, recording, playback, and evidence

**A01. Multi-camera live dashboard - Required.** Shows simultaneous live video in 1, 4, 9, 16, or 25-camera layouts, with a full-screen individual view. Operators use it to assess what is happening now. It needs camera streams and a video delivery layer; a layout existing in the interface does not prove it can play that many streams smoothly. Verify performance using the intended camera count. [3.1, p. 2.]

**A02. Camera organization by location - Required.** Groups cameras by workplace area and labels them with meaningful camera and location names. A responder can move directly from a Stores alarm to the relevant view. It depends on a maintained camera/zone inventory, and all event, playback, search, and health views should refer to the same identifiers. [2, 3.1, pp. 2-3.]

**A03. Continuous and policy-based recording - Required.** Records all footage continuously or according to configured recording policies. Produces a retained video history for playback, evidence extraction, and later analysis. It depends on the VMS/NVR, storage, schedules and stream availability. The specification does not define the exact policy options or the treatment of gaps; these need agreement. [3.1, p. 2; 8.3, p. 5.]

**A04. Shared time synchronization - Required.** Keeps cameras, servers, the recorder, access control and alarm systems on synchronized time using NTP. This allows a badge swipe, camera event and fire signal to be compared meaningfully. Store event time and source identity consistently; allowed clock drift, display timezone and behavior after clock corrections are unresolved details. [3.1, p. 2; 7, pp. 4-5.]

**A05. Timeline playback with event markers - Required.** Lets users navigate recorded video by time and jump to indexed events. Markers distinguish relevant moments from uneventful footage. Playback must retain the source camera and timestamp context. Missing recording segments should be visible rather than silently represented as continuous coverage; that gap display is a proposed implementation safeguard. [3.1, p. 2.]

**A06. Pre-event and post-event clips - Required.** Preserves footage from before and after a detected event or external alarm, so a reviewer sees context rather than only a trigger frame. It needs a recording buffer or access to the recorder. The source does not specify clip lengths; configure them by use case and label incomplete clips when earlier footage is unavailable. [3.1, 3.3, 3.5, pp. 2-3.]

**A07. Snapshots and evidence context - Required.** Attaches a still image, time, camera, location, event classification and AI confidence to events. This supports fast triage before opening a clip. Confidence describes an analytic result, not certainty of wrongdoing. A hardware alarm may have no AI score; preserve that distinction instead of fabricating a percentage. [3.1, 3.3, 5, pp. 2-4.]

**A08. Evidence retention and incident preservation - Required.** Retains incident evidence alongside the event and investigation history. It must coexist with ordinary video-retention policies, so important case material is not accidentally lost during routine rotation. The document does not specify case retention length or hold/release behavior; these should be agreed with the client. [1, 3.1, 10, 13, pp. 2, 6-7.]

**A09. Controlled evidence export - Required.** Allows authorized users to export watermarked video and an evidence package containing the relevant event and review context. Export actions must be auditable. Watermarking alone is not a complete integrity mechanism; package manifests and cryptographic hashes would be proposed strengthening measures, not explicitly specified features. [3.1, 3.3, 12, pp. 2-3, 6.]

**A10. Secure local web and mobile-compatible access - Required.** Gives authorized users a browser dashboard usable from internal desktop and mobile devices. Remote access is through authorized VPN arrangements. Mobile compatibility does not imply a required native phone app; optional push notification is a separate capability. [1, p. 2; 7, pp. 4-5.]

### B. People, access, attendance, and breaks

**B01. Person and vehicle detection - Required.** Identifies people and vehicles in configured camera views to support gates, yards, presence and movement rules. Output is an object observation or event with time and location. Detecting a person does not identify the employee; identity requires another permitted source. Camera position, lighting and occlusion affect results. [2, p. 2.]

**B02. Directional entry/exit line crossing - Required.** Detects a person crossing a virtual boundary and logs direction, time, camera, snapshot and clip. This supports entry/exit histories and can underpin counts. It requires a configured line and short-term movement tracking; standing on the line or turning back needs an agreed debounce rule to avoid duplicate crossings. [2, 3.2, p. 2.]

**B03. Access-control record integration - Conditional.** Imports card, QR, RFID, badge or approved biometric access events when available. Correlation can link a recorded crossing with an authorized credential event. It depends on device interfaces, employee/credential mapping and synchronized time. A badge association is supporting evidence, not proof that a particular person used it. [3.2, p. 2.]

**B04. Tailgating detection - Required; integration-dependent when using access records.** Flags a possible extra person following an authorized entrant through an access point. It compares observed passage with the site's authorization rule or available credential events. Group entry, visitors and obscured doorways need explicit handling. The result is a possible access exception for review. [2, 3.2, p. 2.]

**B05. Visible person with no matching credential event - Conditional on access integration.** Flags a crossing that has no matching access record within a configured time window. Output includes video and the correlation status. A missing or delayed access feed can cause the same symptom as unauthorized entry; the interface should distinguish integration failure from a confirmed mismatch. [3.2, p. 2; 4, p. 4.]

**B06. Credential event with no visible person - Conditional on access integration.** Finds a badge or other access event for which no corresponding person was observed. This helps review access irregularities or sensor/camera issues. Camera outages, poor angles and latency must be considered before drawing conclusions. Use separate statuses for unmatched, unavailable and uncertain evidence. [3.2, p. 2.]

**B07. Unauthorized and after-hours entry - Required.** Flags entry inconsistent with access permissions, a restricted location or a permitted schedule. It combines location, time and available authorization records. After-hours presence alone is not proof of unauthorized access: approved overtime, cleaners, contractors and emergency responders may be exempt. [2, 3.2-3.4, pp. 2-3.]

**B08. First-entry, last-exit and attendance exception reports - Required.** Summarizes observed first arrival, last departure and discrepancies for authorized review. Named employee reports depend on approved identity linkage and adequate camera coverage. The official attendance/payroll system remains authoritative; missed sightings cannot automatically become absence, salary deductions or discipline. [3.2, p. 2; 10, p. 6.]

**B09. Break and shift rule configuration - Required.** Defines break areas, shift hours, standard durations, grace periods, exemptions and escalation rules. These settings determine when a duration becomes an exception. The source gives no universal allowed break length: its 45-minute query is an example, not a default policy. [3.2, pp. 2-3.]

**B10. Approximate long-break detection - Required.** Estimates how long a person remains in a configured break area and flags a duration beyond policy. It needs reliable entry/exit observations or tracking across the area. Occlusion, re-entry and track loss can make duration approximate; named results also require an approved identity association. [2, 3.2, pp. 2-3.]

**B11. Break-exception evidence search - Required.** Retrieves cases such as people observed in the canteen for more than a requested duration on a selected day. Returns the supporting time interval and footage, not an unsupported claim about productivity. If identity is unknown, show anonymous event/track results and explain the missing linkage. [3.2, p. 3.]

**B12. Occupancy and presence visibility - Required at the stated areas.** Shows observed presence and occupancy in work, office and canteen zones and supplies inputs for crowding rules. Counts are estimates where people can be occluded or use unmonitored entrances. The source does not require reliable whole-building headcount or an emergency evacuation roll call. [2, p. 2.]

### C. Safety, incidents, and abnormal activity

**C01. Potential fighting or aggressive physical interaction - Required.** Flags visual activity consistent with a possible fight and provides immediate evidence for a responder. It requires temporal analysis rather than an isolated image alone. Normal work, vigorous gestures or people assisting someone can resemble aggression; the event must remain a hypothesis pending review. [3.3, p. 3.]

**C02. Falls and people lying on the floor - Required.** Detects a possible fall or prone person and raises a potential medical-emergency alert with context. It depends on suitable visibility and behavior analysis. A person bending, working under equipment or lying down intentionally can create false alerts; detection is not a medical diagnosis. [3.3, 3.5, p. 3.]

**C03. Running in prohibited areas - Required.** Flags movement that meets a running rule in zones where running is prohibited. Rules must specify location and temporal behavior. Apparent image speed changes with camera perspective, so simple pixel-speed thresholds need calibration and cannot automatically be treated as physical speed. [3.3, p. 3.]

**C04. Crowding detection - Required.** Raises an event when estimated occupancy or density exceeds a configured threshold in a zone. Output includes the affected location, time and footage. The client must define thresholds, persistence and exemptions; the specification supplies no universal crowd size. [2, 3.3, pp. 2-3.]

**C05. Abnormal gathering detection - Required, but underdefined.** Flags gatherings that violate a site-defined pattern, duration, place or schedule. It is distinct from crowding: a small gathering in a restricted location may matter even below a density limit. Normal meetings and shift handovers must be represented in the rule or reviewed as exceptions. [3.3, p. 3.]

**C06. Loitering detection - Required.** Flags a person or group remaining in a configured zone beyond a dwell-time threshold. Uses tracking, area boundaries and allowed schedules. Queueing, waiting for loading, assigned stationary work and breaks are legitimate activities that need exclusions. Dwell time is uncertain if the track is lost. [2, 3.3, pp. 2-3.]

**C07. After-hours presence monitoring - Required.** Detects people present in an area outside approved operating hours, even if the actual entry was not observed. It uses zone and schedule rules, plus exceptions where available. Presence and entry are different event types and should remain distinguishable in the database and search results. [2, 3.3, pp. 2-3.]

**C08. Restricted-zone and safety-exclusion intrusion - Required.** Alerts when a person enters a configured protected or unsafe area. The output identifies the violated zone and evidence interval. It depends on accurately drawn boundaries and site policy. Camera zones alone do not establish who is authorized unless identity or access information is available. [2, 3.3-3.4, pp. 2-3.]

**C09. Perimeter breach detection - Required.** Detects a person or vehicle crossing a defined perimeter or entering a protected external zone. Direction and permitted routes matter. Lighting, rain, shadows, moving vegetation and blind spots need testing. Severity is normally High or Critical according to the site's policy and incident context. [3.3, 3.5, 5, pp. 3-4.]

**C10. PPE compliance - Conditional / Advanced.** Checks configured protective equipment in relevant work zones, such as whichever helmet or vest categories the client approves. The document does not enumerate required PPE classes. It needs suitable image scale, labeled examples and zone-specific rules; distant or hidden equipment should be marked uncertain rather than automatically absent. [2, p. 2; 11 phase 5, p. 6.]

**C11. Other unsafe-behavior rules - Required as a scope category, not a defined universal detector.** Supports specific agreed unsafe acts beyond the named events. The phrase is too broad to implement or test as written. Each additional behavior needs a precise definition, footage examples, expected response and acceptance test before it becomes a deliverable analytic. [2, p. 2.]

**C12. Incident evidence and review record - Required.** Converts a detected incident into a timestamped event with classification, confidence, pre/post clip, snapshot, acknowledgement, case status, reviewer notes and exportable evidence. It is the shared wrapper for analytics, so every detector does not need its own separate incident-management implementation. [3.3, p. 3.]

### D. Asset movement and theft investigation support

**D01. Protected shelf, rack and tool-board monitoring - Required.** Defines the storage regions or item positions to observe, including shelves, racks, material areas and tool boards. It supplies the spatial reference for removal and return events. Expected contents and legitimate rearrangements must be configured; a zone alone does not identify the exact tool. [2, 3.4, pp. 2-3.]

**D02. Object removal detection - Required.** Flags disappearance or movement of an object from a configured protected location. Produces the approximate removal time and supporting clip for investigation. Occlusion, lighting changes and another object covering the item can resemble removal. The output must say possible removal rather than theft. [3.3-3.4, p. 3.]

**D03. Tool or asset return events - Required in tool-room scope.** Records an item becoming present again in a monitored position and links it to the relevant history where possible. Without unique identification, this may establish only that an object or expected shape reappeared. It cannot guarantee that the identical serialized tool was returned. [2, p. 2.]

**D04. Object left behind - Required.** Flags a newly stationary object in a monitored area after a configured duration or relevant context. It supports safety and suspicious-activity review. The system needs a baseline and persistence rule; it must not infer that every parcel, bag or temporarily stored item is dangerous. [3.3-3.4, p. 3.]

**D05. Unusual asset, material and loading movement - Required, with site-defined rules.** Monitors selected assets, controlled material-transfer routes and loading/unloading activity. It can flag movement outside expected zones, directions or hours. Normal goods handling and authorized transfers need context from schedules or business records. Generic inventory accounting or shipment reconciliation is not explicitly required. [2, 3.4, pp. 2-3.]

**D06. Asset movement correlation with business records - Conditional / Advanced integrations.** Compares video events with access, RFID, QR, tool-issue, tool-management, HRMS or ERP records where integrated. Helps distinguish documented issue/return from an unexplained movement. External records may be delayed or incomplete; a missing record alone must not become a final accusation. [3.4, p. 3; 11, 15, pp. 6-7.]

**D07. Named tools and unique asset identification - Advanced / Conditional.** Supports custom recognition of selected tools or assets, with provision for RFID, barcode/QR, BLE/UWB tags, smart cabinets or tool-vending integrations for stronger item identification. These are alternative or complementary technologies, not a requirement to deploy all of them. Small, similar or hidden tools are a major camera-only limitation. [2, 3.4, pp. 2-3; 11, p. 6.]

**D08. Theft investigation search - Required.** Retrieves people entering stores after a specified time, clips around an item's last observation, or candidate removal events for an asset. Results connect video, access records and reviewer notes. A named welding-machine query works only if that asset is actually mapped or recognized; the language model cannot supply missing visual metadata. [3.4, p. 3; 4, pp. 3-4.]

### E. Fire, sensors, and emergency coordination

**E01. Fire-panel or gateway integration - Required.** Receives alarms from the Fire Alarm Control Panel through an approved dry contact, Modbus, BACnet, OPC UA, API or another approved interface. An adapter maps the signal to location and response rules. The source lists interface options; it does not require implementing every protocol. The independent approved fire system remains authoritative. [3.5, p. 3.]

**E02. Alarm-to-camera mapping and emergency display - Required.** On fire/smoke alarm, shows relevant cameras and pops up the alarm on all authorized monitoring screens. It depends on a maintained mapping from alarm sources to camera coverage. It must still show the alarm if a mapped camera is unavailable, with the missing visual coverage made explicit. [3.5, p. 3; 5, p. 4.]

**E03. External safety and security signal integration - Required support; actual connections depend on site equipment.** Ingests gas leak, hydrogen leak, high temperature, electrical panel alarm, emergency stop, intrusion alarm, panic button, forced-open door, water leak and other agreed safety signals. Preserve the original source and alarm state. Receiving an emergency-stop signal does not authorize AI to operate machinery or override an emergency stop. [3.5, p. 3; 15, p. 7.]

**E04. Visual smoke/flame early warning - Conditional.** Uses video analytics as an additional alert layer where camera technology and site conditions support it. Reflections, welding, steam, dust and lighting can cause confusion. Detection must be validated locally and must not substitute for approved smoke, heat, gas or fire protection. [3.5, p. 3.]

**E05. Emergency evidence capture - Required.** Saves pre-alarm and post-alarm clips and links them to the external signal or visual detection. Provides the sequence before and after a critical event. Preserve the distinction between sensor alarm time, AI detection time and video timestamps so responders can reconstruct what happened. [3.5, p. 3.]

**E06. Local audible and physical notification - Required local alert; physical relay conditional.** Produces dashboard pop-ups and audible warnings, with approved beacon/siren relay integration where permitted. This is central to local operation without internet. Physical outputs need an agreed cause-and-effect matrix; a software demo button is not validation of a real life-safety circuit. [3.5, p. 3; 5, p. 4; 13, p. 7.]

**E07. External messaging and optional mobile push - Conditional channels / Optional push.** Routes notifications to defined personnel through approved email, SMS, WhatsApp or secure messaging gateways; mobile push is optional. Delivery depends on channel connectivity and gateway availability. The system must report delivery state; external delivery during an internet outage cannot be assumed without an independent working route. [3.5, p. 3; 5, p. 4.]

### F. Generative AI, search, voice, and reports

**F01. Typed English commands - Required.** Accepts an authorized user's natural-language request and translates it into a search over permitted camera, event and time metadata. For example, search Stores 2 for after-hours entries on a specific date. Ambiguous locations or dates should be clarified instead of silently guessed. [4, pp. 3-4.]

**F02. Spoken English commands and transcription - Required in full scope.** Converts a user's spoken request to text before interpreting and searching it. This is a command microphone interface, not continuous workplace audio recording. Noise and unusual names can affect recognition; showing the transcript for correction is a proposed design choice. [4, p. 3; 10, p. 6.]

**F03. Video metadata and event indexing - Required.** Makes recorded observations searchable by time, camera, location, event type and correlated records. This index is what lets the assistant answer quickly across historical footage. Storing video without indexing relevant facts does not meet this requirement; missing detections limit what the assistant can retrieve. [1, 4, 11, pp. 2-3, 6.]

**F04. Historical evidence search - Required.** Retrieves matching indexed events and linked clips from a requested period, including the 30-day standard-query acceptance scenario. Recorded video must be analyzable as well as live feeds. The document does not define whether arbitrary newly uploaded footage must be accepted; do not promise that as a baseline. [1, p. 2; 4, pp. 3-4; 12, p. 6.]

**F05. Evidence-grounded answer cards - Required.** Returns timestamp, camera/location, snapshot, confidence and clickable clip for each relevant result, including access-correlation status when requested. A narrative summary should be traceable to these records. If a clip is missing or access is denied, say so instead of presenting unsupported evidence. [4, pp. 3-4.]

**F06. Follow-up conversation - Required.** Supports a second question that narrows or summarizes previous results, such as filtering a stores search to unmatched badge events. Conversation context must preserve the intended dates, cameras and permissions. Changing filters should not silently broaden access or confuse one investigation with another. [4, p. 3.]

**F07. Summaries and daily incident reports - Required.** Produces readable summaries from verified events and case records, including daily incident reports. It should distinguish detections, reviewed findings, open cases and closed cases. Counts must come from the underlying records and preserve the selected time window; text generation cannot fill in unrecorded incidents. [4, p. 3.]

**F08. Text and voice responses - Required in full scope.** Displays answer text and supports spoken responses. Evidence links and detailed results still need a visual interface. Which spoken details are appropriate in shared workspaces, and whether speech generation must work offline, should be explicitly configured and tested. [4, p. 3; 1, p. 2.]

**F09. Tamil and mixed English/Tamil support - Optional / later phase.** Extends the language interface to Tamil and mixed commands. Section 4 calls this phase 2, while section 11 places Tamil in implementation phase 5. Treat it as deferred language scope and ask which milestone is intended; do not assume it is part of the initial English baseline. [4, p. 3; 11, p. 6.]

**F10. Query audit, uncertainty and authorized conclusions - Required.** Logs prompts, search results, retrieved evidence, generated responses and actions. Answers must explicitly acknowledge uncertainty. The assistant cannot state that a person stole something unless an authorized human investigator has recorded that conclusion; the answer should attribute any such finding to the investigator. [4, pp. 3-4; 10, p. 6.]

### G. Alerts, escalation, and case management

**G01. Four-level alarm classification - Required.** Assigns Critical, High, Medium or Low priority according to site policy. Priority determines the immediate display, notification recipients and escalation. Serious falls, violence, fire/gas/hydrogen and perimeter incidents are normally High or Critical, but source examples overlap; configure one authoritative matrix rather than contradictory hardcoded mappings. [3.5, 5, pp. 3-4.]

**G02. Complete alert record - Required.** Stores event ID, alarm class, camera/location, time, sensor/alarm source, snapshot, clip, AI confidence, assigned responder, acknowledgement time, action notes, final disposition and closure approval. Fields that do not apply need an explicit status; for example, a sensor alarm can exist without an AI confidence score. [5, p. 4.]

**G03. Assignment and acknowledgement - Required.** Gives an alert a responsible responder and records who acknowledged it and when. Acknowledgement means someone has taken ownership, not that the situation is safe or the case is closed. Role permissions and the audit trail must cover these actions. [3.3, 5, pp. 3-4.]

**G04. Timed automatic escalation - Required for unacknowledged Critical alerts; also configurable for other classes.** Notifies the next-level contact when the acknowledgement deadline expires. High alerts also have configured escalation in the source table. Timer values, retries, contact ordering and behavior after acknowledgement must be set by policy. Escalation must remain operational locally during internet loss. [3.5, 5, pp. 3-4.]

**G05. Configurable routing rules - Required.** Changes alert behavior by area, shift, business hours, event type and authorized recipients. This allows a tool-room night intrusion and a daytime canteen exception to reach different people. Configuration changes need audit records and a way to verify that a rule reaches a valid responder. [5, p. 4; 10, p. 6.]

**G06. Incident investigation and approved closure - Required.** Maintains case status, notes, evidence, actions, final disposition and closure approval. Separates the detector's suggestion from the reviewer's finding. The PDF does not define exact status names; a proposed sequence is Open, Acknowledged, Investigating, Resolved, and Closed after approval. [1, 3.3, 3.5, 5, pp. 2-4.]

**G07. Daily operational alarm dashboard - Required.** Shows open alarms, unresolved cases, repeat events, camera faults, storage alarms and notification delivery status. It helps operators prioritize outstanding work and detect repeated issues. A dashboard total should be filterable by date, zone and status; exact filters are an implementation proposal. [5, p. 4.]

**G08. Delivery tracking and maintenance-ticket integration - Required delivery visibility / Conditional ticket connection.** Records whether notifications were attempted, sent, delivered or failed where supported by the channel. Low-priority issues can create maintenance tickets when a ticketing system is integrated. Sending a message is not proof that a human read or acknowledged it. [5, p. 4; 13, p. 7.]

### H. Camera and infrastructure health

**H01. Camera online, stream and recording continuity - Required.** Detects offline cameras, lost video, stopped recording and repeated stream failures. These conditions are distinct: a live picture can exist while recording is broken. Track last successful stream/recording time and notify authorized users; video-loss notification must meet the stated acceptance target. [3.1, p. 2; 9, p. 5; 12, p. 6.]

**H02. Visual camera degradation and tampering - Required.** Detects blockage, covering, defocus, excessive dirt, movement/repositioning and tampering. It needs reference views or visual quality analysis. Darkness, lighting changes and legitimate maintenance can look similar, so record the suspected fault and allow technician review. [3.3, p. 3; 9, p. 5.]

**H03. Camera power, network and stream telemetry - Required where data is available.** Monitors PoE/power status, connectivity, packet loss where available, stream bitrate and frame rate. This helps distinguish camera failure from switch, network or stream-quality problems. Some metrics depend on camera and switch management interfaces rather than the video feed itself. [9, p. 5.]

**H04. Server, AI service and hardware health - Required.** Shows AI service state and CPU/GPU/RAM utilization, temperature, fan health, UPS status and disk health. It alerts operators when analytics or infrastructure is degraded even if recording still works. Supported sensors and management interfaces determine which measurements can actually be collected. [3.1, p. 2; 9, p. 5.]

**H05. Storage capacity warnings - Required.** Generates warnings at configurable capacity thresholds, with 70%, 80%, 90% and critical capacity given as examples. It helps prevent silent recording loss. Thresholds alone do not define what to delete or stop when storage fills; retention and emergency full-disk behavior need explicit policy. [9, p. 5.]

**H06. Maintenance workflow and critical-zone urgency - Required.** Records camera name, fault type, first detection, duration, assigned technician, corrective action and closure status. Faults in gates, stores, fire-sensitive areas, tool rooms and the perimeter require immediate notification. Severity and escalation should reflect loss of coverage, not just a generic device error. [9, p. 5.]

**H07. Monthly health and incident-response reports - Required.** Summarizes camera health, recording health, storage health and incident-response performance. Useful measures include downtime and acknowledgement delays, but exact report formulas are not specified. Keep reporting grounded in actual monitoring and case records. [9, pp. 5-6.]

### I. Privacy, access control, and evidence governance

**I01. Role-based permissions - Required.** Restricts access to cameras, playback, exports and sensitive actions by authorized role. Search must apply the same permissions as the dashboard, including thumbnails and metadata. Detailed role and area scopes need a client-approved matrix; a login page alone is insufficient. [3.1, p. 2; 7, 10, 13, pp. 5-7.]

**I02. MFA, VPN and unique credentials - Required.** Requires MFA for administrators and remote users, authorized remote VPN access, and unique camera credentials. Cameras must not be directly exposed to the public internet. The source also lists MFA within network security controls; clarify whether ordinary local users must use it too. [6-7, pp. 4-5; 10, p. 6.]

**I03. Encryption and secure communications - Required.** Protects video, records and relevant services with HTTPS/TLS in transit and encryption at rest. Key storage, rotation, recovery and certificate management need an implementation plan. Encrypting only the login page leaves other data paths outside the intended protection. [7, p. 5; 10, p. 6.]

**I04. Protected audit records - Required.** Records logins, video playback, exports, deletions, configuration changes, alert acknowledgement, AI prompts and case actions in immutable or protected logs. This establishes who accessed or changed sensitive records. The source permits protected logs; it does not prescribe a particular immutability product or storage technology. [10, p. 6.]

**I05. Privacy-sensitive camera placement - Required.** Excludes toilets, changing rooms, prayer/private rooms and any prohibited private area. Site survey and camera fields of view must enforce these boundaries. Privacy masking may help with incidental visibility, but it is a proposed addition and does not authorize installing a camera in a prohibited room. [6, p. 4; 10, p. 6.]

**I06. Ambient audio disabled by default - Required.** Prevents workplace audio recording unless explicitly approved, appropriately reviewed and clearly notified under the client's applicable obligations. Distinguish this from a user deliberately activating the voice-query interface. Storage and retention for command audio also need a defined policy. [10, p. 6; 4, p. 3.]

**I07. Face recognition disabled by default - Required control; activation conditional.** Allows recognition only after written approval, a defined purpose, lawful basis, accuracy validation, retention rules and access controls. Face recognition is not a baseline prerequisite for person detection or anonymous movement analysis. The report does not determine whether a particular deployment satisfies local law. [10, p. 6.]

**I08. Human review before high-impact decisions - Required.** Prevents automatic discipline, salary deduction, termination or theft accusation based solely on AI. Authorized reviewers must confirm high-impact findings before final action. This does not mean waiting for a reviewer before displaying a critical alert or before an independent approved fire system performs its own function. [Cover, p. 1; 3.5, p. 3; 10, p. 6.]

**I09. Secure backup and disaster recovery - Required.** Provides secure backups and a documented recovery procedure for the system's critical data and configuration. Restore scope, frequency, recovery time and permitted data loss are unspecified. RAID protects against some disk failures but is not a substitute for a recoverable backup. [7, p. 5; 10, 13, pp. 6-7.]

**I10. Patching, firmware and retention administration - Required.** Maintains a patch/firmware process, retention policy, privacy controls and security hardening records. Signed firmware, secure update control and disabling defaults are recommended camera properties. Updates must preserve local operations as planned and be logged; maintenance and rollback arrangements need agreement. [6, p. 4; 10, 13, pp. 6-7.]

### J. Local platform, resilience, and expansion

**J01. Local processing and internet-outage operation - Required.** Keeps recording, monitoring, analytics, alerting and the local dashboard running on premises without public internet. A core detector or mandatory login dependency that stops without cloud access conflicts with this requirement. The source's exact offline requirement for every voice/GenAI feature should be clarified; local inference best fits its stated design intent. [1, p. 2; 7, p. 5; 15, p. 7.]

**J02. Segregated camera/AI network - Required.** Separates CCTV/AI from the office network using VLANs and firewall rules, with authorized paths to services. Managed PoE switches power/connect cameras. Isolation must be enforced by network policy; simply assigning different address ranges does not establish access control. [7, pp. 4-5.]

**J03. Camera and video-system interoperability - Required baseline; enhanced support recommended.** Uses ONVIF-compatible IP cameras and a VMS/NVR recording layer. ONVIF Profile T and analytics metadata support are recommended. Specific camera/VMS combinations still need validation; nominal compatibility does not establish that every proprietary analytic or export function integrates. [6-7, p. 4.]

**J04. Expansion to at least 32 cameras - Required.** Preserves the core design while adding streams, storage and inference capacity beyond the initial 8-16-camera deployment. It requires capacity planning, licensing and provisions for additional hardware. A single successful camera demonstration cannot prove 32-camera performance. [1, p. 2; 8.2, p. 5.]

**J05. Resilient recording and separated storage roles - Required architecture; hardware details as specified.** Uses recording storage and an event/metadata layer, with the source's RAID and NVMe recommendations for the intended deployment. Separate responsibilities allow fast metadata search without treating the event database as a video archive. Actual fault tolerance depends on configuration and recovery testing. [7-8, pp. 4-5.]

**J06. Power continuity - Required.** Provides appropriately sized UPS coverage for core and PoE switches, AI server, VMS/NVR, storage, firewall and alarm gateway as applicable. Redundant server power supplies are preferred. Runtime, shutdown thresholds and restart sequence are not specified and must be calculated against the real load. [7-8, p. 5.]

**J07. Integration interfaces and extensibility - Required.** Provides a structure for access control, fire/safety signals, asset records and future HRMS/ERP/tool-management connections, plus API documentation at handover. Each interface needs defined data fields, authentication, time semantics and failure behavior. Extensibility does not mean every named external product is already supported. [3.2, 3.4-3.5, 11, 13, 15, pp. 2-3, 6-7.]

## 4. What the system must do end to end

The following examples turn the catalog into concrete product behavior. They are proposed walkthroughs based on the source, not additional requirements or proof of implemented capability.

### Scenario 1: After-hours stores entry with no matching badge event

1. An operator configures the stores entry line, operating hours and permitted exceptions.
2. A camera observes a directional entry and creates an event with camera, time and evidence.
3. The correlation service checks the relevant access reader's records within an agreed tolerance.
4. The event records matched, unmatched, ambiguous, or source unavailable. A reader outage must not be disguised as an unmatched credential.
5. The rule engine assigns the configured alarm class and notifies the designated responder.
6. A responder acknowledges, reviews footage and records a finding. An approved cleaner may make this a legitimate exception.
7. A later query for after-hours stores entries returns the same event and correlation evidence. The model summarizes the records rather than creating a new interpretation of identity.

### Scenario 2: Fire-panel signal

1. The independent fire system detects and handles its alarm according to its own approved design.
2. The integration gateway sends the corresponding signal to the video platform.
3. The platform maps the source to a zone and relevant cameras, displays the alarm on authorized screens, sounds the local alert and preserves pre/post evidence.
4. Notifications follow the configured emergency contacts. If the alarm remains unacknowledged beyond the policy timer, escalation proceeds automatically.
5. Missing camera coverage or failed message delivery remains visible and does not suppress the source alarm.
6. The incident remains open for authorized review and closure. Acknowledging the video-system notification must not be assumed to reset the fire panel.

### Scenario 3: Tool removal and later investigation

1. A protected tool-board zone changes from expected presence to possible removal.
2. The system preserves context and checks any available tool-issue or RFID/QR record.
3. The event identifies what is actually known: a zone changed, an object class moved, or a uniquely identified asset was issued. These are different evidence levels.
4. The reviewer inspects the clip and business records. Authorized borrowing can explain the event.
5. A search for a named tool succeeds only if that name is mapped to the zone, recognized object or trusted asset identifier.
6. A return observation can update the history, but a final theft conclusion requires an authorized investigator's recorded finding.

### Scenario 4: Long-break query

1. Break-zone and shift policies establish expected duration, grace periods and exemptions.
2. Observations produce an approximate presence interval with known gaps or uncertainty.
3. The query uses the requested date and duration, not a hardcoded 45-minute policy.
4. Results show intervals, evidence and identity linkage only if approved and available.
5. The reviewer checks shift exceptions and missed observations. No automatic payroll action follows.

### Scenario 5: Camera stops recording while the live view still works

1. Stream monitoring confirms the camera is reachable, but recording-health checks detect a missing or stale segment.
2. The health dashboard distinguishes recording failure from video loss.
3. Critical-zone routing notifies the responsible operator and assigns maintenance work.
4. The technician restores recording, records the corrective action and closes the fault.
5. Searches covering the affected period disclose missing evidence rather than returning an apparently complete history.

## 5. Architecture and data needed to make this real

### Architecture from the source

The source describes IP cameras connected through managed PoE switches and a segregated CCTV/AI VLAN, with VMS/NVR recording and storage, GPU inference, an event metadata database, a generative-AI retrieval service, a secure local dashboard and authorized VPN access. [Section 7, pp. 4-5.]

That logical chain should not be interpreted as requiring the recorder to wait for AI or GenAI processing. A proposed implementation has two cooperating paths: a recording path that preserves footage independently, and an analytics path that produces indexed events. External alarms enter the event/workflow layer through adapters. Search reads authorized metadata and retrieves linked evidence from storage.

| Component | Responsibility | Why it is needed |
| --- | --- | --- |
| Camera and integration inventory | Cameras, zones, lines, readers, sensors, locations | Every result must identify a real source and location |
| Recorder / video management layer | Ingest, retain, replay, extract clips | Reliable evidence must exist before it can be searched |
| Analytics workers | Detect objects and behaviors in live or recorded footage | Convert pixels into observations and candidate events |
| Rule and correlation service | Apply schedules, zones, thresholds and external records | Turn generic observations into site-specific exceptions |
| Event database and index | Store searchable events, metadata and evidence references | Support historical queries and dashboard filters |
| Alert and case workflow | Route, acknowledge, escalate, investigate and close | Connect detection to accountable human response |
| Query and speech services | Interpret questions, retrieve evidence, explain results | Provide the required natural-language interface |
| Health and audit services | Monitor services and preserve access/action history | Make failures and sensitive operations observable |
| Web dashboard | Views for monitoring, incidents, search, health and configuration | Gives authorized users one coherent interface |

These are logical modules, not a requirement for nine separate servers or microservices. A hackathon implementation can combine modules while keeping their responsibilities clear.

### Minimum useful data model - proposed

- **Camera:** ID, name, location, stream configuration, active zones, health and recording status.
- **Zone/rule:** type, geometry, direction, operating hours, shift, thresholds, exemption policy, enabled state and version.
- **Observation/event:** ID, source type, source camera or sensor, event type, event/start/end times, confidence when applicable, zone, supporting observations and review state.
- **Evidence:** source recording reference, clip start/end, snapshot reference, availability state, retention/hold state and export history.
- **Access or asset record:** trusted external ID, source system, credential/asset mapping, source timestamp, receipt timestamp and correlation result.
- **Alert:** event reference, priority, assigned responder, policy/deadline, acknowledgement and escalation history.
- **Notification attempt:** channel, recipient, attempted time, delivery state and any error or gateway receipt.
- **Case:** linked events/evidence, investigator, notes, finding, disposition and closure approval.
- **Audit entry:** actor, action, target record, timestamp and outcome, including prompt and retrieval references for AI searches.

Keep AI observations, external source records, correlation outcomes and human findings separate. Overwriting a detector's original event with a reviewer's conclusion makes it harder to explain how the final decision was reached.

### Important implementation distinctions

**Detection versus rules:** detecting a person is a model task; deciding that their presence is after hours is a schedule rule. Combining them in one opaque AI prompt makes the system harder to verify.

**Recording frame rate versus analytics frame rate:** the source's camera frame-rate requirements are capture specifications. How frequently each analytic samples or processes video must be benchmarked. Lower analytic sampling can miss short events; the document does not authorize a universal reduction.

**Inference versus retrieval:** a language model cannot search facts that the system never detected or indexed. Historical reanalysis can address some gaps, but it consumes GPU time and is not the same as a fast indexed search.

**No result versus no event:** no matching indexed event might mean nothing happened, the camera was unavailable, the detector missed it, or the requested attribute was never indexed. Answers should state the coverage actually searched.

**Local versus external notifications:** local alerts can survive internet interruption. External gateways require a working communication path; failed delivery needs logging and configured handling. A retry queue would be a useful proposed design.

## 6. Hardware, network, storage, and installation requirements

The following values are requirements or recommendations from the PDF, not newly selected products. No prices, availability claims or vendor comparisons are assumed.

### Camera specification

| Parameter | Source minimum or baseline | Source recommendation |
| --- | --- | --- |
| Type | IP network camera | IP AI camera with edge analytics metadata |
| Resolution | 4 MP | 4K / 8 MP at gates, stores, tool zones and wide areas |
| Frame rate | 20 fps | 25-30 fps at gates, incidents and safety-critical zones |
| Compression | H.264 | H.265 / H.265+ with H.264 fallback |
| Low light | IR night vision | True WDR, IR and low-light color where justified |
| Wide dynamic range | Preferred rather than a strict minimum | At least 120 dB at entrances |
| Lens | Fixed lens allowed | Motorized varifocal for gates, stores and corridors |
| Network | Ethernet | PoE/PoE+ with managed switches |
| Interoperability | ONVIF compatible | ONVIF Profile T and analytics metadata support |
| Outdoor protection | As required | IP66/IP67 and IK10 where exposed or at vandal risk |
| Cybersecurity | Unique passwords | HTTPS, signed firmware, controlled updates, defaults disabled |

The site survey must document field of view, mounting height, lighting, blind spots, coverage overlap, cable routes, PoE loading, grounding/surge protection and rule-zone overlays for every camera. These directly affect analytic feasibility: an expensive GPU cannot recover detail the camera never captured. [Section 6, p. 4.]

### Server and network specification

| Item | Initial 8-16 cameras | Expansion 16-32 cameras |
| --- | --- | --- |
| CPU | Xeon W/Xeon Scalable or EPYC/Ryzen 9 class; minimum 16 physical cores | EPYC or Xeon Scalable; 24-32 physical cores |
| GPU | RTX 6000 Ada 48 GB or L40S 48 GB preferred; RTX 4090 24 GB permitted for pilot/small deployment subject to thermal, warranty and support requirements | One 48 GB L40S / RTX 6000 Ada, with provision for a second GPU |
| Memory | 128 GB ECC preferred; 64 GB minimum | 128-256 GB ECC |
| System storage | Two 1.92 TB enterprise NVMe drives in RAID 1 | Final design must be sized; source does not specify a replacement system-disk value |
| AI/event storage | 2-4 TB enterprise NVMe for models, metadata, clips and database | Size against actual expanded workload |
| Recording | Dedicated capacity calculated from bitrate and retention | Dedicated RAID storage; separate/scalable recording storage as needed |
| Network | Dual 10 GbE preferred | 10/25 GbE connectivity |
| Power/chassis | Redundant PSU preferred; correctly sized UPS | Rack chassis, redundant PSU, cooling/power/PCIe/licensing provision for expansion |
| Operating system | Ubuntu Server LTS preferred for AI; selected VMS parts may use Windows Server | Validate compatibility of the selected stack |

Gigabit Ethernet is the minimum to edge switches. The source calls for 10 GbE between core switch, server and storage above approximately 16 high-resolution cameras. UPS scope includes the network and alarm gateway as applicable, not just the GPU server. Final capacity must be benchmarked using the actual streams, resolutions, bitrates, frame rates, models per stream and retention. GPU memory size alone cannot establish supported camera count. [Sections 7-8, pp. 4-5.]

### Storage calculation with units made explicit

For continuous recording at average bitrate b in megabits/second, N cameras and D days:

**Decimal GB/day = N x b x 10.8.**

**Decimal TB for D days = N x b x 10.8 x D / 1,000.**

This follows from seconds per day and eight bits per byte. It excludes RAID parity, filesystem overhead, duplicate evidence clips, snapshots, metadata, backups and reserve capacity. Variable bitrate requires a measured average and allowance for variation.

| Cameras | Assumed average bitrate each | Raw video per day | Raw video for 30 days | Source target usable storage |
| --- | --- | --- | --- | --- |
| 8 | 4 Mbps | 345.6 GB | 10.368 TB | 12-20 TB |
| 16 | 4 Mbps | 691.2 GB | 20.736 TB | 24-40 TB |
| 32 | 4 Mbps | 1,382.4 GB | 41.472 TB | 48-80 TB |

The 16-camera example matches the source's rounded 691 GB/day and 20.7 TB/30 days. These illustrative figures do not imply that every 4 MP or 8 MP camera will average 4 Mbps. Doubling average bitrate doubles raw recording storage.

The source recommends surveillance/nearline enterprise disks and RAID 6 or RAID 10 for the 8-camera target, dedicated RAID storage at 16, and a separate recording node or scalable NAS/SAN at 32. Usable capacity is after RAID protection; total purchased raw disk capacity will be larger. Exact drive count and reserve policy need a final storage design. [Section 8.3, p. 5.]

## 7. Alert policy and acceptance testing

### Required severity behavior

| Class | Source examples | Required behavior |
| --- | --- | --- |
| Critical | Fire; gas/hydrogen; smoke/flame; serious fall; active violence; major intrusion | Instant pop-up and audible alert, relevant live view, pre/post clips, notify safety/security and escalation contacts, record acknowledgement |
| High | Suspicious removal; unauthorized secure-room access; camera tamper; perimeter breach; forced-open door | Immediate alert and clip, notify designated users, escalate if unacknowledged within policy |
| Medium | Long break; loitering; crowding; left-behind object; repeated access mismatch | Dashboard/task notification, review report, escalation by rule |
| Low | Camera-quality degradation; capacity warning; non-critical analytics exception | Dashboard and maintenance notification; ticket where integrated |

The source also says some serious safety/perimeter events are normally Critical or High by site policy. That is a configuration decision to settle, not a reason to assign the same event two conflicting priorities. Critical-zone equipment faults may deserve higher urgency than an ordinary quality warning. [Sections 3.5, 5, 9, pp. 3-5.]

### Measurable acceptance criteria from the source

| Requirement | Source target | Proposed verification |
| --- | --- | --- |
| Live-view latency on LAN | Normally less than 2-5 seconds, subject to configuration | Display an observable timed action and measure its appearance in the dashboard across target layouts |
| Standard AI alert | Normally less than 10 seconds from detected event | Record event/detection/display timestamps; also report physical event onset to alert, so inference delay is not hidden |
| Camera/video loss notice | Within 60 seconds or tighter if feasible | Disconnect a stream and measure detection plus user notification |
| Historical indexed search | Normally within 30 seconds for standard queries over 30-day indexed footage, subject to complexity | Use an actual representative 30-day index and agreed query set; report dataset size and cache state |
| Playback start on LAN | Normally within 5 seconds for standard clips | Measure request to first displayed video frame |
| Availability | At least 99.5%, excluding planned maintenance | Agree service boundaries and measurement window; record unplanned downtime |
| Analytic quality | False positives and false negatives separately for every use case | Use labeled positive and negative examples; report per-use-case misses and false alerts |
| Evidence integrity | Watermarked, auditable exports; source/time/reviewer records | Export, reopen and compare evidence context and audit trail |
| Critical workflow | Demonstrate alert, acknowledgement, escalation, delivery logs and closure during SAT | Run an acknowledged alarm and a deliberately unacknowledged alarm through the full workflow |

The wording 'less than 2-5 seconds' and 'normally' does not define a precise percentile or maximum. Agree whether the target is 2 seconds, 5 seconds, a range by layout, or another explicit measurement policy. Similarly, 'detected event' should not hide slow detection from physical onset. No numerical pass threshold for analytic precision or recall is supplied.

For illustration, 99.5% availability over a 30-day measured period permits 3.6 hours of unplanned downtime if the whole 720-hour period is included. This arithmetic is not a substitute for agreeing which services are in scope and how planned maintenance is excluded.

### Accuracy evaluation that would be meaningful

For each analytic, record true positives, false positives and false negatives. Precision is true positives divided by all positive detections; recall is true positives divided by actual positive cases. These definitions are proposed evaluation tools, while separate false-positive/false-negative measurement is explicitly required by the PDF.

Use held-out footage containing both the target event and realistic non-events: normal work that resembles fighting, bending that resembles a fall, legitimate tool issue, approved after-hours staff and temporary object occlusion. Report daylight/night conditions, camera angle, distance, event duration and crowded scenes separately where relevant. For continuous monitoring, false alerts per camera-hour and missed events per scenario are useful alongside precision/recall.

Identity matching and event detection need separate scores. A correct removal detection with an incorrect employee match is not a fully correct event. Likewise, matching a fire-panel signal tests an integration and workflow, not the accuracy of a visual fire detector.

### Failure and boundary tests - proposed

- Disconnect public internet: core local recording, analytics, alarms and dashboard must keep working; show external message failures accurately.
- Disable AI processing: recording and health alerts should behave according to the agreed degraded-service design.
- Stop recording while leaving the live stream active: detect the recording fault independently.
- Send duplicate external alarms: preserve source history without overwhelming responders with uncontrolled duplicates; deduplication policy is a proposed implementation detail.
- Delay access events or shift a source clock: distinguish a true mismatch from unreliable correlation.
- Attempt unauthorized camera search, thumbnail access, playback and export: enforce permissions at every retrieval path.
- Search with an unindexed asset name: report insufficient evidence rather than generate an invented answer.
- Reach capacity thresholds and test the agreed full-disk behavior; do not discover deletion policy during an incident.
- Restore a backup and verify configuration, records, evidence references and permissions.
- Review a false-positive event and export its evidence: preserve the original detection and the final human finding.

## 8. Realistic hackathon scope and demonstration

The full specification is too broad to describe honestly as completed by a small proof of concept without extensive integration and site testing. A persuasive hackathon entry should demonstrate a coherent end-to-end slice and clearly mark unimplemented, simulated and later-phase capabilities. This is a proposed strategy; the organizer's actual judging rubric may require changes.

### Recommended core demonstration

| Priority | Build or demonstrate | Why it matters | Evidence of completion |
| --- | --- | --- | --- |
| 1 | Local video ingestion, recording/playback and configured zones | Establishes the evidence foundation | A real captured interval can be replayed and linked to an event |
| 2 | Person crossing, restricted-zone intrusion and after-hours rules | Concrete, understandable baseline analytics | Staged positive and negative cases with event context |
| 3 | Alert, acknowledgement, escalation and case closure | Shows that detections lead to accountable action | One full incident lifecycle including unacknowledged escalation |
| 4 | Fire/safety signal input and camera mapping | Demonstrates an important integration boundary | Clearly labeled simulator if no approved physical gateway is available |
| 5 | Camera/video-loss health alert | Demonstrates operational reliability | Disconnect a source and show a timed health notification |
| 6 | Indexed English text search with clickable evidence | Demonstrates the distinctive AI experience | Search finds stored events, correct clips and correlation metadata |
| 7 | Access-record correlation | Connects video to an operational use case | Matched, unmatched and unavailable-source examples; mock records labeled |
| 8 | Basic permissions, audit and honest uncertainty | Satisfies core trust requirements | Restricted user cannot access a protected camera; actions appear in audit |

Once that vertical slice works, add designated-zone object removal and approximate long-break exceptions if footage and tracking are adequate. They are part of the source's recommended production pilot, so a demo deferral must be disclosed rather than described as full pilot compliance.

English voice is required in the full system, even though the recommended pilot specifically highlights text search. Add push-to-talk and transcript display if capacity allows; otherwise mark voice as deferred. Complex fight/fall/PPE/smoke and named-tool recognition should be demonstrated only with appropriate data and transparent limitations. A staged clip is useful for a demo but is not a production accuracy benchmark.

### What can be simulated, and how to present it

- Fire-panel input can be a test event from a labeled simulator. State that gateway wiring and field acceptance remain outstanding.
- Access control can use a labeled sample dataset or test API. State that real reader integration and identity validation are pending.
- Eight camera tiles can replay authorized sample footage, but label them as replays rather than eight installed live cameras.
- A shortened escalation timer can make the workflow visible during the demo. Display it as a demo configuration.
- A small event index can prove search behavior. It cannot prove the 30-day/32-camera performance target.

Do not claim production readiness, a validated fire detector, named employee identity, a proven theft, or all-feature accuracy merely because one prepared demonstration succeeds.

### Suggested dashboard screens

1. **Overview:** live camera groups, highest-priority alarms, unresolved cases and key health indicators.
2. **Live and playback:** camera view, event timeline, snapshots and pre/post clips.
3. **Alerts and incidents:** priority queue, assignment, acknowledgement, countdown/escalation, notes and closure.
4. **Evidence search:** typed request, optional voice, filters, result cards and follow-ups.
5. **Access and break exceptions:** directional entries, correlation status, first/last observations and approximate durations.
6. **Assets:** protected zones, removal/return observations and external issue records where available.
7. **Health and maintenance:** camera/recording faults, capacity, service status, technician tasks and reports.
8. **Administration:** users, zones, schedules, routing, integration mappings, retention and audit access.

These are proposed UI groupings, not a source requirement for eight separate pages.

### Suggested live demonstration story

Start with the local dashboard and show that camera evidence is being recorded. Stage an entry into a restricted stores zone outside its permitted hours. Show the event's clip and access-record status, then leave the alarm unacknowledged long enough to demonstrate escalation. Acknowledge it, investigate and record a legitimate-access or suspicious-event finding. Search for that same incident in plain English and open its evidence. Finally, disconnect a camera or internet connection to show the appropriate health or offline behavior. If a fire-panel simulator is included, demonstrate it as a distinct sensor-triggered event rather than pretending the video model detected fire.

## 9. Source implementation phases and pilot

### Six implementation phases in the specification

| Phase | Required scope and outputs |
| --- | --- |
| 1. Survey and design | Site survey, camera layout/field of view, network design, bill of quantities, server/GPU/storage sizing, alarm design, privacy/security plan and schedule |
| 2. Core deployment | Cameras, PoE/network, UPS, server/storage, VMS/NVR, recording, camera-health dashboard and basic analytics |
| 3. Safety and security alarms | Fire/sensor integration, critical workflow, notifications, escalation, case management, theft and restricted-access rules |
| 4. GenAI and search | Metadata index, historical search, typed conversational AI, evidence-grounded answers, reports and voice |
| 5. Advanced/custom models | PPE, named tools/assets, Tamil, RFID/QR/BLE/UWB and HRMS/ERP/tool-management integrations |
| 6. Test and handover | Site Acceptance Test, training, documentation, benchmarks, limitations register and support handover |

Integration mentions in earlier sections and phase 5 are not fully consistent in timing. Basic correlation should have an interface design early, while actual deployments depend on available systems and the agreed rollout. [Section 11, p. 6.]

### Recommended eight-camera production pilot

The source proposes two entry/exit cameras, two workshop cameras, one canteen camera, two stores/tool-room cameras and one loading/outdoor camera. It specifies 30-day retention and an on-premise GPU server.

The initial use cases are entry/exit, restricted-zone intrusion, after-hours presence, camera tampering/faults, fire-panel integration, selected safety alarms, long-break exceptions, removal from designated tool-storage zones, theft investigation search and text historical search. Review the pilot after 30-60 days for alert quality, false alarms, camera angles/lighting, storage use, GPU use, notification response, needed rules and whether asset-tag technologies are necessary before expanding to advanced named-tool or biometric features. [Section 14, p. 7.]

This field pilot is different from a hackathon demo. It includes real installation, prolonged observation, storage retention and operational review that cannot be established through a short stage presentation.

## 10. Risks, ambiguities, and questions to settle

### Highest-impact risks

| Risk | Why it matters | Proposed response |
| --- | --- | --- |
| Identity assumed from ordinary video | Wrong employee attribution affects HR and security findings | Use approved correlations, explicit unknown identity and human review |
| Weak scene coverage | Occlusion and image scale undermine detection and evidence | Validate field of view, lighting and critical-zone coverage before model tuning |
| Alert fatigue | Repeated false alarms reduce response quality | Tune per-use-case rules, measure false alerts, and review dispositions |
| Unsupported GenAI claims | Fluent text can turn incomplete metadata into a false allegation | Retrieve permitted evidence first and attribute every material finding |
| Cloud dependency in core services | Internet loss disables the required local workflow | Verify local authentication, inference, recording and alert paths |
| Incorrect safety-system coupling | A video platform could interfere with independent protection | Use approved integration boundaries and a reviewed cause-and-effect matrix |
| Insufficient recording capacity | Evidence disappears or recording stops | Measure bitrate, size usable capacity and define retention/full-disk behavior |
| Unbounded scope | Hardware, custom models and integrations exceed demo capacity | Track full requirements separately from the chosen demonstration slice |

### Questions that affect implementation or acceptance

1. **Hackathon rules:** What duration, team size, judging criteria, permitted datasets, network restrictions and required deliverables apply?
2. **Available resources:** Which cameras, recordings, GPU, access system and alarm gateway can the team actually use?
3. **Identity:** How should the system associate an observed person with an employee when face recognition is disabled? Are anonymous results acceptable for the pilot?
4. **Time rules:** What site timezone, shifts, holidays, authorized overtime, break allowances and exemptions apply? How should overnight shifts be reported?
5. **Correlation:** Which reader maps to which camera/door, what matching window is allowed, and how are delayed or missing records represented?
6. **Behavior definitions:** What counts as crowding, loitering, abnormal gathering, unsafe behavior and running? Which PPE classes and assets are included?
7. **Confidence and accuracy:** What per-use-case precision/recall or false-alarm/miss limits are acceptable, and on what test dataset?
8. **Latency:** What exactly does 'normally' mean, which percentile is tested, and where does each latency measurement start?
9. **Retention:** Is 30 days required beyond the pilot? How long are case clips, snapshots, access records, query logs and command audio retained?
10. **Alert policy:** Which events are Critical versus High, who acknowledges, how long until escalation, and who can close a case?
11. **Emergency outputs:** Which integrations only receive signals, which approved relay outputs may activate, and who approves the cause-and-effect matrix?
12. **Offline scope:** Must every search, speech-to-text and spoken-response function also work without internet, in addition to the explicitly listed core functions?
13. **External notifications:** Which channels are permitted, what constitutes delivery, and what route remains available during network outages?
14. **Tamil timing:** Does the source's 'phase 2' language reference or the six-phase plan's phase 5 milestone control delivery?
15. **Integration timing:** Which RFID/QR/access capabilities are initial dependencies and which belong in the advanced rollout?
16. **Availability and recovery:** Which services count toward 99.5%, what measurement window applies, what UPS runtime is needed, and what recovery time/data loss is acceptable?
17. **Playback/evidence:** How long are pre/post clips, how are missing segments shown, and how is evidence retained beyond routine rotation?
18. **Governance:** Which jurisdiction and company rules govern privacy, biometric approval, retention and employee review? Who owns these decisions?
19. **Scale validation:** Must all 32 cameras run every analytic concurrently? Which resolutions, frame rates and query concurrency constitute acceptance load?
20. **Ownership/support:** What are the source-code rights, model/data licenses, warranties, maintenance terms and required service response times?

### Capabilities not explicitly required

The PDF does not explicitly require automatic salary deductions, automatic disciplinary action, unrestricted face recognition, license-plate recognition, emotion detection, productivity scoring, cross-camera identity re-identification, fully automated inventory accounting, autonomous machine shutdown, a native mobile app, or unrestricted uploads of arbitrary videos. Some could be separately proposed where appropriate; several would conflict with the document's controls if implemented without the stated approvals or human review. Do not let an ambitious demo silently expand the agreed scope.

## 11. Complete delivery checklist

The specification includes supplier obligations beyond software functionality. A team analyzing compliance should track these separately from demo features. [Sections 6-8, 11-15, pp. 4-7.]

### Design and procurement documentation

- Complete system architecture and hardware/software bill of quantities.
- Make/model details, licensing, warranty and country of origin.
- Site survey, camera layout, field-of-view drawings, mounting/lighting/blind-spot/overlap assessment and rule overlays.
- Cable routes, grounding/surge protection, PoE loading, network topology, IP plan and rack layout.
- Power and UPS calculations, storage calculation and GPU/server sizing calculation.
- Implementation programme, schedule and support model.

### AI and integration documentation

- Capability matrix identifying standard, configuration-only and custom-training features.
- For each capability: limitation, expected accuracy and test method; expected figures require evidence rather than generic marketing claims.
- Fire/safety/alarm integration drawings, approved interfaces and source-to-camera mapping.
- Cause-and-effect matrix, escalation matrix and notification test records.
- Documented assumptions and limitations for fighting, falls, fire/smoke, theft investigation and tool recognition.
- API documentation and source-code/licensing clarification.

### Security, operations, and handover

- Cybersecurity hardening checklist; privacy controls and user-role matrix.
- Retention policy and secure backup/disaster-recovery procedure.
- Site Acceptance Test plan and report, including benchmark results and critical-alarm workflow demonstration.
- Training materials, administrator/user manuals and training delivery.
- Limitations register, support handover and annual maintenance proposal.

### Suggested capability-matrix template

Use one record per analytic or integration: feature ID; source requirement; deployment status; standard/configuration/custom category; camera/zone scope; required inputs; model or rule version; hardware assumptions; known limitations; expected performance; measured performance; test method; evidence link; owner; remaining work. For a hackathon, add a clear status such as implemented, simulated, partially demonstrated, or deferred.

## 12. Coverage map and glossary

### Traceability to all source sections

| PDF source | Covered in this report |
| --- | --- |
| Cover/core principle, p. 1 | Executive assessment; I08; risks and scope boundaries |
| 1. Project Objective, p. 2 | Executive assessment; A10; F01-F10; J01/J04; architecture |
| 2. Areas and Monitoring Scope, p. 2 | Area map; A02; B/C/D catalog; camera-zone configuration |
| 3.1 Live monitoring and recording, p. 2 | A01-A10; H01/H04; I01/I04 |
| 3.2 Entry, exit, attendance and breaks, pp. 2-3 | B01-B12; access and break walkthroughs |
| 3.3 Incidents and abnormal events, p. 3 | C01-C12; D02/D04; H01-H02; G02/G06 |
| 3.4 Theft and suspicious activity, p. 3 | B07; D01-D08; asset walkthrough |
| 3.5 Fire, smoke and emergencies, p. 3 | E01-E07; G01-G06; fire walkthrough |
| 4. GenAI and voice, pp. 3-4 | F01-F10; architecture; language-timing ambiguity |
| 5. Alerts and action workflow, p. 4 | G01-G08; alert policy; acceptance scenarios |
| 6. Cameras and field devices, p. 4 | Camera table; site survey; I02/J03; delivery checklist |
| 7. On-premise architecture, pp. 4-5 | Architecture; I01-I03; J01-J07; network and power |
| 8. Server/GPU/storage, p. 5 | Hardware tables; storage calculation; scale requirements |
| 9. Camera/system health, pp. 5-6 | H01-H07; recording failure walkthrough |
| 10. Safety/privacy/security, p. 6 | I01-I10; executive boundaries; risks and testing |
| 11. Implementation phases, p. 6 | Six-phase table; advanced/conditional catalog statuses |
| 12. Acceptance criteria, p. 6 | Acceptance table; accuracy and failure tests |
| 13. Supplier deliverables, pp. 6-7 | Complete delivery checklist and capability-matrix template |
| 14. Recommended pilot, p. 7 | Eight-camera allocation, initial use cases and 30-60-day review |
| 15. Technical-team scope, p. 7 | Full catalog, architecture, delivery checklist and boundary statement |

### Terms used in the specification

- **VMS / NVR:** video management software / network video recorder; records and manages camera footage.
- **IP camera:** a camera that transmits video over a data network.
- **PoE / PoE+:** power and data delivered through an Ethernet connection, subject to supported power capacity.
- **VLAN:** a logically separated network segment; firewall policy controls communication between segments.
- **GPU inference:** running trained AI models on a graphics processor to produce detections or other outputs.
- **Metadata:** structured facts about footage, such as time, camera, event type and evidence location.
- **ONVIF:** camera/video interoperability specifications; the exact supported profile and functions still matter.
- **FACP:** Fire Alarm Control Panel, part of the independent fire detection/alarm system.
- **NTP:** a protocol for synchronizing device clocks.
- **WDR:** wide dynamic range, useful when a scene contains bright and dark regions.
- **RFID / QR / BLE / UWB:** identification or location technologies that can complement video-based asset tracking.
- **HRMS / ERP:** human-resources management / enterprise resource planning systems.
- **RBAC / MFA / VPN:** role-based access control / multi-factor authentication / virtual private network.
- **RAID / NVMe / NAS / SAN:** disk redundancy arrangements / a fast storage interface / network-attached storage / storage area network.
- **UPS:** uninterruptible power supply, providing limited backup power and supporting orderly shutdown.
- **BOQ / SAT:** bill of quantities / Site Acceptance Test.
- **False positive / false negative:** an alert for an event that did not occur / a real event the system missed.

### Source and method

Source: AI_Video_Intelligence_Workplace_System_Requirements.pdf, seven pages, titled 'On-Premise AI Video Intelligence and Workplace Safety System - Technical Requirements Specification / Scope of Work,' prepared for S Flo / Workplace Operations. All seven pages were text-extracted and visually reviewed. Requirements references throughout this report point to that supplied document. No web research, legal determination, vendor benchmark, procurement quote or external hackathon brief is represented here.

The catalog contains 91 consolidated capabilities across ten groups. These are an analytical decomposition, not an official organizer feature count. The remaining chapters retain the hardware, rollout, performance, governance and supplier obligations so they are not lost by reducing the specification to a software feature list.

