"""
2.2.0-1 — golden test of the published specifications.

Pins, for each of the 14 shipped scenarios (scenarios/**/*.el) and the 16
published examples (tests/examples/**/*.el):
  - whether it parses;
  - the validator's errors and warnings, in order, as (tag, message text);
  - the policy_values seeded by el_engine.initial_state(spec).

The expected results are in published_specs_golden.json, next to this
file, generated at 2cdfe23 and identical at tag v2.1.0. Any change to a
published file, to the set of published files, or to what the toolchain
reports for them fails this test.

Regenerate only when a change is intended (never run automatically), from
the repository root:

    python tests/test_published_specs_unchanged.py --write

and review the diff of tests/published_specs_golden.json before committing.
`--root <checkout>` generates against another checkout's toolchain and
files (for example a worktree of an earlier tag); without --write the
result is printed.
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN = Path(__file__).resolve().parent / "published_specs_golden.json"

PUBLISHED_FILES = [
    "scenarios/consent/consent_scenario.el",
    "scenarios/consent/federation_consent_scenario.el",
    "scenarios/ecommerce/ecommerce_scenario.el",
    "scenarios/ereferral/ereferral_model.el",
    "scenarios/erequesting_claiming/erequesting_claiming_scenario.el",
    "scenarios/fhir/generated_governance.el",
    "scenarios/gp_referral/gp_referral_scenario.el",
    "scenarios/probes/transfer_probe.el",
    "scenarios/procurement_tender/procurement_tender_scenario.el",
    "scenarios/referral/referral_scenario.el",
    "scenarios/specialist_pool/specialist_pool_scenario.el",
    "scenarios/terms_of_engagement/external_agent_access_scenario.el",
    "scenarios/terms_of_engagement/public_data_portal_scenario.el",
    "scenarios/vendor/ai_vendor_probe.el",
    "tests/examples/comparisons/invalid_comparison_in_step.el",
    "tests/examples/comparisons/invalid_comparison_type.el",
    "tests/examples/comparisons/invalid_envelope_currency.el",
    "tests/examples/comparisons/invalid_envelope_membership.el",
    "tests/examples/comparisons/invalid_fact_key_clash.el",
    "tests/examples/comparisons/ok_cover_check.el",
    "tests/examples/standing/invalid_standing_fields.el",
    "tests/examples/standing/invalid_standing_in_group.el",
    "tests/examples/standing/invalid_term_end_type.el",
    "tests/examples/standing/ok_cover_for_the_term.el",
    "tests/examples/typed_values/invalid_calendar_date.el",
    "tests/examples/typed_values/invalid_currency_code.el",
    "tests/examples/typed_values/invalid_instant_valid.el",
    "tests/examples/typed_values/invalid_policy_value_type.el",
    "tests/examples/typed_values/invalid_range_ends.el",
    "tests/examples/typed_values/ok_typed_values.el",
]

_TAG = re.compile(r"\[([^\]]+)\] ?(.*)", re.DOTALL)


def _split(message, root):
    """(tag, text) of one message; the checkout's path is dropped from
    syntax errors so the result does not depend on where it lives."""
    message = message.replace(str(root) + "/", "")
    m = _TAG.match(message)
    return [m.group(1), m.group(2)] if m else [None, message]


def published_files(root):
    """Every .el file under scenarios/ and tests/examples/, repo-relative."""
    return sorted(
        p.relative_to(root).as_posix()
        for d in ("scenarios", "tests/examples")
        for p in (root / d).rglob("*.el")
    )


def generate(root):
    """The golden data for the checkout at `root`, using its toolchain."""
    root = Path(root).resolve()
    sys.path.insert(0, str(root / "toolchain"))
    from el_parser import parse
    from el_engine import initial_state

    files = {}
    for rel in PUBLISHED_FILES:
        result = parse(str(root / rel), validate=True)
        files[rel] = {
            "parsed": result.model is not None,
            "errors": [_split(e, root) for e in result.errors],
            "warnings": [_split(w, root) for w in result.warnings],
            "policy_values": (
                [list(pv) for pv in initial_state(result.model).policy_values]
                if result.model is not None else None
            ),
        }
    return {"files": files}


def _dump(data):
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def test_published_specs_unchanged():
    assert len(PUBLISHED_FILES) == 30
    assert published_files(REPO_ROOT) == sorted(PUBLISHED_FILES), (
        "The set of published .el files changed; update PUBLISHED_FILES "
        "and regenerate (see the module docstring)."
    )
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert list(expected["files"]) == PUBLISHED_FILES
    actual = json.loads(_dump(generate(REPO_ROOT)))
    for rel in PUBLISHED_FILES:
        assert actual["files"][rel] == expected["files"][rel], rel
    assert actual == expected


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate the published-specs golden data.")
    ap.add_argument("--root", default=str(REPO_ROOT), help="checkout to generate from")
    ap.add_argument("--write", action="store_true", help=f"overwrite {GOLDEN.name}")
    args = ap.parse_args()
    text = _dump(generate(args.root))
    if args.write:
        GOLDEN.write_text(text, encoding="utf-8")
        print(f"wrote {GOLDEN}")
    else:
        sys.stdout.write(text)
