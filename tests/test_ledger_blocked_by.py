"""
Layer 3 — blocked_by on blocked records.

A refusal by an active embargo (advance() Step 5) names that embargo
instance; a refusal for a required permit not held (Step 6) names the
permit: the actor's latest instance of it, or, if the actor never held it,
state and granted_at_tick None. declare_violation() fills it the same way
for its embargo and permit refusals (the first candidate's refusal). Every
other refusal (role, preconditions, the strict guard, enrolment) leaves it
None. The reason text is unchanged.
"""
import contextlib
import io
from dataclasses import replace

import el_api
from el_engine import TokenRef, enroll, grant_token, initial_state, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_SPEC = """
enterprise specification BlockedByProbe
party Gate
party Dog
party Ag
burden recB { for_action: "rec" state: active deadline: "5 minutes" discharge_mode: strict }
permit declP { for_action: "declRec" state: active }
permit useP { for_action: "use" state: active }
embargo stopE { for_action: "use" state: active }
embargo declE { for_action: "declRec" state: active }
community C {
    objective: "o"
    Gate fills gw
    Dog fills dec
    Ag fills user
    role gw { action rec { actor: gw } }
    role dec {
        action declRec {
            actor: dec
            requires_permit declP
            declares_violation_of recB
        }
    }
    role user {
        action use { actor: user requires_permit useP }
        action prepare { actor: user precondition: "ready" }
    }
}
"""


def _runtime(*grants):
    result = _quiet(parse_string, _SPEC, validate=False)
    assert result.ok, result.errors
    spec = result.model
    state = initial_state(spec)
    for actor, role in (("Gate", "gw"), ("Dog", "dec"), ("Ag", "user")):
        state = enroll(state, actor, role_name=role)
    for grant in grants:
        token, holder = grant[:2]
        tok = token_from_spec(spec, token, holder, 0)
        if len(grant) == 3:
            tok = replace(tok, state=grant[2])
        state = grant_token(state, tok)
    return Runtime(state, spec)


def test_step5_names_the_blocking_embargo():
    rt = _runtime(("useP", "Ag"), ("stopE", "Ag"))
    record = rt.advance("use", "Ag")
    assert record.reason == "active embargo 'stopE' blocks action"
    assert record.blocked_by == TokenRef("stopE", "embargo", "Ag", "active", 0)


def test_step6_names_the_permit_never_held_or_not_active():
    record = _runtime().advance("use", "Ag")
    assert record.reason == "required permit 'useP' not held by actor"
    assert record.blocked_by == TokenRef("useP", "permit", "Ag", None, None)

    record = _runtime(("useP", "Ag", "superseded")).advance("use", "Ag")
    assert record.reason == "required permit 'useP' not held by actor"
    assert record.blocked_by == TokenRef("useP", "permit", "Ag", "superseded", 0)


def test_declaration_refusals_name_the_embargo_or_permit():
    rt = _runtime(("recB", "Gate"), ("declP", "Dog"), ("declE", "Dog"))
    record = rt.declare_violation("recB", "Dog", at_tick=5)
    assert record.reason == "active embargo 'declE' blocks action"
    assert record.blocked_by == TokenRef("declE", "embargo", "Dog", "active", 0)

    record = _runtime(("recB", "Gate")).declare_violation("recB", "Dog", at_tick=5)
    assert record.reason == "required permit 'declP' not held by actor"
    assert record.blocked_by == TokenRef("declP", "permit", "Dog", None, None)

    record = _runtime(("recB", "Gate"), ("declP", "Dog")).declare_violation("recB", "Dog",
                                                                           at_tick=5)
    assert (record.outcome, record.blocked_by) == ("violation", None)


def test_other_refusals_leave_blocked_by_empty():
    rt = _runtime(("useP", "Ag"))
    assert rt.advance("use", "Nobody").blocked_by is None              # not enrolled
    role = rt.advance("use", "Gate")
    assert role.outcome == "blocked" and role.blocked_by is None       # role
    pre = rt.advance("prepare", "Ag")
    assert pre.reason.startswith("precondition") and pre.blocked_by is None
    frozen = _runtime(("recB", "Gate"), ("useP", "Ag")).advance("use", "Ag")
    assert "strict burden 'recB'" in frozen.reason and frozen.blocked_by is None
    early = _runtime(("recB", "Gate"), ("declP", "Dog")).declare_violation("recB", "Dog",
                                                                          at_tick=4)
    assert early.outcome == "blocked" and early.blocked_by is None     # not overdue
    assert rt.advance("use", "Ag").blocked_by is None                  # ok


def test_blocked_by_agrees_with_in_force_at():
    rt = _runtime(("useP", "Ag"), ("stopE", "Ag"))
    record = rt.advance("use", "Ag")
    ref = record.blocked_by
    assert rt.in_force_at(ref.token_name, ref.holder, record.tick) is True

    rt = _quiet(el_api._build_referral_runtime)
    rt.advance("initiateReferral", "GPClinician", facts={
        "Patient must have an active episode of care and clinical indication for referral": True})
    rt.revoke_authorization("patientDataAuthorization")
    record = rt.advance("conductAIExamination", "SpecialistAIAgent", facts={
        "Referral must be active for AI examination to proceed": True,
        "AI agent must hold patientRecordAccessPermitByAuthorization": True})
    ref = record.blocked_by
    assert ref == TokenRef("patientRecordAccessPermitByAuthorization", "permit",
                           "SpecialistAIAgent", "superseded", 0)
    assert rt.in_force_at(ref.token_name, ref.holder, record.tick) is False
    assert rt.in_force_at(ref.token_name, ref.holder, record.tick - 1) is True
