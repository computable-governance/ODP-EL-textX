"""
Runtime.claim()/Runtime.decline() verification (DN_005 §3 Option C).

toolchain/el_engine.py's claim()/decline() are thin wrappers that
synthesize a live accept/reject Evaluation-equivalent fact
(LiveEvaluation) and route it through the EXISTING C1/7a-claim gating
logic inside advance() — no duplicate transition logic. This mirrors
tests/test_erequesting_claiming_scenario.py's discipline: empirical,
against the real parsed scenario/engine, not asserted-from-design.
Reuses that same scenario file and seeded-state helper pattern, but
calls Runtime.claim()/Runtime.decline() directly instead of advance()
with a pre-declared spec Evaluation.

Note on providerB/DiagnosticProviderB vs providerA/DiagnosticProviderA
in the two decline()-as-no-op tests below: the scenario file
unconditionally spec-declares an accept Evaluation for exactly
(providerAClaimBurden, DiagnosticProviderA). Live facts are
additive-only per DN_005 §3 (accept_evaluations is a set union, no
subtraction path) — so a live decline() can never override an
already-declared spec-level accept for the same pair. This is by
design, not a limitation of this implementation. providerB has no
spec-declared Evaluation at all, so it's the pair that actually
exercises decline()'s no-op behavior uninterfered with.
"""
from el_engine import TokenInstance, enroll, grant_token, initial_state
from el_parser import parse
from el_runtime import Runtime

SCENARIO = "scenarios/erequesting_claiming/erequesting_claiming_scenario.el"


def _spec():
    result = parse(SCENARIO, validate=True)
    assert result.ok, result.errors
    return result.model


def _seeded_state():
    state = initial_state()
    state = enroll(state, "DiagnosticProviderA", role_name="eligibleProviderA")
    state = enroll(state, "DiagnosticProviderB", role_name="eligibleProviderB")
    state = grant_token(state, TokenInstance(
        token_name="providerAClaimBurden", kind="burden", holder="DiagnosticProviderA",
        state="claimable", discharge_mode="eventual", priority="high",
        granted_at_tick=0, deadline="4 hours from referral delegation",
        for_action="claimReferralA",
    ))
    state = grant_token(state, TokenInstance(
        token_name="providerBClaimBurden", kind="burden", holder="DiagnosticProviderB",
        state="claimable", discharge_mode="eventual", priority="high",
        granted_at_tick=0, deadline="4 hours from referral delegation",
        for_action="claimReferralB",
    ))
    return state


def _runtime():
    return Runtime(_seeded_state(), _spec())


def test_runtime_claim_activates_holder_and_lapses_sibling():
    runtime = _runtime()
    record = runtime.claim("providerAClaimBurden", "DiagnosticProviderA")

    assert record.outcome == "ok"
    by_name = {t.token_name: t for t in runtime.current_state().tokens}
    assert by_name["providerAClaimBurden"].state == "active"
    assert by_name["providerBClaimBurden"].state == "lapsed"
    assert record.effects == (
        "claimed burden 'providerAClaimBurden'",
        "lapsed burden 'providerBClaimBurden' held by 'DiagnosticProviderB' "
        "(sibling 'providerAClaimBurden' claimed, group 'referralClaimGroup')",
    )


def test_runtime_decline_is_a_no_op():
    """providerB/DiagnosticProviderB has no spec-declared Evaluation at all
    (confirmed against the scenario file: it declares exactly one
    Evaluation, targeting provider A only) -- decline()'s live reject
    fact is the only thing in play here, uninterfered with by any
    spec-level accept, making this a genuine no-op test. (providerA/
    DiagnosticProviderA cannot be used for this: that scenario
    unconditionally spec-declares an accept Evaluation for exactly that
    pair, which decline()'s live reject fact can never override -- the
    gating set is a union with no subtraction path, by design.)"""
    runtime = _runtime()
    record = runtime.decline("providerBClaimBurden", "DiagnosticProviderB")

    assert record.outcome == "ok"
    assert record.effects == ()
    by_name = {t.token_name: t for t in runtime.current_state().tokens}
    assert by_name["providerAClaimBurden"].state == "claimable"
    assert by_name["providerBClaimBurden"].state == "claimable"


def test_runtime_claim_unknown_token_raises_keyerror():
    runtime = _runtime()
    try:
        runtime.claim("noSuchBurden", "DiagnosticProviderA")
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_runtime_claim_when_not_claimable_returns_blocked():
    runtime = _runtime()
    # First claim succeeds, transitioning the token out of 'claimable'.
    first = runtime.claim("providerAClaimBurden", "DiagnosticProviderA")
    assert first.outcome == "ok"

    # Second claim on the same, now-active token finds nothing 'claimable'.
    second = runtime.claim("providerAClaimBurden", "DiagnosticProviderA")
    assert second.outcome == "blocked"
    assert second.reason is not None


def test_runtime_decline_then_claim_still_works():
    """Same providerB/DiagnosticProviderB pair as
    test_runtime_decline_is_a_no_op, for the same reason (no
    spec-declared Evaluation to interfere) -- declining first must not
    block a subsequent claim() on the same token."""
    runtime = _runtime()
    declined = runtime.decline("providerBClaimBurden", "DiagnosticProviderB")
    assert declined.outcome == "ok"
    assert declined.effects == ()

    by_name = {t.token_name: t for t in runtime.current_state().tokens}
    assert by_name["providerBClaimBurden"].state == "claimable"

    claimed = runtime.claim("providerBClaimBurden", "DiagnosticProviderB")
    assert claimed.outcome == "ok"
    by_name = {t.token_name: t for t in runtime.current_state().tokens}
    assert by_name["providerBClaimBurden"].state == "active"
    assert by_name["providerAClaimBurden"].state == "lapsed"
