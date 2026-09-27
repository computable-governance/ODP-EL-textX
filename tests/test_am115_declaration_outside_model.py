"""
AM-115 — a declaration stays outside the model and outside available-actions.

A declaration (declares_violation_of) is made through
el_engine.declare_violation(), never advance(). So:
  - neither Kripke builder's T5 exercises a declaration permit (without the
    skip, both would add an "exercise:declP → declRec" edge once the
    strict freeze lifts);
  - AF(discharged) for the strict burden is unchanged by the declaration
    machinery, in both builders;
  - GET available-actions omits the declaration permit (execute-action would
    refuse it).
"""
import contextlib
import io

import pytest

import el_api
from el_kripke import build_kripke_from_runtime, build_kripke_model

from test_am115_declare_violation import _runtime, _spec


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _exercised(km):
    return {label.split(" → ", 1)[0] for label in km.labels.values()
            if label.startswith("exercise:")}


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_t5_never_exercises_a_declaration(builder):
    if builder == "static":
        km = _quiet(build_kripke_model, _spec(), horizon=10)
    else:
        km = _quiet(build_kripke_from_runtime, _runtime(), horizon=10)
    exercised = _exercised(km)
    assert "exercise:useP" in exercised          # ordinary permits still exercised
    assert "exercise:declP" not in exercised


@pytest.mark.parametrize("builder", ["static", "hybrid"])
def test_strict_burden_af_holds(builder):
    if builder == "static":
        km = _quiet(build_kripke_model, _spec(), horizon=10)
    else:
        km = _quiet(build_kripke_from_runtime, _runtime(), horizon=10)
    assert km.check_obligation("recB").satisfied


def test_available_actions_omits_the_declaration_permit(monkeypatch):
    rt = _runtime()
    rt.advance("rec", "Gate")                     # end the freeze
    monkeypatch.setattr(el_api, "_runtime", rt)
    assert [a.action for a in el_api.get_available_actions("Dog").available_actions] == []
    assert [a.action for a in el_api.get_available_actions("Ag").available_actions] == ["use"]
