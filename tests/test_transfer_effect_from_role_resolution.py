"""
Layer 3 — el_engine.py's live `transfer` DeonticEffect handler (AM-85).

Fixes the from_role/to_role resolution asymmetry AM-82 diagnosed but
deliberately left unfixed (see that entry's "Known, deliberately unfixed
asymmetry" note, and the matching note in el_kripke.py's
_build_transfer_index() docstring): to_role was already resolved via role
membership with a graceful literal-name fallback
(`[... for a in state.actors if a.role_name == to_role] or [to_role]`);
from_role got no such resolution at all — it was matched directly against
`t.holder`, which only ever worked if from_role happened to literally
equal an actor's own name. A genuine role name passed as from_role never
matched anything: the transfer silently did nothing, no error, no log
entry explaining why.

There was no existing test exercising this handler via live execution at
all before this amendment — AM-82's own tests
(tests/test_hybrid_t9_transfer.py) are Kripke-side/state-only, built
against scenarios/probes/transfer_probe.el, which is itself explicitly
documented as Kripke-tier/disposable ("not expected to be touched again").
This file adds a small, focused, throwaway inline probe (parse_string(),
same pattern as tests/test_discharge_burden.py) exercising the handler
directly via el_engine.advance()/el_runtime.Runtime, distinct from that
Kripke probe.

Probe shape: Holder fills sourceRole, Target fills targetRole -- Holder's
own name deliberately does NOT equal "sourceRole", so a test that passes
here could not have passed against the pre-fix code (which matched
t.holder == from_role literally).
"""
from el_engine import enroll
from el_parser import parse_string
from el_runtime import Runtime

_PROBE = """
enterprise specification TransferHandlerProbe

party Holder {
    holds mainBurden
    holds fallbackBurden
    holds unfilledFromBurden
}

party Target {}

burden mainBurden {
    state: active
    discharge_mode: eventual
    description: "AM-85 probe: from_role given as a real role name -- also the actual bug case, since Holder's own name does not equal sourceRole"
}

burden fallbackBurden {
    state: active
    discharge_mode: eventual
    description: "AM-85 probe: from_role omitted, falls back to the invoking actor"
}

burden unfilledFromBurden {
    state: active
    discharge_mode: eventual
    description: "AM-85 probe: from_role names a role nobody currently fills"
}

commitment mainCommitment {
    by: Holder
    obligation: "AM-85 probe obligation 1"
    creates_burden: mainBurden
}

commitment fallbackCommitment {
    by: Holder
    obligation: "AM-85 probe obligation 2"
    creates_burden: fallbackBurden
}

commitment unfilledFromCommitment {
    by: Holder
    obligation: "AM-85 probe obligation 3"
    creates_burden: unfilledFromBurden
}

community TransferHandlerProbeCommunity {
    objective: "Exercise the live transfer DeonticEffect's from_role/to_role resolution symmetry fix (AM-85)"

    role sourceRole
        {
            action doTransfer {
                description: "from_role given as a real role name, resolved via role membership"
                actor: sourceRole
                effect transfer mainBurden from sourceRole to targetRole
            }

            action doTransferNoFromRole {
                description: "from_role omitted -- falls back to the invoking actor, unchanged"
                actor: sourceRole
                effect transfer fallbackBurden to targetRole
            }

            action doTransferUnfilledFrom {
                description: "from_role names a role nobody currently fills"
                actor: sourceRole
                effect transfer unfilledFromBurden from emptyRole to targetRole
            }
        }

    role targetRole
        {}

    role emptyRole
        description: "Declared but never filled by any actor -- exercises the or [eff.from_role] literal fallback"
        {}
}
"""


def _build_probe_runtime() -> Runtime:
    result = parse_string(_PROBE, validate=True)
    assert result.ok, result.errors
    rt = Runtime.build_from_spec(result.model)
    # Role membership has no grammar construct in this DSL (no "fills"/
    # "member" binding -- an Action's actor: roleX is descriptive only,
    # per DOC-03), so it's assigned in Python, same pattern
    # scenarios/probes/transfer_probe.el's own docstring documents and
    # el_api.py's scenario builders already use.
    state = enroll(rt._state, "Holder", "sourceRole")
    state = enroll(state, "Target", "targetRole")
    return Runtime(state, rt._spec)


def _token(state, name, holder=None):
    for t in state.tokens:
        if t.token_name == name and (holder is None or t.holder == holder):
            return t
    raise AssertionError(f"no TokenInstance named '{name}'" + (f" held by '{holder}'" if holder else ""))


def test_transfer_resolves_from_role_via_role_membership():
    """Also the AM-82 regression case: Holder's own name ("Holder") does
    not equal the role name ("sourceRole") used as from_role, so this
    could only pass against the fixed code -- pre-fix, `t.holder ==
    from_role` would compare "Holder" == "sourceRole" and never match,
    leaving mainBurden silently stuck with Holder."""
    rt = _build_probe_runtime()
    before = _token(rt._state, "mainBurden")
    assert before.holder == "Holder"

    record = rt.advance("doTransfer", "Holder", {})
    assert record.outcome == "ok"
    assert record.effects == ("transferred 'mainBurden' from 'Holder' to ['Target']",)

    after = _token(rt._state, "mainBurden")
    assert after.holder == "Target"
    assert after.state == "active"


def test_transfer_from_role_omitted_falls_back_to_invoking_actor():
    """Confirms the actor_name fallback (from_role absent entirely) still
    works unchanged post-fix: actor_name is already a concrete actor, not
    a role name, and must not be re-resolved through role lookup."""
    rt = _build_probe_runtime()
    before = _token(rt._state, "fallbackBurden")
    assert before.holder == "Holder"

    record = rt.advance("doTransferNoFromRole", "Holder", {})
    assert record.outcome == "ok"
    assert record.effects == ("transferred 'fallbackBurden' from 'Holder' to ['Target']",)

    after = _token(rt._state, "fallbackBurden")
    assert after.holder == "Target"


def test_transfer_from_role_names_an_unfilled_role_degrades_gracefully():
    """from_role ("emptyRole") is a real, declared role, but nobody fills
    it. Role-membership resolution returns [], so the `or [eff.from_role]`
    fallback kicks in -- exactly like it always has for to_role -- and
    attempts a literal match against the string "emptyRole". No actor is
    literally named that here, so nothing matches: the token stays with
    its actual holder (Holder), outcome is still 'ok', and no 'transferred'
    effect is logged for it. Same degrade-gracefully-not-crash behavior
    the pre-fix code already had for any from_role that didn't literally
    match a holder -- this scenario's outcome is unchanged by the fix,
    only *how* it gets there changed (a real fallback attempt now, not
    the only code path there ever was)."""
    rt = _build_probe_runtime()

    record = rt.advance("doTransferUnfilledFrom", "Holder", {})
    assert record.outcome == "ok"
    assert record.effects == ()

    after = _token(rt._state, "unfilledFromBurden")
    assert after.holder == "Holder"
