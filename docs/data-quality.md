# Data-quality contract

Validation returns accepted and rejected collections. Rejections drive persisted quarantine rows and a configurable threshold exception; they are not merely printed.

| Category | Enforcement |
|---|---|
| Completeness | All entity fields required except `end_date`; whitespace/sentinels normalized first |
| Uniqueness | Pandas deterministic key deduplication; warehouse primary keys |
| Validity | Basic email format, controlled status/type sets, date parsing and ordered ranges |
| Referential integrity | Employment references checked against existing plus accepted parent keys; database FKs defend the final write |
| Timeliness | Timezone-aware modification timestamps bounded by source snapshot; transactional watermarks |

Error codes include `MISSING_REQUIRED_FIELD`, `DUPLICATE_KEY`, `INVALID_EMAIL`, `INVALID_DATE_RANGE`, `INVALID_TYPE_OR_DATE`, `INVALID_STATUS`, `INVALID_EMPLOYMENT_TYPE`, `INVALID_TIMESTAMP`, `UNKNOWN_CLASSIFICATION`, and `REFERENTIAL_INTEGRITY_FAILURE`.

The email check is syntactic; it does not verify deliverability or claim complete RFC validation. Referential checks include tombstoned parents for historical integrity; current analytical views exclude deleted parents. No arbitrary freshness SLA is invented for synthetic historical data.

Quarantine stores run ID, entity, source ID, code, safe diagnostic text, original JSONB, and detection time. The threshold is rejected/extracted across the whole run, with no division for an empty run. Duplicates count as rejected. Unexpected programming exceptions abort the run instead of being silently treated as ordinary invalid records.

Tests live in `tests/data_quality/`, normalization/extraction tests in `tests/unit/`, and actual routing/rollback assertions in `tests/integration/`.
