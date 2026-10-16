"""
2.1.0-3 — read-only policy value seeding into WorldState.

WorldState.policy_values holds (policy name, value text) for each
top-level Policy, sorted by name, seeded from initial_value by
initial_state(spec), Runtime.build_from_spec and build_from_federation.
There is no setter, and nothing in the engine or verifier reads it yet.

The main risk is a state change that rebuilds WorldState field by field
and silently drops the values; the builders now use dataclasses.replace,
and these tests check the values survive every kind of state change.

Layer 3 (runtime) tests per tests/README.md's strategy.
"""
import contextlib
import dataclasses
import io
import re
from pathlib import Path

import pytest

from el_engine import (
    WorldState, enroll, grant_token, initial_state, policy_value_kind,
    policy_value_text, token_from_spec,
)
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


_PROBE = """
enterprise specification SeedingProbe
agent Worker
party Owner

policy Zeta : decimal { initial_value: 0.0000001 }
policy Fee : amount { initial_value: 250.00 AUD }
policy Rate : percentage { initial_value: 4.50% }
policy Window : duration { initial_value: 60 days }
policy Opens : instant { initial_value: 2026-11-30T17:00+10:00 }

normative_policy Schedule {
    source: "Schedule of fees"
    kind: contractual
    type: integer
    initial_value: 5
}

permit joinPermit {
    for_action: "work"
    state: active
}

embargo laterEmbargo {
    for_action: "work"
    state: pending
    triggered_by: stop
}

burden quickBurden {
    for_action: "work"
    state: active
    deadline: "1 minute"
    discharge_mode: eventual
}

community C {
    objective: "probe"
    event stop
    on_join workerRole transfer joinPermit
    on_join workerRole transfer laterEmbargo
    Worker fills workerRole
    Owner fills ownerRole
    role workerRole { action work { actor: workerRole } }
    role ownerRole { action stopWork { actor: ownerRole emits: stop } }
}
"""

_EXPECTED = (
    ("Fee", "250.00 AUD"),
    ("Opens", "2026-11-30T17:00+10:00"),
    ("Rate", "4.50%"),
    ("Window", "60 days"),
    ("Zeta", "0.0000001"),
)


def _spec():
    result = _quiet(parse_string, _PROBE, validate=False)
    assert result.ok, result.errors
    return result.model


# ── Seeding ──────────────────────────────────────────────────────────────

def test_initial_state_without_spec_has_no_values():
    assert initial_state().policy_values == ()


def test_initial_state_with_spec_seeds_sorted_by_name():
    assert initial_state(_spec()).policy_values == _EXPECTED


def test_build_from_spec_seeds():
    rt = _quiet(Runtime.build_from_spec, _spec())
    assert rt.current_state().policy_values == _EXPECTED


def test_build_from_federation_seeds():
    rt = _quiet(Runtime.build_from_federation, _spec())
    assert rt.current_state().policy_values == _EXPECTED


def test_normative_policy_not_seeded():
    state = initial_state(_spec())
    assert state.policy_value("Schedule") is None


def test_policy_value_lookup():
    state = initial_state(_spec())
    assert state.policy_value("Fee") == "250.00 AUD"
    assert state.policy_value("Missing") is None


# ── Read-only ────────────────────────────────────────────────────────────

def test_no_setter():
    assert not [n for n in dir(WorldState) if 'policy' in n and n.startswith(('with_', 'set'))]
    state = initial_state(_spec())
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.policy_values = ()


# ── Values survive every state change ────────────────────────────────────

def test_values_survive_state_builders():
    spec = _spec()
    state = initial_state(spec)
    state = state.with_tick(3)
    assert state.policy_values == _EXPECTED
    state = state.with_tokens(())
    assert state.policy_values == _EXPECTED
    state = state.with_responded({("r", "t", "h", 0)})
    assert state.policy_values == _EXPECTED
    state = enroll(state, "Worker", role_name="workerRole")
    assert state.policy_values == _EXPECTED
    state = grant_token(state, token_from_spec(spec, "quickBurden", "Worker", state.tick))
    assert state.policy_values == _EXPECTED


def test_values_survive_runtime_operations():
    spec = _spec()
    rt = _quiet(Runtime.build_from_spec, spec)
    rt._state = grant_token(rt.current_state(),
                            token_from_spec(spec, "quickBurden", "Worker", 0))

    def check():
        assert rt.current_state().policy_values == _EXPECTED

    _quiet(rt.advance, "stopWork", "Owner");   check()   # fires an event
    assert _quiet(rt.advance_clock, 5).outcome == "ok"; check()
    record = _quiet(rt.check_live_violations)
    assert record.violations == ("quickBurden",); check()
    _quiet(rt.fire_violation_responses);       check()
    _quiet(rt.advance, "work", "Worker");      check()   # blocked by the embargo
    # The steps really changed the state: the event activated the embargo,
    # the clock ran and the burden was violated.
    states = {t.token_name: t.state for t in rt.current_state().tokens}
    assert states["laterEmbargo"] == "active"
    assert states["quickBurden"] == "violated"
    assert rt.current_state().tick >= 5


def test_only_initial_state_builds_a_worldstate_from_fields():
    # A rebuild by keyword would drop policy_values; every other state change
    # goes through dataclasses.replace.
    src = (Path(__file__).resolve().parent.parent / 'toolchain' / 'el_engine.py').read_text()
    calls = re.findall(r'\bWorldState\(', src)
    assert len(calls) == 1
    assert 'return WorldState(tokens=(), actors=(), tick=0, policy_values=policy_values)' in src


# ── Plain text ───────────────────────────────────────────────────────────

def _value(text, policy_type='Any'):
    src = (f'enterprise specification P\n'
           f'policy Q : {policy_type} {{ initial_value: {text} }}\n')
    result = parse_string(src, validate=False)
    assert result.ok, result.errors
    return result.model.elements[0].initial_value


@pytest.mark.parametrize('text, expected', [
    ('5', '5'), ('-5', '-5'), ('-0', '0'),
    ('4.50', '4.50'),                              # scale kept as written
    ('-0.5', '-0.5'), ('-0.0', '-0.0'),
    ('0.0000001', '0.0000001'),                    # never 1E-7
    ('10000000000000000.5', '10000000000000000.5'),
    ('100000000000000000000', '100000000000000000000'),
    ('6%', '6%'), ('4.25%', '4.25%'), ('0.0000001%', '0.0000001%'),
    ('250.00 AUD', '250.00 AUD'), ('0.0000001 aud', '0.0000001 aud'),
    ('2026-11-30', '2026-11-30'),
    ('2026-11-30T17:00+10:00', '2026-11-30T17:00+10:00'),  # offset kept
    ('5 days', '5 days'), ('1 hour', '1 hour'),
    ('7..10', '7..10'),
    ('true', 'true'), ('false', 'false'),
    ('"hello world"', 'hello world'),
    ('someOption', 'someOption'),
])
def test_policy_value_text(text, expected):
    out = policy_value_text(_value(text))
    assert out == expected
    assert 'E' not in out.replace('AUD', '')


@pytest.mark.parametrize('text, kind', [
    ('5', 'integer'), ('4.5', 'decimal'), ('4.5%', 'percentage'),
    ('250.00 AUD', 'amount'), ('2026-11-30', 'date'),
    ('2026-11-30T17:00Z', 'instant'), ('5 days', 'duration'),
    ('7..10', 'interval'), ('true', 'boolean'), ('"x"', 'name'), ('x', 'name'),
])
def test_policy_value_kind(text, kind):
    assert policy_value_kind(_value(text)) == kind


# ── API-built runtimes (2.1.0-4) ─────────────────────────────────────────

@pytest.mark.parametrize('name, identity_policy, identity_text', [
    ('public_data_portal', 'AgentIdentityPolicy',
     'signed requests or mTLS with an agency-registered agent key'),
    ('external_agent_access', 'WorkloadIdentityPolicy',
     'mTLS with provider-issued client certificate'),
])
def test_api_terms_of_engagement_runtime_carries_policy_values(
        name, identity_policy, identity_text):
    import el_api
    state = _quiet(el_api._SCENARIO_BUILDERS[name]).current_state()
    names = [n for n, _ in state.policy_values]
    assert names == sorted(names) and len(names) == 5
    assert state.policy_value("RefusalQuarantinePolicy") == "24 hours"
    assert state.policy_value("RefusalReviewPolicy") == "1 day"
    assert state.policy_value(identity_policy) == identity_text
