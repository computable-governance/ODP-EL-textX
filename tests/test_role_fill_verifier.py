"""
Layer 4 — 2.4.0-3: the verifier does not model `effect fill` (parity R27).

The static builder takes performers from the specification's `fills`
statements only, so a fill effect changes no world or edge and the filler
never performs the role's actions there. The hybrid builder reads
state.actors once, at its anchor: a fill made before the build is seen, one
made after it is not.
"""
import contextlib
import io

from el_engine import grant_token, token_from_spec
from el_kripke import build_kripke_from_runtime, build_kripke_model
from el_parser import parse_string
from el_runtime import Runtime

_FILL = "            effect fill contractorRole with SupplierA"


def _src(award_body):
    return f"""
enterprise specification RoleFillVerifier

burden workBurden {{ for_action: "perform" state: active deadline: "2 days" }}

party Buyer
party SupplierA

commitment workCommitment {{ by: SupplierA obligation: "do the work" creates_burden: workBurden }}

community C {{
    objective: "probe"
    Buyer fills buyerRole
    role buyerRole {{
        action award {{
            actor: buyerRole
{award_body}
        }}
    }}
    role contractorRole {{
        action perform {{
            actor: contractorRole
        }}
    }}
}}
"""


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)


def _spec(award_body=_FILL):
    result = _quiet(parse_string, _src(award_body), validate=False)
    assert result.ok, result.errors
    return result.model


def _performed_by_filler(km):
    return [label for label in km.labels.values()
            if label.startswith("discharge:") and label.endswith(" by SupplierA")]


def _runtime(spec):
    rt = Runtime.build_from_spec(spec)
    rt._state = grant_token(rt.current_state(), token_from_spec(spec, "workBurden", "SupplierA", 0))
    return rt


def test_static_build_is_unchanged_by_the_fill_and_the_filler_never_performs():
    with_fill = _quiet(build_kripke_model, _spec(), horizon=10)
    without = _quiet(build_kripke_model, _spec(""), horizon=10)
    assert len(with_fill.worlds) == len(without.worlds)
    assert sum(len(v) for v in with_fill.edges.values()) == \
        sum(len(v) for v in without.edges.values())
    assert sorted(with_fill.labels.values()) == sorted(without.labels.values())
    assert _performed_by_filler(with_fill) == []


def test_hybrid_built_after_the_fill_sees_the_filler_in_the_role():
    spec = _spec()
    rt = _runtime(spec)
    assert rt.advance("award", "Buyer").outcome == "ok"
    km = _quiet(build_kripke_from_runtime, rt, horizon=10)
    assert _performed_by_filler(km) != []


def test_hybrid_built_before_the_fill_does_not():
    spec = _spec()
    rt = _runtime(spec)
    km = _quiet(build_kripke_from_runtime, rt, horizon=10)
    assert _performed_by_filler(km) == []
