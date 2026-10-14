# Template instructions

These JSON/JSONL files describe proposed application/data contracts. They are NOT universal training formats, ready-to-import CVAT schemas, finished annotations, or observed events. Example records are marked example_only. Null values mean not supplied, not zero or approval.

- source_manifest.template.json: one record per original recording or source image, with provenance and permitted use.
- camera_inventory.template.json: configuration inventory without credentials.
- annotation_policy.template.json: proposed initial classes and labeling decisions; tailor to the selected use case.
- temporal_events.example.jsonl: illustrative event intervals in seconds relative to a source; convert to the selected trainer's format.
- dataset_manifest.template.json: immutable grouped split membership and dataset provenance.
- integration_record.example.json: sanitized external-message contract example, not a real alarm.
- query_evaluation.example.jsonl: an illustrative search test requiring a separately defined fixture snapshot.
- model_release.template.json: artifact/runtime/evaluation/approval record; templates must never be auto-promoted.

Keep original annotations in the labeling tool's native export and generate model-specific COCO/YOLO/MOT/temporal datasets through validated conversions. Do not merge example records into a real dataset. Replace placeholder identifiers deliberately; retain the example flag until a record represents reviewed real data. A schema flag alone does not enforce production permissions or approval.
