"""
2.1.0-5 — policy values do not change the Kripke model.

WorldState.policy_values (2.1.0-3) is seeded read-only and the verifier
does not read it (docs/ENGINE_VERIFIER_PARITY.md, row R10). For each API
scenario that has policy values, the hybrid model built from the runtime as built (with its
policy values) must equal the model built after the values are removed:
the same worlds, the same edge labels and the same AF/EF verdict for every
burden. Relative, so no absolute world count is pinned.

Layer 4 (verifier) tests per tests/README.md's strategy.
"""
import contextlib
import dataclasses
import io

import pytest

import el_api
from el_kripke import build_kripke_from_runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


# The models are large at the API horizon (10); the property does not depend
# on the horizon, so a shorter one keeps the test fast.
_HORIZON = 5


def _summary(runtime, k):
    km = _quiet(build_kripke_from_runtime, runtime, horizon=_HORIZON, deadline_scale=k)
    burdens = sorted({t.token_name for t in runtime.current_state().tokens
                      if t.kind == "burden"})
    verdicts = {}
    for name in burdens:
        af, ef = km.check_obligation(name), km.check_permission(name)
        verdicts[name] = (af.satisfied, af.status, ef.satisfied)
    labels = sorted(set(km.labels.values()))
    return len(km.worlds), labels, verdicts


def _seeded():
    return {name: _quiet(build).current_state().policy_values
            for name, build in el_api._SCENARIO_BUILDERS.items()}


# Only scenarios with policy values: for the others removing the values
# changes nothing, so the comparison would prove nothing.
_SEEDED_SCENARIOS = sorted(name for name, values in _seeded().items() if values)


@pytest.mark.parametrize("name", _SEEDED_SCENARIOS)
def test_policy_values_do_not_change_the_model(name):
    runtime = _quiet(el_api._SCENARIO_BUILDERS[name])
    assert runtime.current_state().policy_values
    k = el_api._SCENARIO_DEADLINE_SCALE.get(name, 1)
    with_values = _summary(runtime, k)

    runtime._state = dataclasses.replace(runtime.current_state(), policy_values=())
    without_values = _summary(runtime, k)

    assert with_values == without_values


def test_some_scenario_really_has_policy_values():
    # Guards against the test above passing vacuously.
    seeded = _seeded()
    assert _SEEDED_SCENARIOS, seeded
    assert seeded["public_data_portal"] and seeded["external_agent_access"]
