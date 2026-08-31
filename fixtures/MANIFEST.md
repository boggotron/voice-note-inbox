# Fixture manifest

**Provenance: every file under `fixtures/` is 100% synthetic/fabricated.** No
file in this directory originates from a real Superwhisper recording, a real
transcript, real personal data, or real OpenAI API output. All names, places,
companies (e.g. "Riverside Plumbing Co", "Northwind Traders", "Acme Supply",
"Aurora"), and identifiers (e.g. `sw-fixture-*`, `sw-golden-*`, all UUIDs,
all `source_path_hash` values) were authored by hand for this repository as
test data. This file exists so CI (tracked in #4) can assert that no real
data was ever substituted in.

This manifest is produced and reviewed as part of issue #2. If you add a new
fixture file, add a row for it here in the same pull request.

## `fixtures/valid/`

Synthetic, schema-valid instances of every record type, used as the
happy-path baseline for validation.

| File | Schema | Notes |
|---|---|---|
| `meta-01.json`, `meta-02.json` | `schemas/meta.schema.json` | Two independent synthetic Superwhisper captures, mode `Idea Inbox`. |
| `model-output-01.json`, `model-output-02.json` | `schemas/model-output.schema.json` | Standalone structured-output-shaped results corresponding to `meta-01`/`meta-02`. |
| `enriched-record-01.json`, `enriched-record-02.json` | `schemas/enriched-record.schema.json` | Full enriched records embedding the above meta/model-output content. |
| `dead-letter-record-01.json` | `schemas/dead-letter-record.schema.json` | Synthetic terminal-failure (auth error) diagnostic record, no transcript content. |
| `dead-letter-record-02.json` | `schemas/dead-letter-record.schema.json` | Synthetic exhausted-retries (429) diagnostic record with a multi-attempt history. |

## `fixtures/incomplete-metadata/`

Synthetic `meta.json` instances that are syntactically valid JSON but fail
`schemas/meta.schema.json` validation, for the intake workflow's
incomplete-metadata rejection path (plan Test Plan: "incomplete metadata").

| File | Schema | Expected result | Notes |
|---|---|---|---|
| `missing-transcript.json` | `schemas/meta.schema.json` | INVALID | `transcript` property entirely absent. |
| `empty-first-pass-note.json` | `schemas/meta.schema.json` | INVALID | `first_pass_note` present but empty string (`minLength: 1` violation). |
| `missing-mode.json` | `schemas/meta.schema.json` | INVALID | `mode` property entirely absent. |

## `fixtures/wrong-mode/`

Synthetic `meta.json` instances that ARE structurally valid against
`schemas/meta.schema.json` (mode is deliberately not schema-restricted to
`"Idea Inbox"`, see that schema's description) but must be rejected by the
intake workflow's business rule requiring an exact `"Idea Inbox"` mode match
(plan Test Plan: "wrong mode").

| File | Schema | Expected schema result | Notes |
|---|---|---|---|
| `quick-capture.json` | `schemas/meta.schema.json` | VALID (schema) / rejected by workflow | `mode: "Quick Capture"`. |
| `meeting-notes.json` | `schemas/meta.schema.json` | VALID (schema) / rejected by workflow | `mode: "Meeting Notes"`. |

## `fixtures/malformed-json/`

Files that are **not valid JSON at all** (parse failures), for the intake
workflow's malformed-write rejection path (plan Test Plan: "malformed JSON"),
e.g. simulating Superwhisper being interrupted mid-write.

| File | Expected result | Notes |
|---|---|---|
| `truncated.json` | JSON parse error | File cuts off mid-string/mid-object, unbalanced braces/quotes. |
| `trailing-comma.json` | JSON parse error | Otherwise well-formed object with an illegal trailing comma. |
| `empty-file.json` | JSON parse error | Zero-byte file. |

These are intentionally excluded from schema validation in the validator
script (a JSON Schema validator cannot run against text that isn't JSON);
the script instead asserts each one fails to parse.

## `fixtures/duplicate-event/`

Two byte-identical, individually schema-valid `meta.json` fixtures sharing
the same `source_id` and `captured_at`, simulating a filesystem watcher
firing twice for the same underlying capture (e.g. temp-file write plus
final rename). Used to test the intake workflow's idempotency key
(`source_id`/path hash), per plan Test Plan: "duplicate event" and "repeat
its event and confirm idempotency."

| File | Schema | Notes |
|---|---|---|
| `event-a-first-delivery.json` | `schemas/meta.schema.json` | VALID; first delivery of the event. |
| `event-b-second-delivery.json` | `schemas/meta.schema.json` | VALID; duplicate delivery, same `source_id`. |

## `fixtures/golden-eval/`

Nine synthetic evaluation cases, one per cell of the full
`urgency` x `confidence` grid (`low`/`medium`/`high` x `low`/`medium`/`high`),
each a directory containing:

- `meta.json` — the synthetic input capture (validates against
  `schemas/meta.schema.json`; its `transcript` and `first_pass_note` fields
  together are the "transcript-like fixture" input for this case).
- `expected-model-output.json` — the expected structured model result
  (validates against `schemas/model-output.schema.json`).
- `expected-approval-behavior.json` — a small, non-schema-bound annotation
  (`expected_approval_state` + `rationale`) documenting what a **future**
  approval gate would illustratively decide for this urgency/confidence
  combination. **This is a design/judgment call, not current behavior**: the
  MVP pipeline defined in the plan document always writes
  `approval_state: "not_requested"` on every enriched record, because no
  approval workflow exists yet (tracked separately, out of scope for #2).
  These annotations exist so the eval harness in #7 has forward-looking
  expected data to compare against once that gate is built, and so the
  `not_requested`/`pending` values in `schemas/enriched-record.schema.json`'s
  `approval_state` enum both have at least one concrete example. The
  illustrative rule used to assign these: `pending` when `confidence == low`
  or `urgency == high`, `not_requested` otherwise. `approved`/`rejected` are
  not used in this set because they only make sense after a human has
  already acted on a `pending` item, not as the immediate output of
  processing a fresh capture.

| Case | urgency | confidence | expected_approval_state |
|---|---|---|---|
| `01-low-low` | low | low | pending |
| `02-low-medium` | low | medium | not_requested |
| `03-low-high` | low | high | not_requested |
| `04-medium-low` | medium | low | pending |
| `05-medium-medium` | medium | medium | not_requested |
| `06-medium-high` | medium | high | not_requested |
| `07-high-low` | high | low | pending |
| `08-high-medium` | high | medium | pending |
| `09-high-high` | high | high | pending |

All subject matter (plumbing companies, clients, projects, patients,
prescriptions, server names) is invented for this fixture set.

## Validation

Every fixture is validated by `scripts/validate_fixtures.py` (Python,
`jsonschema` + `referencing`, JSON Schema draft 2020-12) against its intended
schema, as described above. Run it with `python3 scripts/validate_fixtures.py`
from the repository root. See that script's own output for the current
pass/fail status of every fixture file.
