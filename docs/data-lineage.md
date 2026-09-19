# Data lineage

| REST source | Raw evidence | Normalization / validation | Accepted batch | Warehouse |
|---|---|---|---|---|
| `/api/v1/persons` | `raw.person` | `normalize('person')`, `deduplicate`, `validate` | `staging.person` | `analytics.dim_person` |
| `/api/v1/classifications` | `raw.classification` | `normalize('classification')`, `deduplicate`, `validate` | `staging.classification` | `analytics.dim_classification` |
| `/api/v1/employments` | `raw.employment` | `normalize('employment')`, `deduplicate`, `validate` | `staging.employment` | `analytics.fact_employment`, `analytics.employment_history` |

Every layer links to the audit run; rejected original payloads link to the same run in `quarantine.record`.

| Field | Rule |
|---|---|
| Text | Strip surrounding whitespace; empty, N/A, NULL and NONE become null (case insensitive) |
| Business/foreign keys | Preserve case; require nonempty text |
| Names/departments | Preserve meaningful source casing; trim whitespace |
| Email | Trim and lowercase; validate basic syntax |
| Status/type | Lowercase and check accepted values |
| Dates | Parse ISO dates; sentinel end dates become null |
| `updated_at` | Parse ISO timestamp with timezone; reject values beyond snapshot boundary |
| `is_deleted` | Accept booleans or explicit true/false strings; reject ambiguous values |
| Duplicate key | Most recent timestamp, then greatest source ID; loser enters quarantine |

The source service supplies trusted modification timestamps when it appends versions. It never infers a modification time from the business start date.
