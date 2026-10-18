"""
2.2.0-7 to 2.2.0-9 — `deadline: <Policy>` (read-only).

A token's deadline may name a Policy instead of quoting a duration:
`deadline: NoticePeriod`. The deadline is the policy's declared duration
value (its initial_value; policy values are read-only), read through one
resolver, el_engine.deadline_text(): by the engine (2.2.0-7), by both
verifier builders (2.2.0-8) and by the validator's deadline warnings
(2.2.0-9). A policy-fed deadline behaves exactly as the same duration
written as a literal; violation lines name the policy.

Layer 1 (grammar), Layer 2 (validator), Layer 3 (runtime) and Layer 4
(Kripke) tests per tests/README.md's strategy.
"""
import contextlib
import io

import pytest

from el_engine import deadline_text, token_from_spec
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_SPEC = """enterprise specification PolicyDeadlineProbe
policy NoticePeriod : {ptype} {{ initial_value: {value} }}
party Supplier {{ holds notice }}
party Watchdog {{ holds declarePermit }}
community C {{
    objective: "o"
    Supplier fills r
    Watchdog fills w
    role r {{ action giveNotice {{ actor: r }} }}
    role w {{ action declareLate {{ actor: w requires_permit declarePermit declares_violation_of notice }} }}
}}
permit declarePermit {{ state: active }}
burden notice {{ for_action: "giveNotice" state: active deadline: {deadline} {mode} }}
commitment noticeCommitment {{ by: Supplier obligation: "give notice" creates_burden: notice }}
"""


def _src(deadline="NoticePeriod", ptype="duration", value="24 hours", mode=""):
    return _SPEC.format(deadline=deadline, ptype=ptype, value=value, mode=mode)


def _model(**kw):
    result = _quiet(parse_string, _src(**kw), validate=False)
    assert result.model is not None, result.errors
    return result.model


def _token(model, name="notice"):
    return next(e for e in model.elements
                if type(e).__name__ == "DeonticToken" and e.name == name)


def _runtime(**kw):
    return _quiet(Runtime.build_from_spec, _model(**kw))


# ── Grammar ──────────────────────────────────────────────────────────────

def test_parses_as_a_policy_reference():
    tok = _token(_model())
    assert not tok.deadline and tok.deadline_policy.name == "NoticePeriod"


def test_literal_deadline_unchanged():
    tok = _token(_model(deadline='"24 hours"'))
    assert tok.deadline == "24 hours" and tok.deadline_policy is None


def test_inline_token_takes_a_policy():
    src = """enterprise specification InlineProbe
policy NoticePeriod : duration { initial_value: 3 days }
community C {
    objective: "o"
    role r { burden inlineNotice { state: active deadline: NoticePeriod } }
}
"""
    result = _quiet(parse_string, src, validate=False)
    assert result.model is not None, result.errors
    inline = result.model.elements[-1].roles[0].holds_tokens[0]
    assert deadline_text(inline) == "3 days"


def test_undeclared_policy_is_refused():
    result = _quiet(parse_string, _src(deadline="NoSuchPolicy"), validate=False)
    assert result.model is None and result.errors[0].startswith("[SEMANTIC]")


# ── Resolver ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kw, text", [
    ({}, "24 hours"),
    ({"value": "1 day"}, "1 day"),
    ({"value": "+5 days"}, "5 days"),                    # 2.1.0 accepts the sign
    ({"value": "-5 days"}, None),                        # not a usable duration
    ({"deadline": '"24 hours"'}, "24 hours"),            # a literal, unchanged
    ({"ptype": "date", "value": "2027-06-30"}, None),    # not of type duration
    ({"ptype": "integer", "value": "5"}, None),
])
def test_deadline_text(kw, text):
    assert deadline_text(_token(_model(**kw))) == text


def test_policy_values_take_precedence_when_passed():
    """For future setting acts; nothing passes policy_values in 2.2.0."""
    tok = _token(_model())
    assert deadline_text(tok, {"NoticePeriod": "48 hours"}) == "48 hours"
    assert deadline_text(tok, {"NoticePeriod": "soon"}) is None


# ── Engine ───────────────────────────────────────────────────────────────

def test_token_instance_carries_the_resolved_text():
    model = _model()
    assert token_from_spec(model, "notice", "Supplier", 0).deadline == "24 hours"
    rt = _quiet(Runtime.build_from_spec, model)
    assert [t.deadline for t in rt.current_state().tokens if t.token_name == "notice"] == ["24 hours"]


@pytest.mark.parametrize("deadline, note", [
    ("NoticePeriod", " (policy NoticePeriod = 24 hours)"),
    ('"24 hours"', ""),
])
def test_violated_at_the_policy_duration(deadline, note):
    rt = _runtime(deadline=deadline)
    rt.advance_clock(1439)
    assert rt.check_live_violations().violations == ()
    rt.advance_clock(1)
    record = rt.check_live_violations()
    assert record.violations == ("notice",)
    assert record.effects == (
        f"violated 'notice' held by 'Supplier' (elapsed 1440 >= deadline 1440 steps){note}",)


def test_unusable_policy_is_no_deadline():
    rt = _runtime(ptype="date", value="2027-06-30")
    rt.advance_clock(100000)
    assert rt.check_live_violations().violations == ()


def test_declare_violation_reads_the_policy():
    rt = _runtime(mode="discharge_mode: strict")
    early = rt.declare_violation("notice", "Watchdog", at_tick=1439)
    assert early.outcome == "blocked"
    assert early.reason == "'notice' is not overdue: 1439 of 1440 steps elapsed at step 1439"
    record = rt.declare_violation("notice", "Watchdog", at_tick=1440)
    assert record.outcome == "violation"
    assert record.effects == (
        "declared 'notice' held by 'Supplier' violated (elapsed 1440 >= deadline 1440 steps "
        "at step 1440) (policy NoticePeriod = 24 hours)",)


# ── Verifier (2.2.0-8) ───────────────────────────────────────────────────

from el_kripke import _build_enforceable_deadlines, build_kripke_from_runtime, build_kripke_model  # noqa: E402

_HORIZON = 10


def _summary(km, burdens=("notice",)):
    verdicts = {}
    for name in burdens:
        af, ef = km.check_obligation(name), km.check_permission(name)
        verdicts[name] = (af.satisfied, af.status, ef.satisfied)
    return km.worlds, km.edges, km.labels, verdicts


def _static(deadline, value="5 minutes"):
    return _quiet(build_kripke_model, _model(deadline=deadline, value=value), horizon=_HORIZON)


def _hybrid(deadline, value="5 minutes"):
    return _quiet(build_kripke_from_runtime, _runtime(deadline=deadline, value=value),
                  horizon=_HORIZON)


def test_enforceable_in_both_builders():
    assert "notice" in _build_enforceable_deadlines(_model())
    assert "notice" not in _build_enforceable_deadlines(_model(ptype="date", value="2027-06-30"))


@pytest.mark.parametrize("build", [_static, _hybrid], ids=["static", "hybrid"])
def test_model_identical_to_the_literal(build):
    policy, literal = build("NoticePeriod"), build('"5 minutes"')
    assert _summary(policy) == _summary(literal)
    # Not vacuous: within the horizon the deadline adds a violation path.
    assert any(label.startswith("violate:notice") for label in policy.labels.values())
    assert _summary(policy) != _summary(build('"referral episode"'))


def test_hybrid_reads_the_declared_value_not_policy_values():
    """R10: the verifier never reads WorldState.policy_values, even for a
    deadline; a changed runtime copy does not change the model."""
    import dataclasses
    runtime = _runtime(value="5 minutes")
    before = _summary(_quiet(build_kripke_from_runtime, runtime, horizon=_HORIZON))
    runtime._state = dataclasses.replace(runtime.current_state(),
                                         policy_values=(("NoticePeriod", "1 minute"),))
    after = _summary(_quiet(build_kripke_from_runtime, runtime, horizon=_HORIZON))
    assert before == after
