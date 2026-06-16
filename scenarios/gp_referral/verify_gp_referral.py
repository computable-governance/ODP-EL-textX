#!/usr/bin/env python3
"""
verify_gp_referral.py
=====================
Layer 4 (Kripke) verification of the GP-referral governance scenario.

Answers four verification questions from the scenario header:

  Q1: AF(discharged:referralInitiationBurden)
      Expected YES — discharge_mode: strict; GP must act at first opportunity.

  Q2: AF(discharged:referralResponseBurden)
      Expected NO  — discharge_mode: eventual; specialist may delay indefinitely.
      EF(discharged:referralResponseBurden)
      Expected YES — some path discharges it.

  Q3: AF(objective_satisfied:ReferralFederation)
      Expected NO  — blocked by eventual referralResponseBurden.
      EF(objective_satisfied:ReferralFederation)
      Expected YES — exists a path satisfying all_discharged(referralBurdenGroup).

  Q4: AF(objective_satisfied:SpecialistCommunity)
      Expected NO  — both specialist burdens are eventual.
      EF(objective_satisfied:SpecialistCommunity)
      Expected YES — any_discharged(specialistBurdenGroup); one path discharges at least one.

Usage
-----
    python scenarios/gp_referral/verify_gp_referral.py      # from repo root
    python verify_gp_referral.py                             # from scenario dir
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Path setup ───────────────────────────────────────────────────────────────
# This script may be run from any directory; resolve paths relative to its
# own location so imports always find the toolchain.

_SCRIPT_DIR = Path(__file__).resolve().parent          # scenarios/gp_referral/
_REPO_ROOT  = _SCRIPT_DIR.parent.parent                # project root
_TOOLCHAIN  = _REPO_ROOT / "toolchain"
_SCENARIO   = _SCRIPT_DIR / "gp_referral_scenario.el"

if str(_TOOLCHAIN) not in sys.path:
    sys.path.insert(0, str(_TOOLCHAIN))

from el_parser import parse                            # noqa: E402
from el_kripke import build_kripke_model               # noqa: E402


# ── Expected results (from scenario header comment) ──────────────────────────

EXPECTED: dict[str, bool] = {
    "Q1_AF_referralInitiationBurden":          True,
    "Q2_AF_referralResponseBurden":            False,
    "Q2_EF_referralResponseBurden":            True,
    "Q3_AF_objective_satisfied_Federation":    False,
    "Q3_EF_objective_satisfied_Federation":    True,
    "Q4_AF_objective_satisfied_Specialist":    False,
    "Q4_EF_objective_satisfied_Specialist":    True,
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _sym(b: bool) -> str:
    return "✓" if b else "✗"


def _yesno(b: bool) -> str:
    return "YES" if b else "NO"


def _print_modal(operator: str, prop: str, satisfied: bool) -> None:
    print(f"  {_sym(satisfied)} {operator}({prop}): {_yesno(satisfied)}")


# ── Main verification ─────────────────────────────────────────────────────────

def main() -> int:
    # 1. Parse
    print("=" * 60)
    print("GP-Referral Governance Scenario — Layer 4 Kripke Verification")
    print("=" * 60)
    print(f"\nParsing: {_SCENARIO.relative_to(_REPO_ROOT)}")

    result = parse(_SCENARIO, validate=True)
    if not result.ok:
        print("\n[ERROR] Parse/validation failed:")
        for err in result.errors:
            print(f"  {err}")
        return 1

    if result.errors:
        print("\n[WARN] Validation errors (continuing):")
        for err in result.errors:
            print(f"  {err}")

    print("  Parse OK")

    # 2. Build Kripke model
    print("\nBuilding Kripke model (horizon=10)...")
    km = build_kripke_model(result.model, horizon=10)

    print(f"\n  Worlds : {len(km.worlds)}")
    print(f"  Edges  : {sum(len(v) for v in km.edges.values())}")
    print(f"  Obligations tracked : {list(km.obligation_descriptors.keys())}")
    print(f"  Satisfaction conditions : {list(km.satisfaction_conditions.keys())}")

    # 3. Q1 — AF(discharged:referralInitiationBurden)
    print("\n" + "-" * 60)
    print("Q1: AF(discharged:referralInitiationBurden)")
    print("    discharge_mode: strict — GP must act at first opportunity")
    v_q1_af = km.check_obligation("referralInitiationBurden")
    print(v_q1_af.render())
    actual_q1_af = v_q1_af.satisfied

    # 4. Q2 — AF and EF for referralResponseBurden
    print("\n" + "-" * 60)
    print("Q2: AF(discharged:referralResponseBurden)")
    print("    discharge_mode: eventual — specialist may delay indefinitely")
    v_q2_af = km.check_obligation("referralResponseBurden")
    print(v_q2_af.render())
    actual_q2_af = v_q2_af.satisfied

    print()
    print("Q2: EF(discharged:referralResponseBurden)")
    v_q2_ef = km.check_permission("referralResponseBurden")
    print(v_q2_ef.render())
    actual_q2_ef = v_q2_ef.satisfied

    # 5. Q3 — objective_satisfied:ReferralFederation (AF and EF)
    prop_fed = "objective_satisfied:ReferralFederation"
    print("\n" + "-" * 60)
    print(f"Q3: AF({prop_fed})")
    print("    satisfaction: all_discharged(referralBurdenGroup)")
    q3_af = km.AF(km.initial, prop_fed)
    q3_ef = km.EF(km.initial, prop_fed)
    _print_modal("AF", prop_fed, q3_af)
    print(f"Q3: EF({prop_fed})")
    _print_modal("EF", prop_fed, q3_ef)
    actual_q3_af = q3_af
    actual_q3_ef = q3_ef

    # 6. Q4 — objective_satisfied:SpecialistCommunity (AF and EF)
    prop_spec = "objective_satisfied:SpecialistCommunity"
    print("\n" + "-" * 60)
    print(f"Q4: AF({prop_spec})")
    print("    satisfaction: any_discharged(specialistBurdenGroup)")
    q4_af = km.AF(km.initial, prop_spec)
    q4_ef = km.EF(km.initial, prop_spec)
    _print_modal("AF", prop_spec, q4_af)
    print(f"Q4: EF({prop_spec})")
    _print_modal("EF", prop_spec, q4_ef)
    actual_q4_af = q4_af
    actual_q4_ef = q4_ef

    # 7. PASS / FAIL summary
    actual: dict[str, bool] = {
        "Q1_AF_referralInitiationBurden":          actual_q1_af,
        "Q2_AF_referralResponseBurden":            actual_q2_af,
        "Q2_EF_referralResponseBurden":            actual_q2_ef,
        "Q3_AF_objective_satisfied_Federation":    actual_q3_af,
        "Q3_EF_objective_satisfied_Federation":    actual_q3_ef,
        "Q4_AF_objective_satisfied_Specialist":    actual_q4_af,
        "Q4_EF_objective_satisfied_Specialist":    actual_q4_ef,
    }

    print("\n" + "=" * 60)
    print("SUMMARY — actual vs expected")
    print("=" * 60)

    all_pass = True
    for key, expected_val in EXPECTED.items():
        got = actual[key]
        ok  = got == expected_val
        if not ok:
            all_pass = False
        status = "PASS" if ok else "FAIL"
        mark   = _sym(ok)
        print(f"  {mark} {key:<50s}  got={_yesno(got)}  expected={_yesno(expected_val)}  [{status}]")

    print()
    if all_pass:
        print("RESULT: PASS — all verification checks match expected outcomes")
        return 0
    else:
        print("RESULT: FAIL — one or more checks differ from expected outcomes")
        return 1


if __name__ == "__main__":
    sys.exit(main())
