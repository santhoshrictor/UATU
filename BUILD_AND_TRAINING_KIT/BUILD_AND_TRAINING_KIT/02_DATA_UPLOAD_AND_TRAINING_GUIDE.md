# What to provide, where to put it, and how training actually works

Prepared 13 October 2026. This guide accompanies the master build prompt and the supplied requirements. Folder names below are proposed conventions. They are not existing training services or proof that models have been trained.

**First distinction: four different uses of your files**

| Use | What you supply | Where it belongs | What happens |
|---|---|---|---|
| Coding context | Requirements, build plan, completed brief, sanitized interface docs | Coding assistant's project files or permitted attachments | AI reads specifications and writes/tests software |
| Model development | Authorized footage, images, annotations, dataset manifests | Private dataset storage, annotation tool, approved training machine | A training/evaluation program reads data and produces model artifacts |
| Runtime knowledge | Camera names, zones, schedules, incidents, access/asset metadata | Application database and evidence index | Search retrieves current authorized records |
| Deployment secrets | Camera passwords, gateway credentials, keys, notification tokens | Protected local secret configuration or secret manager | Running services authenticate to real systems |

Attaching a video to a coding chat does not by itself fine-tune the deployed detector. The developer must implement and run a training job, save a versioned model, evaluate it, and deliberately deploy it. Uploading the PDF gives product context; it does not train a camera model. Most features require software and configuration rather than new model weights.

**Step 1 — Give the coding AI the project brief**

Copy this kit into a new project folder and preserve the reference/ directory. Open the folder in your coding editor. Fill in 03_SITE_BRIEF_TEMPLATE.md as far as possible; unknown values can stay explicitly unknown. Give the assistant 01_MASTER_BUILD_PROMPT.md as the instruction.

The minimum initial context is the original PDF, the 91-feature analysis, the ordered build plan, and your brief. You can start without footage, but camera/model/field acceptance will remain incomplete. A chat-only tool may write suggestions but cannot necessarily install software, run tests, access cameras, or train models; use an environment with the required local execution capabilities for implementation.

Add sanitized camera manuals, integration APIs/register maps, sample record schemas, and policy documents as they become available. Screenshots of desired UI are optional design references. They do not replace technical inputs.

Do not put passwords, private keys, unrestricted employee records, or production credentials into prompts. Merely opening a local file in a hosted coding assistant can disclose its contents to that provider; locality of the file is not a guarantee of local model processing. Supply private data only through an approved environment and policy. Keep bulk footage out of ordinary chat attachments.

**Step 2 — Create a private data location**

Choose an access-controlled local disk or approved on-premise storage. Use an example layout like this; the actual root should be outside ordinary source control and unintended cloud-sync folders:

```text
private-data/
  manifests/                 # source, permission, camera, session, and hash metadata
  raw/site-01/cam-01/         # unchanged original recordings
  working/                   # derived frames/clips for annotation; provenance preserved
  annotations/master/        # reviewed, tool-native annotations and label definitions
  datasets/detection-v001/    # versioned images, labels, split manifests
  datasets/actions-v001/      # clips/frames, temporal labels, split manifests
  datasets/tracking-v001/     # sequences and anonymous track annotations
  integration-fixtures/      # sanitized schema-compatible sample records
  query-evaluation/          # questions, filters, evidence references, expected outcomes
  voice-evaluation/          # approved command recordings and corrected transcripts
  sealed-acceptance/         # independently controlled final site-evaluation data
  model-runs/                # configs, checkpoints, metrics, logs
  approved-models/           # deliberately promoted deployment artifacts
```

Give the coding assistant manifests and paths where appropriate. Mount raw/training data read-only into jobs when possible; give output access only to the intended run directories. Keep final acceptance data separately permissioned from the training workflow. File hashes and manifests help detect accidental duplication but do not grant privacy or licensing permission.

No real dataset folders or recordings are included in this kit. The JSON templates are examples of project metadata contracts, not CVAT-import files or completed training datasets.

**Step 3 — Collect the right inputs for each feature family**

| Feature family | What to collect/provide | Labels/configuration needed | Is custom training normally needed? |
|---|---|---|---|
| Live view/recording/playback | Camera manuals, stream capabilities, permitted camera connection, representative recordings | Camera inventory, retention, timezone, supported codecs | No; implement and test media handling |
| Person/vehicle detection | Original scenes across the actual viewing conditions | Object boxes/classes; visibility/occlusion guidance | Start pretrained; fine-tune only if measured gaps justify it |
| Entry/exit, intrusion, perimeter | Full passage sequences, camera view image, line/zone placement | Tracks, crossing times/directions, allowed routes | Usually detector/tracker plus configured rules |
| Occupancy/crowding | Empty, lightly occupied, busy, and occluded scenes | Reference counts, zone definition, threshold/persistence | Usually detector and rules; specialized counting may be needed |
| Loitering/after-hours/breaks | Longer continuous intervals, entries/exits, shifts, exceptions | Dwell intervals, gaps, schedules, permitted identity associations | Usually tracking/rules; evaluate identity and coverage limits |
| Tailgating/access mismatches | Synchronized passage video, reader events, door state where available | Matched/ambiguous/unmatched references, group/visitor policy | Mainly correlation; additional vision work may be necessary |
| Falls/prone person | Permitted temporal examples and ordinary floor/bending activities | Event start/end, participant tracks, visibility, ambiguous cases | Often a temporal action model or calibrated temporal rules |
| Possible fighting | Permitted video of interactions plus ordinary teamwork/gestures | Temporal interaction labels, participants, reviewer uncertainty | Often a temporal model; image boxes alone are insufficient |
| Running | Motion sequences in the target view and ordinary walking | Action interval; calibration if estimating physical speed | Temporal model and/or calibrated motion rules |
| PPE | Actual workwear/PPE in actual camera views, including occlusion | Person/equipment boxes or associations; present/absent/unknown where visible | Often fine-tuning for specific equipment and image scale |
| Removal/return/left behind | Before/during/after footage, lighting changes, occlusions, authorized changes | Object/zone state and event intervals | Scene rules or trained recognition depending on the case |
| Named tools | Actual tools at operational distance, many viewpoints, similar tools | Tool classes/boxes; item identifiers supplied by tags/business records | Often custom recognition; serial identity may need tags |
| Camera faults/tampering | Normal day/night, covered/blurred/moved-camera examples, maintenance logs | Fault type and interval, baseline view, telemetry | Often rules plus calibration; optional learned detector |
| Fire/gas/door/safety inputs | Approved gateway manual, wiring/interface map, sanitized alarm messages | Device/source state, timestamps, camera mapping, response policy | No visual training for receiving sensor alarms |
| Visual smoke/flame | Licensed/authorized representative footage and confounders | Temporal/region annotations and known limits | Specialized model/site evaluation; independent protection remains |
| Notifications/cases/reports | Recipient roles, schedules, escalation/closure policies, sample cases | Workflow rules and expected outcomes | No model training required |
| Conversational search | Camera vocabulary, query examples, actual indexed events | Expected structured filters, allowed evidence, ambiguity/denial outcomes | Begin with retrieval and prompting; no custom LLM training required initially |
| Voice commands/Tamil | Approved spoken queries, varied speakers/noise, corrected transcripts | Transcript, language, intended query | Evaluate pretrained speech; adapt only for measured needs |
| Server/network/storage health | Supported device metrics/manuals and fault scenarios | Thresholds, critical areas, maintenance policy | No model training required |

**Step 4 — Preserve video quality and provenance**

Keep original camera exports where available. Avoid messaging-app compression, screen recordings, heavy crops, and edited compilations as the sole data source. Common containers such as MP4/MKV are usable if the chosen tools decode their actual codec; an extension alone is insufficient.

For each recording retain source_id, site/camera/session IDs, original filename, checksum, recorded start/timezone or explicit unknown, duration, resolution, frame-rate/timebase information, codec, lighting/weather/context, approved purpose, license/permission reference, and transformation history. Record whether it is genuine operational footage, safely staged, public licensed data, or synthetic.

Keep full temporal context around action events and a mapping from each derived clip/frame back to the original recording. Do not invent timestamps when they are unavailable. When downsampling or transcoding, preserve frame/time mapping and track variable frame rate correctly. Continuous uneventful footage matters for measuring false alarms.

For safe planned scenarios, use an approved test area and appropriate supervision. Do not create actual fights, hazardous falls, fire, smoke exposure, or bypassed safety equipment to obtain training data. Use suitable existing licensed material or professionally managed safe tests, and document their domain limitations.

**Step 5 — Annotate in a suitable tool**

Use an approved self-hosted CVAT instance for sensitive site footage when feasible. Follow its supported installation instructions; do not assume this kit has installed it. On a small laptop, annotation services may need to run separately from the full application stack. Hosted annotation is an alternative only when the data owner permits that destination. [CVAT installation](https://docs.cvat.ai/docs/administration/basics/installation/)

Suggested workflow:

1. Create a project for a compatible annotation task and define its label set. Keep object detection, temporal actions, and specialized tools logically separated where their schemas differ.
2. Create tasks tied to source camera/session records and add approved videos or images.
3. Annotate boxes for visible objects; use persistent anonymous tracks for sequence evaluation.
4. Record occlusion, truncation, visibility, and uncertain labels according to written instructions. Do not infer an employee's identity.
5. Review interpolated tracks and any auto-generated labels manually. Auto-annotation is a draft, not ground truth.
6. Add reviewed action start/end intervals and participant references. If the chosen export does not represent those intervals, maintain a separately versioned temporal annotation file and conversion script.
7. Review disagreements, correct them, then export the master annotations and a training-compatible format.

CVAT projects share label definitions across their tasks; its documented task/import/export workflow supports preparing datasets for downstream training. UI labels may change with version. [Projects](https://docs.cvat.ai/docs/workspace/projects/), [tasks](https://docs.cvat.ai/docs/workspace/tasks-page/), [import](https://docs.cvat.ai/docs/dataset_management/import-datasets/), [export](https://docs.cvat.ai/docs/dataset_management/export-datasets/)

Use COCO or an appropriate YOLO export for detection according to the selected trainer, MOT-compatible export for anonymous tracking, and a model-specific temporal dataset for actions. YOLO detection labels use class ID and normalized center/width/height coordinates; they do not by themselves describe an action over time. [Ultralytics detection format](https://docs.ultralytics.com/datasets/detect/), [CVAT MOT](https://docs.cvat.ai/docs/dataset_management/formats/format-mot/)

**Step 6 — Write the labeling rules before bulk annotation**

Decide which classes are required and what counts as a positive, negative, ambiguous, or unobservable example. Define minimum visibility, occlusion treatment, box conventions, track continuity, event boundaries, and label versioning.

PPE needs special care: not visible does not mean absent. A helmet lying on a shelf does not establish helmet use by a person. A person lying on the floor does not establish a medical diagnosis. Object removal is not a theft label. Preserve what the image or linked records support.

Have a second reviewer inspect a meaningful sample and difficult cases; record disagreement and adjudication. Keep label counts and missing-condition reports. Specify how ignored/unknown annotations are translated for each training library so unlabeled visible objects do not accidentally become negative examples.

**Step 7 — Split data before deriving training samples**

Define a group by original recording/session/event, and where applicable by site/camera/participant. Keep related footage and derived frames in the same group. Hold out separate days/sessions for same-camera deployment evaluation and separate cameras/sites for generalization claims. Overlapping views of the same incident must not leak across splits.

A 70/15/15 train/validation/test split is a possible starting convention, not a universal requirement. Choose enough independent events and conditions for each split. Training changes model weights; validation chooses settings; the locked test estimates final performance. Maintain separate site-acceptance material controlled by a reviewer. Fit preprocessing and create augmentations only using the permitted training partition. [Data-leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html)

Do not randomly distribute adjacent frames from one clip between train and test. Thousands of nearly identical frames do not become thousands of independent events. If you repeatedly tune after examining test errors, retire that test set into development and create a new independent final assessment.

**Step 8 — Decide how much data to collect**

There is no defensible universal number of uploaded images that makes this product industry ready. Required coverage depends on camera geometry, class variety, rare events, background variation, acceptable misses, and false-alert burden.

For the first data audit, an illustrative starting packet is 3–5 short clips per available camera view, approximately 1–3 minutes each, from genuinely different conditions, plus relevant longer intervals for dwell/absence cases. This packet helps inspect format and coverage; it is not a training sufficiency or acceptance threshold.

Next, annotate a representative evaluation subset and run a pretrained baseline. Collect more data where the measured errors occur. Expand independent positive events and long normal sequences, then compare learning curves and held-out results. Action models may need substantial independent sequences; increasing duplicate frames cannot replace missing event diversity. Keep difficult negatives such as kneeling, teamwork, shadows, steam, legitimate tool movement, visitors, and shift changes.

Before procurement or a training commitment, require a per-model data/compute estimate derived from the inspected data. Report event counts, camera-hours, scene coverage, and confidence/uncertainty with results.

**Step 9 — Train on an approved machine**

Use a local/on-premise GPU training machine by default for private footage. A rented GPU is an option only after approval of data transfer, provider, access, retention, and budget. Do not upload employee footage to a public notebook or public dataset repository. Download approved model dependencies before disconnected operation, with licenses and hashes recorded.

Your previously inspected laptop has about 4 GB VRAM and 11.7 GB usable RAM. It can support development and some small experiments; do not promise it can train every action model or run the whole production stack concurrently. Training capacity and 24/7 inference capacity are different decisions.

Give the training environment the versioned train/validation data, grouped manifests, labels, class map, chosen base-model reference/license, training configuration, and output directory. The evaluator receives the locked test set separately. Use 04_MODEL_TRAINING_PROMPT.md to direct the work. No generic training command is supplied here because the correct command, labels, losses, input sequence length, and resource settings depend on the selected model.

Track code revision, environment, seed, dataset hashes, parameters, metrics, and output artifacts. MLflow is one optional tool for these records; a clear local run manifest is sufficient initially. [MLflow tracking](https://www.mlflow.org/docs/latest/tracking/)

Temporal models need their own data pipeline. For example, NVIDIA's action-recognition documentation describes temporal RGB/flow inputs; this is evidence that video action training differs from ordinary bounding-box detection, not a requirement to use that toolkit. [NVIDIA action recognition](https://docs.nvidia.com/tao/tao-toolkit/latest/text/cv_finetuning/pytorch/action_recognition_net.html)

**Step 10 — Evaluate before installing a model**

Measure each use case separately. Include event precision/recall, false alerts per camera-hour, detection delay, scene-specific failures, and sample counts. Use count/duration/tracking metrics where relevant. Model-training accuracy alone is insufficient.

For live alert evaluation, test the detector plus tracker, persistence rules, schedules, and deduplication as a whole. Review independently labeled normal/unalerted footage to estimate misses. Evaluate export/quantization changes again; a faster converted model can behave differently.

Deploy only an approved artifact with model checksum, class map, input preprocessing, thresholds, supported runtime, evaluated conditions, model card, and rollback version. Register it in the application; run in shadow mode and inspect actual events before enabling operational alerts. Keep experimental and accepted models visibly distinct.

**Step 11 — Provide integration and query fixtures**

Access, fire, inventory, and notification functions generally need integration specifications and sanitized records, not detector training images. Include real field names, event/state values, timezone/time precision, authentication method description without secrets, duplicate/delay behavior, rate limits, and heartbeat/error examples. Keep stable pseudonymous IDs where relationships must be tested; pseudonymization alone does not make data anonymous.

For conversational evaluation, provide questions paired with expected filters, permitted evidence IDs, counts, and outcomes such as clarification_required, insufficient_coverage, or access_denied. Use immutable fixture snapshots for reproducibility. Actual runtime incident records belong in the database/index; avoid baking a changing incident history into model weights.

For speech evaluation, supply approved command recordings and verbatim corrected transcripts, plus intended filters. Keep recordings from the same speaker/session grouped when evaluating generalization. Record speech retention permissions. No employee face-enrollment set is required for the baseline system.

**Step 12 — Establish production acceptance**

The final product needs accepted application tests, real camera/gateway tests, model evaluations on representative unseen data, target-load benchmarks, permissions/security testing, backup restoration, outage recovery, trained responders, and the PDF's site pilot. More uploads alone cannot establish these properties.

Do not mark a required feature accepted while it depends on missing hardware, labels, approvals, or model validation. Keep the dependency visible and complete other work. The original PDF, full build plan, and 91-feature traceability are in reference/.

**What you should supply first, given your current situation**

1. The bundled requirements and build plan.
2. Your completed site brief, with unknowns explicitly marked.
3. Any permitted sample workplace videos already available, with source metadata. If none exist, say so; do not invent them.
4. A camera access plan: one borrowed/test camera is enough to begin physical connectivity work.
5. Names/models or manuals for planned access and alarm systems, when available.

Begin application development and pretrained evaluation first. Build the annotation/training pipeline when footage exists and a measurable model gap has been identified.
