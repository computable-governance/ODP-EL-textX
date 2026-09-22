"""
Layer 2/4 — AM-93: `delegated_from` as a list.

Grammar today: `(delegated_from+=DelegatedFrom)*` in ObjectBody (same
position — after holds_tokens, before principal_of), each entry with its
own optional `duration`. ISO/IEC 15414 §7.10.1: several parties
collectively become principal of an agent, so an agent may list several
delegators.

Declarative only. The model exposes `EnterpriseObject.delegated_from` as a
list of `DelegatedFrom` records (`.delegator` + `.duration` together);
`delegation_duration` no longer exists. Multi-parent detection
(`parents_of()`, W-16c/d/e, V-08) is untouched — it works from
Delegations / principal_of, not from `delegated_from`.

The two independent `_is_standing_affiliation` twins (el_reasoner.py,
el_kripke.py) treat the entries with SET semantics: a principal_of is
standing iff that principal is not among ANY entry's delegator, so
declaration order and duplicate entries make no difference. The parity
test below runs both twins over a truth table to pin that.

A delegator listed twice in one object parses and is accepted as written
(no de-duplication, no new rule).
"""
import itertools
from types import SimpleNamespace

import pytest

from el_kripke import _is_standing_affiliation as kripke_standing
from el_parser import parse, parse_string
from el_reasoner import _is_standing_affiliation as reasoner_standing
from el_reasoner import standing_parents_of


def _obj(model, name):
    return next(e for e in model.elements if getattr(e, "name", None) == name)


def _entries(model, name):
    return [(e.delegator.name, e.duration) for e in _obj(model, name).delegated_from]


# ── 1. single entry: parse + model shape ─────────────────────────────────

def test_single_delegated_from_is_a_one_entry_list():
    result = parse_string("""
enterprise specification SingleProbe
party P1
agent AgentA {
    delegated_from P1
}
""", validate=False)
    assert result.ok, result.errors
    agent = _obj(result.model, "AgentA")
    assert isinstance(agent.delegated_from, list) and len(agent.delegated_from) == 1
    assert agent.delegated_from[0].delegator is _obj(result.model, "P1")
    assert agent.delegated_from[0].duration == ""      # absent duration is '' (textX default)
    assert not hasattr(agent, "delegation_duration")


def test_single_delegated_from_keeps_its_duration():
    result = parse_string("""
enterprise specification SingleDurationProbe
party P1
agent AgentA {
    delegated_from P1
        duration: "one session"
}
""", validate=False)
    assert result.ok, result.errors
    assert _entries(result.model, "AgentA") == [("P1", "one session")]


def test_object_without_delegated_from_has_empty_list():
    result = parse_string("""
enterprise specification NoneProbe
party P1 { principal_of AgentA }
agent AgentA
agent AgentB { principal_of AgentA }
""", validate=False)
    assert result.ok, result.errors
    for name in ("P1", "AgentA", "AgentB"):       # with a body, and with none
        assert _obj(result.model, name).delegated_from == []


# ── 2. several entries: parse, per-entry durations, position, duplicates ─

@pytest.mark.parametrize("durations", [
    (None, None),
    ("d1", None),
    (None, "d2"),
    ("d1", "d2"),
])
def test_two_entries_keep_per_entry_durations(durations):
    lines = []
    for delegator, dur in zip(("P1", "P2"), durations):
        lines.append(f"    delegated_from {delegator}")
        if dur is not None:
            lines.append(f'        duration: "{dur}"')
    body = "\n".join(lines)
    result = parse_string(f"""
enterprise specification TwoEntryProbe
party P1
party P2
agent AgentA {{
{body}
}}
""", validate=False)
    assert result.ok, result.errors
    assert _entries(result.model, "AgentA") == [
        ("P1", durations[0] or ""),
        ("P2", durations[1] or ""),
    ]


def test_entries_sit_between_holds_and_principal_of():
    result = parse_string("""
enterprise specification PositionProbe
party P1
party P2
party P3
burden tokenT { state: active }
agent AgentB
agent AgentA {
    holds tokenT
    delegated_from P1
        duration: "first"
    delegated_from P2
    delegated_from P3
        duration: "third"
    principal_of AgentB
}
""", validate=False)
    assert result.ok, result.errors
    agent = _obj(result.model, "AgentA")
    assert [t.name for t in agent.holds_tokens] == ["tokenT"]
    assert _entries(result.model, "AgentA") == [("P1", "first"), ("P2", ""), ("P3", "third")]
    assert [a.name for a in agent.principal_of] == ["AgentB"]


def test_principal_of_before_delegated_from_is_still_a_syntax_error():
    """R1 keeps the body position: the change lets entries repeat, it does
    not make the body order-independent."""
    result = parse_string("""
enterprise specification OrderProbe
party P1
agent AgentA {
    principal_of P1
    delegated_from P1
}
""", validate=False)
    assert not result.ok
    assert any(e.startswith("[SYNTAX]") for e in result.errors)


def test_same_delegator_listed_twice_is_accepted_as_written():
    """No de-duplication and no new rule: both entries are kept, each with
    its own duration, and nothing is reported."""
    result = parse_string("""
enterprise specification DuplicateProbe
party P1
agent AgentA {
    delegated_from P1
        duration: "first"
    delegated_from P1
        duration: "second"
}
""", validate=True)
    assert result.ok, result.errors
    assert result.warnings == []
    assert _entries(result.model, "AgentA") == [("P1", "first"), ("P1", "second")]


# ── 3. parity: both _is_standing_affiliation twins, truth table ──────────

_PRINCIPALS = ("A", "B", "C", "D")
_DELEGATORS = ("A", "B", "C")


def _sequences():
    """Every ordered delegator sequence of length 0..3 over {A, B, C}:
    all declaration orders of every subset, plus duplicates."""
    for n in range(0, 4):
        yield from itertools.product(_DELEGATORS, repeat=n)


def _truth_table_model():
    agents = []
    for i, seq in enumerate(_sequences()):
        body = "\n".join(f"    delegated_from {d}" for d in seq)
        agents.append((f"X{i}", seq, f"agent X{i} {{\n{body}\n}}"))
    text = (
        "enterprise specification TruthTableProbe\n"
        + "\n".join(f"party {p}" for p in _PRINCIPALS)
        + "\n"
        + "\n".join(a[2] for a in agents)
    )
    result = parse_string(text, validate=False)
    assert result.ok, result.errors
    return result.model, [(name, seq) for name, seq, _ in agents]


def test_twins_agree_and_use_set_semantics_over_the_truth_table():
    model, agents = _truth_table_model()
    assert len(agents) == 1 + 3 + 9 + 27
    for name, seq in agents:
        agent = _obj(model, name)
        for principal in _PRINCIPALS:
            expected = principal not in set(seq)        # standing iff not any delegator
            r = reasoner_standing(principal, agent)
            k = kripke_standing(principal, agent)
            assert r == k, f"twins disagree: principal={principal} delegated_from={seq}"
            assert r is expected, f"principal={principal} delegated_from={seq}: got {r}"


def test_twins_agree_on_agents_without_the_attribute_or_with_none():
    for agent in (SimpleNamespace(), SimpleNamespace(delegated_from=None),
                  SimpleNamespace(delegated_from=[])):
        assert reasoner_standing("A", agent) is True
        assert kripke_standing("A", agent) is True


# ── 4. paired with ANY of several delegators is non-standing ─────────────

_MULTI_PARENT_SPEC = """
enterprise specification PairedAnyProbe
party P1 {{ principal_of AgentA }}
party P2 {{ principal_of AgentA }}
party P3 {{ principal_of AgentA }}
agent AgentA {{
{entries}
}}
"""


@pytest.mark.parametrize("order", list(itertools.permutations(("P1", "P2"))))
def test_principal_of_paired_with_any_delegator_is_non_standing(order):
    entries = "\n".join(f"    delegated_from {d}" for d in order)
    result = parse_string(_MULTI_PARENT_SPEC.format(entries=entries), validate=True)
    assert result.ok, result.errors
    # P1 and P2 are each paired (with one of the two entries); P3 is not.
    assert standing_parents_of(result.model, "AgentA") == ["P3"]
    assert not any(w.startswith("[W-16e]") for w in result.warnings)


def test_all_principals_paired_leaves_no_standing_parent_and_no_warning():
    """Guards the failure mode a list-valued attribute would otherwise
    cause: a reader that still saw `delegated_from` as one object would
    treat every paired principal_of as standing and emit a false [W-16e].
    [W-16e] itself stays silent here, as asserted.

    AM-95: P1 and P2 are still genuine declared parents of AgentA via the
    delegated_from channel alone (§6.6.8 NOTE 3 — no backing Delegation
    required), so [W-16g] correctly fires for them; it is a distinct
    channel from the principal_of/standing one this test guards."""
    result = parse_string("""
enterprise specification AllPairedProbe
party P1 { principal_of AgentA }
party P2 { principal_of AgentA }
agent AgentA {
    delegated_from P1
    delegated_from P2
}
""", validate=True)
    assert result.ok, result.errors
    assert standing_parents_of(result.model, "AgentA") == []
    assert not any(w.startswith("[W-16e]") for w in result.warnings)
    assert result.warnings == [
        "[W-16g] Agent 'AgentA' has 2 declared parents across all channels: "
        "P1 (delegated_from), P2 (delegated_from). Principals are collectively "
        "responsible (§7.10.1); delegated_from is itself a self-sufficient static "
        "declaration (§6.6.8 NOTE 3) and is counted here even with no backing "
        "Delegation. How these authorities combine is application-defined; the "
        "toolchain does not compose them. See "
        "el_reasoner.all_declared_parents_of(model, 'AgentA')."
    ]


def test_unpaired_principals_are_standing_alongside_a_paired_one():
    result = parse_string("""
enterprise specification UnpairedProbe
party P1 { principal_of AgentA }
party P2
party P3 { principal_of AgentA }
party P4 { principal_of AgentA }
agent AgentA {
    delegated_from P1
    delegated_from P2
}
""", validate=True)
    assert result.ok, result.errors
    assert standing_parents_of(result.model, "AgentA") == ["P3", "P4"]
    assert any(w.startswith("[W-16e]") and "P3, P4" in w for w in result.warnings)


# ── 6. named tracked scenarios: single entries, warnings unchanged ───────

def test_named_scenarios_single_entries_and_warnings_unchanged():
    """AM-95: referral_scenario.el now carries exactly one [W-16g] (a
    genuine tracked-corpus true positive — see AM-95's amendment entry);
    the delegated_from entries themselves are unaffected by it.

    AM-96: consent_scenario.el now carries two genuine [W-16h] true
    positives (aiAnalysisPermit, required but never granted — see
    AM-96's amendment entry); the delegated_from entries checked below
    are unaffected by it."""
    referral = parse("scenarios/referral/referral_scenario.el", validate=True)
    assert referral.ok, referral.errors
    assert referral.warnings == [
        "[W-16g] Agent 'SpecialistClinician' has 2 declared parents across all "
        "channels: GPClinician (gpToSpecialistDelegation, delegated_from), "
        "SpecialistPractice (standing principal_of). Principals are collectively "
        "responsible (§7.10.1); delegated_from is itself a self-sufficient static "
        "declaration (§6.6.8 NOTE 3) and is counted here even with no backing "
        "Delegation. How these authorities combine is application-defined; the "
        "toolchain does not compose them. See "
        "el_reasoner.all_declared_parents_of(model, 'SpecialistClinician')."
    ]
    assert _entries(referral.model, "SpecialistClinician") == [("GPClinician", "referral episode")]
    assert _entries(referral.model, "SpecialistAIAgent") == [("SpecialistClinician", "referral episode")]

    consent = parse("scenarios/consent/consent_scenario.el", validate=True)
    assert consent.ok, consent.errors
    assert consent.warnings == [
        "[W-16h] Action 'performAnalysis' (role 'aiAgentRole', community "
        "'ConsentCommunity') requires permit 'aiAnalysisPermit', but nothing in "
        "this specification grants it — no Authorization names it, no holds "
        "clause (object or role) names it, and no action effect creates it. The "
        "requirement can never be satisfied. Add a grant for 'aiAnalysisPermit', "
        "or remove the requirement if it is no longer needed. See "
        "el_reasoner.ungrantable_permit_requirements(model).",
        "[W-16h] Action 'seekConsent' (role 'aiAgentRole', community "
        "'ConsentCommunity') requires permit 'aiAnalysisPermit', but nothing in "
        "this specification grants it — no Authorization names it, no holds "
        "clause (object or role) names it, and no action effect creates it. The "
        "requirement can never be satisfied. Add a grant for 'aiAnalysisPermit', "
        "or remove the requirement if it is no longer needed. See "
        "el_reasoner.ungrantable_permit_requirements(model).",
    ]
    assert _entries(consent.model, "SpecialistAgent") == [("GPPracticeParty", "referral period")]
    assert _entries(consent.model, "AIDiagnosticAgent") == [("SpecialistAgent", "clinical session")]

    federation = parse("scenarios/consent/federation_consent_scenario.el", validate=True)
    assert federation.ok, federation.errors
    assert len(federation.warnings) == 1
    assert federation.warnings[0].startswith("[W-16e] Agent 'SpecialistParty' has 2 standing")
    assert _entries(federation.model, "AISpecialistAgent") == [("SpecialistParty", "")]
