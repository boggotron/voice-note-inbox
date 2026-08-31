#!/usr/bin/env python3
"""Validate every schema and fixture for issue #2 (Schemas, JSON contracts &
synthetic fixtures).

This is the test loop for this task: there is no other test framework in the
repository yet (CI wiring is tracked separately in #4). It:

  1. Meta-validates all four JSON Schemas under schemas/ against the
     JSON Schema draft 2020-12 meta-schema.
  2. Validates every fixture under fixtures/ against its *intended* schema,
     with the expected outcome (valid/invalid) spelled out per fixture
     group, matching fixtures/MANIFEST.md.
  3. Exits non-zero if any fixture's actual outcome does not match its
     expected outcome, or if any schema is itself invalid.

Usage:
    python3 scripts/validate_fixtures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = ROOT / "schemas"
FIXTURES_DIR = ROOT / "fixtures"

FAILURES: list[str] = []
PASSES: list[str] = []


def record(ok: bool, label: str, detail: str = "") -> None:
    line = f"{'PASS' if ok else 'FAIL'}: {label}" + (f" -- {detail}" if detail else "")
    (PASSES if ok else FAILURES).append(line)
    print(line)


def load_schemas() -> tuple[dict[str, dict], Registry]:
    schemas = {}
    for path in sorted(SCHEMAS_DIR.glob("*.schema.json")):
        doc = json.loads(path.read_text())
        try:
            Draft202012Validator.check_schema(doc)
            record(True, f"schema meta-valid: {path.relative_to(ROOT)}")
        except Exception as exc:  # noqa: BLE001
            record(False, f"schema meta-valid: {path.relative_to(ROOT)}", str(exc))
        schemas[path.name] = doc

    resources = [
        (doc["$id"], Resource(contents=doc, specification=DRAFT202012))
        for doc in schemas.values()
    ]
    registry = Registry().with_resources(resources)
    return schemas, registry


def make_validator(schema: dict, registry: Registry) -> Draft202012Validator:
    return Draft202012Validator(schema, registry=registry)


def check_instance(validator: Draft202012Validator, instance, label: str, expect_valid: bool) -> None:
    errors = list(validator.iter_errors(instance))
    is_valid = not errors
    ok = is_valid == expect_valid
    detail = ""
    if not ok:
        if expect_valid:
            detail = "expected VALID but got errors: " + "; ".join(e.message for e in errors[:3])
        else:
            detail = "expected INVALID but instance validated cleanly"
    elif not expect_valid:
        detail = "correctly rejected: " + errors[0].message
    record(ok, label, detail)


def load_json_strict(path: Path):
    return json.loads(path.read_text())


def main() -> int:
    schemas, registry = load_schemas()

    meta_validator = make_validator(schemas["meta.schema.json"], registry)
    model_output_validator = make_validator(schemas["model-output.schema.json"], registry)
    enriched_validator = make_validator(schemas["enriched-record.schema.json"], registry)
    dead_letter_validator = make_validator(schemas["dead-letter-record.schema.json"], registry)
    approval_enum = schemas["enriched-record.schema.json"]["properties"]["approval_state"]["enum"]

    # --- fixtures/valid/ -----------------------------------------------
    valid_dir = FIXTURES_DIR / "valid"
    for name in ["meta-01.json", "meta-02.json"]:
        instance = load_json_strict(valid_dir / name)
        check_instance(meta_validator, instance, f"valid/{name} vs meta.schema.json", True)
    for name in ["model-output-01.json", "model-output-02.json"]:
        instance = load_json_strict(valid_dir / name)
        check_instance(model_output_validator, instance, f"valid/{name} vs model-output.schema.json", True)
    for name in ["enriched-record-01.json", "enriched-record-02.json"]:
        instance = load_json_strict(valid_dir / name)
        check_instance(enriched_validator, instance, f"valid/{name} vs enriched-record.schema.json", True)
    for name in ["dead-letter-record-01.json", "dead-letter-record-02.json"]:
        instance = load_json_strict(valid_dir / name)
        check_instance(dead_letter_validator, instance, f"valid/{name} vs dead-letter-record.schema.json", True)

    # --- fixtures/incomplete-metadata/ (must FAIL meta.schema.json) ----
    incomplete_dir = FIXTURES_DIR / "incomplete-metadata"
    for path in sorted(incomplete_dir.glob("*.json")):
        instance = load_json_strict(path)
        check_instance(meta_validator, instance, f"incomplete-metadata/{path.name} vs meta.schema.json", False)

    # --- fixtures/wrong-mode/ (structurally VALID; business rule elsewhere) --
    wrong_mode_dir = FIXTURES_DIR / "wrong-mode"
    for path in sorted(wrong_mode_dir.glob("*.json")):
        instance = load_json_strict(path)
        check_instance(meta_validator, instance, f"wrong-mode/{path.name} vs meta.schema.json (schema-valid; workflow must still reject by business rule)", True)
        if instance.get("mode") == "Idea Inbox":
            record(False, f"wrong-mode/{path.name} sanity check", "fixture mode is 'Idea Inbox', does not exercise the wrong-mode case")
        else:
            record(True, f"wrong-mode/{path.name} sanity check", f"mode={instance.get('mode')!r} != 'Idea Inbox'")

    # --- fixtures/malformed-json/ (must fail to PARSE, not schema-validated) --
    malformed_dir = FIXTURES_DIR / "malformed-json"
    for path in sorted(malformed_dir.glob("*.json")):
        text = path.read_text()
        try:
            json.loads(text)
            record(False, f"malformed-json/{path.name} parse check", "expected a JSON parse error but file parsed successfully")
        except json.JSONDecodeError as exc:
            record(True, f"malformed-json/{path.name} parse check", f"parse failed as expected: {exc}")

    # --- fixtures/duplicate-event/ (both VALID; same source_id/captured_at) --
    dup_dir = FIXTURES_DIR / "duplicate-event"
    dup_instances = {}
    for path in sorted(dup_dir.glob("*.json")):
        instance = load_json_strict(path)
        check_instance(meta_validator, instance, f"duplicate-event/{path.name} vs meta.schema.json", True)
        dup_instances[path.name] = instance
    keys = {(i["source_id"], i["captured_at"]) for i in dup_instances.values()}
    record(
        len(dup_instances) >= 2 and len(keys) == 1,
        "duplicate-event/ fixtures share one (source_id, captured_at) idempotency key",
        f"keys found: {keys}",
    )

    # --- fixtures/golden-eval/ ------------------------------------------
    golden_dir = FIXTURES_DIR / "golden-eval"
    urgencies_seen: set[str] = set()
    confidences_seen: set[str] = set()
    combos_seen: set[tuple[str, str]] = set()
    approval_states_seen: set[str] = set()

    for case_dir in sorted(p for p in golden_dir.iterdir() if p.is_dir()):
        meta_instance = load_json_strict(case_dir / "meta.json")
        check_instance(meta_validator, meta_instance, f"golden-eval/{case_dir.name}/meta.json vs meta.schema.json", True)

        model_instance = load_json_strict(case_dir / "expected-model-output.json")
        check_instance(model_output_validator, model_instance, f"golden-eval/{case_dir.name}/expected-model-output.json vs model-output.schema.json", True)

        approval_instance = load_json_strict(case_dir / "expected-approval-behavior.json")
        state = approval_instance.get("expected_approval_state")
        ok = state in approval_enum
        record(ok, f"golden-eval/{case_dir.name}/expected-approval-behavior.json expected_approval_state in enriched-record approval_state enum", f"value={state!r}, enum={approval_enum}")

        if not model_instance.get("errors"):
            urgency = model_instance.get("urgency")
            confidence = model_instance.get("confidence")
            urgencies_seen.add(urgency)
            confidences_seen.add(confidence)
            combos_seen.add((urgency, confidence))
        approval_states_seen.add(state)

    expected_levels = {"low", "medium", "high"}
    record(
        urgencies_seen == expected_levels,
        "golden-eval/ covers all urgency values at least once",
        f"seen={urgencies_seen}",
    )
    record(
        confidences_seen == expected_levels,
        "golden-eval/ covers all confidence values at least once",
        f"seen={confidences_seen}",
    )
    record(
        combos_seen == {(u, c) for u in expected_levels for c in expected_levels},
        "golden-eval/ covers the full urgency x confidence cross product (9/9)",
        f"seen {len(combos_seen)}/9 combos",
    )
    record(
        {"not_requested", "pending"}.issubset(approval_states_seen),
        "golden-eval/ covers multiple approval-behavior values (not_requested and pending)",
        f"seen={approval_states_seen}",
    )

    print()
    print(f"{len(PASSES)} passed, {len(FAILURES)} failed")
    if FAILURES:
        print("\nFailures:")
        for f in FAILURES:
            print(" -", f)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
