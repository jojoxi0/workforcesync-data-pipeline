# Data model

| Schema/table | Grain and key |
|---|---|
| `source.change` | One immutable source version; generated `change_id` |
| `source.scenario` | One applied deterministic seed scenario |
| `raw.<entity>` | One source identifier per pipeline run; original JSONB |
| `staging.<entity>` | One accepted business key in the most recent committed batch |
| `analytics.dim_person` | Current person; `person_id` |
| `analytics.dim_classification` | Current classification; `classification_id` |
| `analytics.fact_employment` | Current employment contract; `employment_id` |
| `analytics.employment_history` | Observed contract version; `(employment_id, updated_at)` |
| `audit.pipeline_run` | One pipeline invocation; UUID `run_id` |
| `audit.entity_run` | Counts and interval per entity/run |
| `audit.pipeline_watermark` | Successful boundary per pipeline/entity |
| `quarantine.record` | One rejected source record/reason per attempted run |

Person contains first/last name, email, and active/inactive status. Classification contains name and department. Employment contains person/classification foreign keys, full_time/part_time/contract type, active/ended/leave status, and start/end dates. Dates are inclusive operational values; headcount queries use status, not implicit date inference.

All typed records include `updated_at`, `is_deleted`, and `pipeline_run_id`. Source IDs differ from business IDs: the duplicate fixture intentionally has two source IDs describing the same person. Soft-deleted parents remain referentially available; analytical joins filter them for current counts.

Raw/quarantine may contain sensitive payloads in a real deployment. This demonstration uses synthetic `example.test` addresses. Before using real data, add least-privilege roles, retention, access control, and source authentication.

`rows_loaded` equals inserted + updated + deleted. A first-seen tombstone is an insert; `rows_deleted` counts existing nondeleted rows transitioning to deleted. Replays with an equal/older version count as zero loaded. `rows_extracted - rows_rejected` is the accepted row count, including accepted no-ops. Failed transactional writes have zero committed load counts.
