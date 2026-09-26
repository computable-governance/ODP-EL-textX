"""
Layer 2 — AM-96: ungrantable permit requirements —
`el_reasoner.grantable_permit_names()` / `ungrantable_permit_requirements()`
and `[W-16h]`.

An Action's `requires_permit` can name a permit that nothing in the
specification ever grants — no `Authorization`, no `holds` clause
(object or role), no action `effect create`. Today this is caught only
at runtime (`el_engine` step 6 / `Runtime.advance()` blocks it, and the
Layer-2 static reasoner `can_perform()` reports it too) — with zero
static diagnostic. Distinct from AM-94's `[W-16f]` (a choice between
co-granted permits, a substitution risk): this is a requirement that is
unsatisfiable from the start, a dead end — worded as a spec-authoring
defect to fix, not an application-composition question.

AM-96 closes the gap:
  - `el_reasoner.grantable_permit_names(model)` — every permit name with
    at least one static source: `Authorization.grants_permit`,
    `EnterpriseObject.holds_tokens`, `Role.holds_tokens` (included on
    the same basis V-15/V-16a already use — see that function's
    docstring), or an action's own `effect create`. Deliberately NOT
    built from Delegation `transfers_burden`/`transfers_token_group` — a
    Delegation transfers an EXISTING token, it does not create one
    (§6.4.7 NOTE 1); treating "some Delegation transfers it" as evidence
    would reproduce V-16a's own circularity for a stricter question.
  - `el_reasoner.ungrantable_permit_requirements(model)` — every
    (action, permit) pair from `required_permits_by_action()` (AM-94,
    reused — not a fifth independent extraction) whose permit is not
    grantable.
  - `el_validator._validate_ungrantable_permit_requirement()` —
    `[W-16h]`, built from the same query (no twin logic), advisory
    (AM-89 channel, never affects `.ok`). When the ungrantable permit is
    ALSO named in a Delegation transfer, the message says so explicitly
    (a separate wording variant, pinned below).
"""
import itertools

from el_parser import parse, parse_string
from el_reasoner import grantable_permit_names, ungrantable_permit_requirements


def _w16h(result):
    return [w for w in result.warnings if w.startswith("[W-16h]")]


_ROLE_HEADER = 'role ProbeRole description: "probe role"'


# ── Ungranted anywhere → warns ─────────────────────────────────────────────

_UNGRANTED_SPEC = f"""
enterprise specification UngrantedAnywhereProbe

party Actor {{}}

permit neverGranted {{
    state: active
    description: "declared but never granted to anyone, anywhere"
}}

community ProbeCommunity {{
    objective: "probe"
    {_ROLE_HEADER} {{
        action doTheThing {{
            actor: Actor
            requires_permit neverGranted
        }}
    }}
}}
"""


def test_permit_granted_nowhere_warns_with_exact_message():
    result = parse_string(_UNGRANTED_SPEC, validate=True)
    assert result.ok, result.errors
    w16h = _w16h(result)
    assert len(w16h) == 1
    assert w16h[0] == (
        "[W-16h] Action 'doTheThing' (role 'ProbeRole', community "
        "'ProbeCommunity') requires permit 'neverGranted', but nothing in this "
        "specification grants it — no Authorization names it, no holds clause "
        "(object or role) names it, and no action effect creates it. The "
        "requirement can never be satisfied. Add a grant for 'neverGranted', or "
        "remove the requirement if it is no longer needed. See "
        "el_reasoner.ungrantable_permit_requirements(model)."
    )
    assert "neverGranted" not in grantable_permit_names(result.model)


# ── Each grant channel, alone, silences the warning ────────────────────────

def test_authorization_only_is_silent():
    spec = f"""
enterprise specification AuthOnlyProbe

party Grantor {{}}
party Actor {{}}

permit p1 {{
    state: active
}}

authorization grantIt {{
    authority: Grantor
    to_agent: Actor
    grants_permit: p1
}}

community ProbeCommunity {{
    objective: "probe"
    {_ROLE_HEADER} {{
        action doTheThing {{
            actor: Actor
            requires_permit p1
        }}
    }}
}}
"""
    result = parse_string(spec, validate=True)
    assert result.ok, result.errors
    assert _w16h(result) == []
    assert "p1" in grantable_permit_names(result.model)


def test_enterprise_object_holds_only_is_silent():
    spec = f"""
enterprise specification ObjectHoldsOnlyProbe

party Actor {{
    holds p1
}}

permit p1 {{
    state: active
}}

community ProbeCommunity {{
    objective: "probe"
    {_ROLE_HEADER} {{
        action doTheThing {{
            actor: Actor
            requires_permit p1
        }}
    }}
}}
"""
    result = parse_string(spec, validate=True)
    assert result.ok, result.errors
    assert _w16h(result) == []
    assert "p1" in grantable_permit_names(result.model)


def test_role_holds_only_is_silent():
    spec = f"""
enterprise specification RoleHoldsOnlyProbe

party Actor {{}}

permit p1 {{
    state: active
}}

community ProbeCommunity {{
    objective: "probe"
    {_ROLE_HEADER} {{
        holds p1

        action doTheThing {{
            actor: Actor
            requires_permit p1
        }}
    }}
}}
"""
    result = parse_string(spec, validate=True)
    assert result.ok, result.errors
    assert _w16h(result) == []
    assert "p1" in grantable_permit_names(result.model)


def test_effect_create_only_is_silent():
    spec = f"""
enterprise specification EffectCreateOnlyProbe

party Actor {{}}

permit p1 {{
    state: active
}}

community ProbeCommunity {{
    objective: "probe"
    {_ROLE_HEADER} {{
        action grantingAction {{
            actor: Actor
            effect create p1
        }}

        action doTheThing {{
            actor: Actor
            requires_permit p1
        }}
    }}
}}
"""
    result = parse_string(spec, validate=True)
    assert result.ok, result.errors
    assert _w16h(result) == []
    assert "p1" in grantable_permit_names(result.model)


def test_granted_and_required_is_silent():
    spec = f"""
enterprise specification GrantedAndRequiredProbe

party Actor {{
    holds p1
}}

permit p1 {{
    state: active
}}

community ProbeCommunity {{
    objective: "probe"
    {_ROLE_HEADER} {{
        action doTheThing {{
            actor: Actor
            requires_permit p1
        }}
    }}
}}
"""
    result = parse_string(spec, validate=True)
    assert result.ok, result.errors
    assert _w16h(result) == []


# ── Delegation-transfer-only: warns, WITH the delegation-transfer note ─────

_GHOST_PERMIT_SPEC = """
enterprise specification DelegatedGhostPermitProbe

party DelegParent {}
party Agent {}

burden groundedBurden {
    state: active
    discharge_mode: eventual
    description: "the one grounded member -- satisfies V-15's at-least-one threshold"
}

permit ghostPermit {
    state: active
    description: "never held, never authorized, never effect-created anywhere -- only 'transferred'"
}

commitment groundingCommitment {
    by: DelegParent
    obligation: "probe obligation"
    creates_burden: groundedBurden
}

token_group probeGroup {
    member: groundedBurden
    member: ghostPermit
}

delegation delegGroup {
    from: DelegParent
    to: Agent
    obligation: "probe obligation"
    transfers_token_group: probeGroup
}

community ProbeCommunity {
    objective: "probe"
    role ProbeRole description: "probe role" {
        action doTheThing {
            actor: Agent
            requires_permit ghostPermit
        }
    }
}
"""


def test_delegation_transfer_only_warns_with_transfer_note():
    """A Delegation naming the permit in its transfer is NOT evidence of
    grantability (§6.4.7 NOTE 1: transfer presupposes, not creates), but
    the [W-16h] message says so explicitly -- distinct wording from the
    plain ungranted-anywhere case above."""
    result = parse_string(_GHOST_PERMIT_SPEC, validate=True)
    assert result.ok, result.errors
    assert "ghostPermit" not in grantable_permit_names(result.model)
    w16h = _w16h(result)
    assert len(w16h) == 1
    assert w16h[0] == (
        "[W-16h] Action 'doTheThing' (role 'ProbeRole', community "
        "'ProbeCommunity') requires permit 'ghostPermit', but nothing in this "
        "specification grants it — no Authorization names it, no holds clause "
        "(object or role) names it, and no action effect creates it, though it "
        "is named in a Delegation transfer (which presupposes, not creates, the "
        "token). The requirement can never be satisfied. Add a grant for "
        "'ghostPermit', or remove the requirement if it is no longer needed. "
        "See el_reasoner.ungrantable_permit_requirements(model)."
    )


# ── Order-invariance ────────────────────────────────────────────────────────

_ORDER_PARTS = {
    "party": "party Actor {}",
    "permit_a": "permit permitA { state: active }",
    "permit_b": "permit permitB { state: active }",
}


def _order_spec(order):
    body = "\n".join(_ORDER_PARTS[k] for k in order)
    return f"""
enterprise specification OrderProbe
{body}
community ProbeCommunity {{
    objective: "probe"
    {_ROLE_HEADER} {{
        action actionA {{
            actor: Actor
            requires_permit permitA
        }}
        action actionB {{
            actor: Actor
            requires_permit permitB
        }}
    }}
}}
"""


def test_w16h_order_invariant_across_all_permutations():
    seen = set()
    for order in itertools.permutations(_ORDER_PARTS.keys()):
        result = parse_string(_order_spec(order), validate=True)
        assert result.ok, (order, result.errors)
        w16h = tuple(sorted(_w16h(result)))
        assert len(w16h) == 2, order
        seen.add(w16h)
    assert len(seen) == 1


# ── grantable_permit_names() / ungrantable_permit_requirements() basics ────

def test_unknown_model_has_no_grantable_names_beyond_what_is_declared():
    result = parse_string(_UNGRANTED_SPEC, validate=False)
    assert grantable_permit_names(result.model) == set()


def test_ungrantable_permit_requirements_matches_w16h_message_content():
    result = parse_string(_UNGRANTED_SPEC, validate=True)
    reqs = ungrantable_permit_requirements(result.model)
    assert len(reqs) == 1
    w16h = _w16h(result)[0]
    assert reqs[0].permit in w16h
    assert reqs[0].action.name in w16h


def test_warnings_never_affect_ok():
    result = parse_string(_UNGRANTED_SPEC, validate=True)
    assert result.ok is True
    assert result.errors == []
    assert len(result.warnings) >= 1


# ── Named tracked scenarios ─────────────────────────────────────────────

def test_consent_scenario_no_longer_produces_w16h():
    """AM-96 found two real, tracked-corpus [W-16h] hits here --
    consent_scenario.el's aiAnalysisPermit was required by both
    aiAgentRole actions (seekConsent, performAnalysis) but granted
    nowhere. AM-97 fixed the scenario content: seekConsent now grants
    aiAnalysisPermit via `effect create ... to aiAgentRole` as a side
    effect of the action executing (the file has no discharged_by-style
    mechanism to hang the grant off seekConsentObligation's discharge
    instead -- see AM-97's amendment entry and the cross-referenced open
    finding in docs/CONCEPTS_INDEX.md). performAnalysis is unchanged,
    still gated by the permit. The rule's own correctness (W-16h firing
    at all, its exact wording, the Delegation-transfer variant) remains
    fully covered by this file's inline probes above, independent of
    this scenario file."""
    result = parse("scenarios/consent/consent_scenario.el", validate=True)
    assert result.ok, result.errors
    # AM-103: scoped to [W-16h], the code this test is about.
    assert not any(w.startswith("[W-16h]") for w in result.warnings), result.warnings


def test_referral_scenario_produces_no_w16h():
    result = parse("scenarios/referral/referral_scenario.el", validate=True)
    assert result.ok, result.errors
    assert _w16h(result) == []


def test_federation_consent_scenario_produces_no_w16h():
    result = parse("scenarios/consent/federation_consent_scenario.el", validate=True)
    assert result.ok, result.errors
    assert _w16h(result) == []
