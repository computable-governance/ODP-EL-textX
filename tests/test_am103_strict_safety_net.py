"""
AM-103 — static warnings for strict burdens without a deployment safety
net; available-actions marks embargoed obligations; the embargoed/unpermitted
strict-discharge deadlock pinned as current behaviour.

A blocking-compelled strict burden is to be violated through an external,
authorised violation declaration (a later amendment), which needs a
deadline to judge against and a ViolationResponse to act on:

  - [W-19]: a strict burden whose deadline has no elapsed-time magnitude
    (none, prose, or a bare number) — el_engine._has_deadline_magnitude();
  - [W-20]: a strict burden no ViolationResponse names in on_violation_of.

Both are advisory (AM-89 channel), top-level and inline tokens alike.

available-actions: an obligation whose action an active embargo the actor
holds covers is listed as "obligated_blocked" — exactly when the engine's
Step 5 refuses it.

Known open finding, pinned as current behaviour (see CONCEPTS_INDEX,
"A strict burden whose discharge is itself blocked deadlocks"): when the
holder cannot perform the discharging action (an embargo covers it, or its
required permit was revoked), the engine refuses every non-discharging
action and time, never violates the burden, and only discharge_burden()
ends it; both builders show a dead end with AF and EF false. These tests
record that behaviour; they are expected to change with the violation-
declaration and freeze-scope amendments.
"""
import contextlib
import io

import pytest

import el_api
from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_kripke import ObligationState, build_kripke_from_runtime, build_kripke_model
from el_parser import parse, parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _codes(src, code):
    result = parse_string(src)
    assert result.ok, result.errors
    return [w for w in result.warnings if w.startswith(code)]


def _burden_spec(burden_body, extra=""):
    return f"""
enterprise specification StrictNetProbe
agent Holder {{ holds probeBurden }}
burden probeBurden {{
    for_action: "doIt"
    state: active
{burden_body}
}}
community C {{
    objective: "probe strict-burden warnings"
    role r {{ action doIt {{ actor: r }} }}
}}
commitment HolderDoes {{ by: Holder obligation: "do it" creates_burden: probeBurden }}
{extra}
"""


_VR = """
violation_response ProbeLate {
    on_violation_of: probeBurden
    obligates: Holder
    response_kind: escalate
}
"""


# ── [W-19] ────────────────────────────────────────────────────────────────────

def test_w19_no_deadline():
    (w,) = _codes(_burden_spec("    discharge_mode: strict"), "[W-19]")
    assert "Strict burden 'probeBurden' has no deadline." in w


@pytest.mark.parametrize("deadline", ["clinical session", "5"])
def test_w19_deadline_without_magnitude(deadline):
    src = _burden_spec(f'    deadline: "{deadline}"\n    discharge_mode: strict')
    (w,) = _codes(src, "[W-19]")
    assert f"has deadline '{deadline}', which carries no elapsed-time magnitude" in w


def test_w19_silent_with_magnitude():
    src = _burden_spec('    deadline: "15 minutes"\n    discharge_mode: strict')
    assert _codes(src, "[W-19]") == []


def test_w19_silent_for_eventual():
    assert _codes(_burden_spec("    discharge_mode: eventual"), "[W-19]") == []


def test_w19_w20_cover_inline_tokens():
    src = """
enterprise specification InlineStrictProbe
agent Holder { }
community C {
    objective: "probe inline strict burdens"
    role r {
        burden inlineBurden { for_action: "doIt" state: active discharge_mode: strict }
        action doIt { actor: r }
    }
}
"""
    result = parse_string(src)
    assert result.ok, result.errors
    assert any(w.startswith("[W-19] Strict burden 'inlineBurden'") for w in result.warnings)
    assert any(w.startswith("[W-20] Strict burden 'inlineBurden'") for w in result.warnings)


# ── [W-20] ────────────────────────────────────────────────────────────────────

def test_w20_no_violation_response():
    src = _burden_spec('    deadline: "15 minutes"\n    discharge_mode: strict')
    (w,) = _codes(src, "[W-20]")
    assert "Strict burden 'probeBurden' is named by no ViolationResponse" in w
    assert "Not needed if the enforcement point discharges the burden atomically" in w


def test_w20_silent_when_named():
    src = _burden_spec('    deadline: "15 minutes"\n    discharge_mode: strict', _VR)
    assert _codes(src, "[W-20]") == []


def test_w20_silent_for_eventual():
    assert _codes(_burden_spec("    discharge_mode: eventual"), "[W-20]") == []


def test_tracked_scenarios():
    """Consent: prose deadline and no ViolationResponse. Referral: both
    strict burdens have 48-hour deadlines, none has a ViolationResponse."""
    consent = _quiet(parse, "scenarios/consent/consent_scenario.el")
    gaps = [w for w in consent.warnings if w.startswith(("[W-19]", "[W-20]"))]
    assert len(gaps) == 2
    assert gaps[0].startswith("[W-19] Strict burden 'seekConsentObligation' has deadline 'clinical session'")
    assert gaps[1].startswith("[W-20] Strict burden 'seekConsentObligation' is named by no ViolationResponse")
    referral = _quiet(parse, "scenarios/referral/referral_scenario.el")
    assert not [w for w in referral.warnings if w.startswith("[W-19]")]
    assert sorted(w.split("'")[1] for w in referral.warnings if w.startswith("[W-20]")) == [
        "escalationNoticeBurden", "referralInitiationBurden",
    ]


# ── available-actions: "obligated_blocked" matches the engine's Step 5 ───────

_AVAILABLE = """
enterprise specification ObligatedBlockedProbe
agent Worker { holds fileBurden holds logBurden holds fileEmbargo }
burden fileBurden { for_action: "fileIt" state: active discharge_mode: eventual }
burden logBurden  { for_action: "logIt"  state: active discharge_mode: eventual }
embargo fileEmbargo { for_action: "fileIt" state: active }
community C {
    objective: "probe obligated_blocked"
    role r {
        action fileIt { actor: r }
        action logIt  { actor: r }
    }
}
commitment WorkerFiles { by: Worker obligation: "file" creates_burden: fileBurden }
commitment WorkerLogs  { by: Worker obligation: "log"  creates_burden: logBurden }
"""


def _available_runtime():
    spec = parse_string(_AVAILABLE, validate=False).model
    state = enroll(initial_state(), "Worker")
    for token in ("fileBurden", "logBurden", "fileEmbargo"):
        state = grant_token(state, token_from_spec(spec, token, "Worker", 0))
    return Runtime(state, spec)


def test_available_actions_obligated_blocked_parity(monkeypatch):
    monkeypatch.setattr(el_api, "_runtime", _available_runtime())
    entries = {a.action: a.reason for a in el_api.get_available_actions("Worker").available_actions}
    assert entries == {"fileIt": "obligated_blocked", "logIt": "obligated"}
    for action, reason in entries.items():
        rec = _available_runtime().advance(action, "Worker")
        refused_by_embargo = rec.outcome == "blocked" and "embargo" in rec.reason
        assert refused_by_embargo is (reason == "obligated_blocked"), (action, rec.reason)


# ── Known open finding: strict burden whose discharge is itself blocked ──────

_DEADLOCK_EMBARGO = """
enterprise specification DeadlockEmbargo
agent Gate   { holds recordBurden holds recordEmbargo }
agent Worker { holds readPermit holds chatBurden }
burden recordBurden { for_action: "recordIt" state: active deadline: "10 minutes" discharge_mode: strict }
burden chatBurden   { for_action: "chat" state: active deadline: "10 minutes" discharge_mode: eventual }
permit readPermit   { for_action: "readData" state: active }
embargo recordEmbargo { state: active }
community C {
    objective: "deadlock probe"
    event pinged
    role gateRole   { action recordIt { actor: gateRole inhibited_by_embargo recordEmbargo } }
    role workerRole {
        action readData { actor: workerRole requires_permit readPermit }
        action chat     { actor: workerRole }
        action ping     { actor: workerRole emits: pinged }
    }
}
commitment GateRecords { by: Gate obligation: "record" creates_burden: recordBurden }
commitment WorkerChats { by: Worker obligation: "chat" creates_burden: chatBurden }
violation_response RecordLate { on_violation_of: recordBurden obligates: Gate response_kind: escalate }
"""

_DEADLOCK_PERMIT = """
enterprise specification DeadlockPermit
party Authority { }
agent Gate   { holds examinePermit holds examineBurden }
agent Worker { holds chatBurden }
burden examineBurden { for_action: "examine" state: pending deadline: "10 minutes" triggered_by: alarm discharge_mode: strict }
burden chatBurden    { for_action: "chat" state: active deadline: "10 minutes" discharge_mode: eventual }
permit examinePermit { for_action: "examine" state: PERMIT_STATE }
embargo afterRevokeEmbargo { for_action: "unrelated" state: pending }
authorization ExamineAuth {
    authority: Authority
    to_agent: Gate
    grants_permit: examinePermit
    revocable: true
    on_revocation: activate afterRevokeEmbargo
}
community C {
    objective: "deadlock probe"
    event alarm
    role gateRole   { action examine { actor: gateRole requires_permit examinePermit } }
    role workerRole {
        action raiseAlarm { actor: workerRole emits: alarm }
        action chat       { actor: workerRole }
    }
}
commitment GateExamines { by: Gate obligation: "examine" creates_burden: examineBurden }
commitment WorkerChats  { by: Worker obligation: "chat" creates_burden: chatBurden }
violation_response ExamineLate { on_violation_of: examineBurden obligates: Gate response_kind: escalate }
"""


def _spec(src):
    result = parse_string(src, validate=False)
    assert result.ok, result.errors
    return result.model


def _embargo_case():
    spec = _spec(_DEADLOCK_EMBARGO)
    state = initial_state()
    for actor in ("Gate", "Worker"):
        state = enroll(state, actor)
    for token, holder in [("recordBurden", "Gate"), ("recordEmbargo", "Gate"),
                          ("readPermit", "Worker"), ("chatBurden", "Worker")]:
        state = grant_token(state, token_from_spec(spec, token, holder, 0))
    return Runtime(state, spec)


def _permit_case():
    """Revoke before the trigger fires (revocation is refused once the
    strict burden is actionable), then fire it."""
    spec = _spec(_DEADLOCK_PERMIT.replace("PERMIT_STATE", "active"))
    state = initial_state()
    for actor in ("Authority", "Gate", "Worker"):
        state = enroll(state, actor)
    for token, holder in [("examinePermit", "Gate"), ("examineBurden", "Gate"),
                          ("chatBurden", "Worker")]:
        state = grant_token(state, token_from_spec(spec, token, holder, 0))
    rt = Runtime(state, spec)
    assert rt.revoke_authorization("ExamineAuth").outcome == "ok"
    assert rt.advance("raiseAlarm", "Worker").outcome == "ok"
    return rt


_CASES = {
    "embargo": (_embargo_case, "recordIt", "recordBurden", "active embargo 'recordEmbargo'"),
    "permit": (_permit_case, "examine", "examineBurden", "required permit 'examinePermit' not held"),
}


def _state_of(rt, token):
    return next(t.state for t in rt.current_state().tokens if t.token_name == token)


@pytest.mark.parametrize("case", sorted(_CASES))
def test_known_deadlock_engine(case):
    make, action, token, reason = _CASES[case]
    rec = make().advance(action, "Gate")
    assert rec.outcome == "blocked" and reason in rec.reason

    for call in (lambda r: r.advance_clock(50), lambda r: r.fire_event("pinged")):
        rec = call(make())
        assert rec.outcome == "blocked" and "strict burden" in rec.reason

    rt = make()
    assert rt.advance("chat", "Worker").outcome == "ok"   # a discharge is allowed
    assert rt.advance_clock(50).outcome == "blocked"       # time still cannot pass
    rt.check_live_violations()
    rt.fire_violation_responses()
    assert _state_of(rt, token) == "active"                # never violated

    rt = make()
    assert rt.discharge_burden(token).outcome == "ok"      # the only exit
    assert _state_of(rt, token) == "discharged"


@pytest.mark.parametrize("builder", ["static", "hybrid"])
@pytest.mark.parametrize("case", sorted(_CASES))
def test_known_deadlock_verifier(case, builder):
    make, _, token, _ = _CASES[case]
    if builder == "hybrid":
        km = _quiet(build_kripke_from_runtime, make(), horizon=10)
    elif case == "embargo":
        km = _quiet(build_kripke_model, _spec(_DEADLOCK_EMBARGO), horizon=10)
    else:
        # The static builder has no revocation (T7 is hybrid-only): an
        # inactive permit is its analogue of a revoked one.
        km = _quiet(build_kripke_model,
                    _spec(_DEADLOCK_PERMIT.replace("PERMIT_STATE", "pending")), horizon=10)
    dead_ends = [w for w in km.worlds
                 if w.obligation_dict().get(token) == ObligationState.PENDING
                 and not km.successors(w)]
    assert dead_ends
    assert km.check_obligation(token).satisfied is False
    assert km.check_permission(token).satisfied is False
    assert km.EF(km.initial, f"violated:{token}") is False
