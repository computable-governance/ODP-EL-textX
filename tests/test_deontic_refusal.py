"""
Layer 3 — the shared embargo and permit check (2.3.0-1).

el_engine._deontic_refusal() is advance() Steps 5 and 6, also used by
declare_violation() for each candidate declaration Action. Its reasons and
blocked_by tokens are the ones both sites gave before it existed; these
tests pin the helper directly and check that both sites refuse with what
it returns.
"""
from el_engine import TokenRef, _deontic_refusal, _find_action
from test_ledger_blocked_by import _runtime


def test_embargo_first_then_permit():
    rt = _runtime(("stopE", "Ag"))
    spec, state = rt._spec, rt.current_state()
    use, _ = _find_action(spec, "use")
    assert _deontic_refusal(spec, state, "Ag", "use", use) == (
        "active embargo 'stopE' blocks action",
        TokenRef("stopE", "embargo", "Ag", "active", 0))

    state = _runtime().current_state()
    assert _deontic_refusal(spec, state, "Ag", "use", use) == (
        "required permit 'useP' not held by actor",
        TokenRef("useP", "permit", "Ag", None, None))

    state = _runtime(("useP", "Ag")).current_state()
    assert _deontic_refusal(spec, state, "Ag", "use", use) == (None, None)


def test_undeclared_action_skips_the_permit_check():
    rt = _runtime(("stopE", "Ag"))
    spec = rt._spec
    assert _deontic_refusal(spec, _runtime().current_state(), "Ag", "use") == (None, None)
    # Step 5 still applies: stopE's for_action is "use".
    assert _deontic_refusal(spec, rt.current_state(), "Ag", "use")[0] == (
        "active embargo 'stopE' blocks action")


def test_both_sites_refuse_with_the_helper_result():
    for grants in ((("useP", "Ag"), ("stopE", "Ag")), ()):
        rt = _runtime(*grants)
        use, _ = _find_action(rt._spec, "use")
        expected = _deontic_refusal(rt._spec, rt.current_state(), "Ag", "use", use)
        record = rt.advance("use", "Ag")
        assert (record.reason, record.blocked_by) == expected

    for grants in ((("recB", "Gate"), ("declP", "Dog"), ("declE", "Dog")),
                   (("recB", "Gate"),)):
        rt = _runtime(*grants)
        decl, _ = _find_action(rt._spec, "declRec")
        expected = _deontic_refusal(rt._spec, rt.current_state(), "Dog", "declRec", decl)
        record = rt.declare_violation("recB", "Dog", at_tick=5)
        assert (record.reason, record.blocked_by) == expected
