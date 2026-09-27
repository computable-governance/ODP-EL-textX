"""
AM-114 part 5 — an action may be performed only by an actor that fills a
role declaring it (§7.8.2).

Engine: advance() Step 2 refuses an actor that fills none of the roles
declaring the action (an actor enrolled without a role fills none); an
undeclared action has no role to check. claim() and decline() go through
advance(), so the rule applies to them. Verifier: both builders restrict
each action's performers to role fillers, from a fixed actor -> roles map
(hybrid: state.actors; static: the spec's `fills` statements, unrestricted
for a spec with none — transitional).
"""
import contextlib
import io

import pytest

import el_api
from el_engine import enroll, grant_token, initial_state, token_from_spec
from el_kripke import build_kripke_from_runtime, build_kripke_model
from el_parser import parse_string
from el_runtime import Runtime


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


# ── Terms of engagement: engine ──────────────────────────────────────────────

_TOE = {
    "public_data_portal": dict(agent="ExternalAIAgent", principal="AgentOperator",
                               gateway="AgencyGateway", contact="AgencySecurityContact",
                               request="readPublishedDataset"),
    "external_agent_access": dict(agent="VendorReferralAgent", principal="VendorOrg",
                                  gateway="ProviderAPIGateway", contact="ProviderSecurityContact",
                                  request="submitServiceRequest"),
}


def _run(name, steps):
    rt = el_api._SCENARIO_BUILDERS[name]()
    return [rt.advance(action, actor) for actor, action in steps]


def _refused(rec, actor, role, action):
    return (rec.outcome == "blocked"
            and rec.reason == f"actor '{actor}' does not fill role '{role}', "
                              f"which declares action '{action}'")


@pytest.mark.parametrize("name", sorted(_TOE))
def test_agent_cannot_record_its_own_refusal(name):
    c = _TOE[name]
    *_, rec = _run(name, [(c["gateway"], "refuseRequest"), (c["agent"], "recordRefusal")])
    assert _refused(rec, c["agent"], "accessGatewayRole", "recordRefusal")


@pytest.mark.parametrize("name", sorted(_TOE))
def test_agent_cannot_review_its_own_refusal(name):
    c = _TOE[name]
    *_, rec = _run(name, [(c["gateway"], "refuseRequest"), (c["gateway"], "recordRefusal"),
                          (c["agent"], "reviewRefusal")])
    assert _refused(rec, c["agent"], "incidentContactRole", "reviewRefusal")


@pytest.mark.parametrize("name", sorted(_TOE))
@pytest.mark.parametrize("who", ["agent", "principal"])
def test_only_the_contact_acknowledges_an_incident(name, who):
    c = _TOE[name]
    *_, rec = _run(name, [(c["principal"], "detectIncident"), (c["principal"], "notifyIncident"),
                          (c[who], "acknowledgeIncident")])
    assert _refused(rec, c[who], "incidentContactRole", "acknowledgeIncident")
    assert rec.discharged == ()


@pytest.mark.parametrize("name", sorted(_TOE))
def test_legitimate_refusal_flow(name):
    c = _TOE[name]
    recs = _run(name, [(c["agent"], c["request"]), (c["gateway"], "refuseRequest"),
                       (c["gateway"], "recordRefusal"), (c["contact"], "reviewRefusal"),
                       (c["agent"], "retryByOtherRoute")])
    assert [r.outcome for r in recs] == ["ok", "ok", "ok", "ok", "blocked"]
    assert recs[2].discharged == ("refusalRecordBurden",)
    assert recs[3].discharged == ("refusalReviewBurden",)
    assert recs[4].reason == "active embargo 'noCircumventionEmbargo' blocks action"


@pytest.mark.parametrize("name", sorted(_TOE))
def test_legitimate_incident_flow(name):
    c = _TOE[name]
    recs = _run(name, [(c["principal"], "detectIncident"), (c["principal"], "notifyIncident"),
                       (c["contact"], "acknowledgeIncident")])
    assert [r.outcome for r in recs] == ["ok", "ok", "ok"]
    assert recs[2].discharged == ("incidentNotificationBurden",)


# ── Terms of engagement: verifier ────────────────────────────────────────────

def _labels(km):
    return set(km.labels.values())


@pytest.mark.parametrize("name", sorted(_TOE))
def test_hybrid_acknowledgement_needs_a_contact(name):
    """With the contact enrolled without its role, nobody may perform
    acknowledgeIncident: the engine refuses it and the hybrid model has no
    acknowledgement edge."""
    c = _TOE[name]
    rt = el_api._SCENARIO_BUILDERS[name]()
    assert any("via acknowledgeIncident" in l for l in _labels(_quiet(build_kripke_from_runtime, rt, 10)))

    state = rt.current_state()
    stripped = [a for a in state.actors if a.role_name != "incidentContactRole"]
    state = type(state)(tokens=state.tokens, actors=tuple(stripped), tick=state.tick)
    state = enroll(state, c["contact"])
    rt_without = Runtime(state, rt._spec)
    km = _quiet(build_kripke_from_runtime, rt_without, 10)
    assert not any("via acknowledgeIncident" in l for l in _labels(km))
    rt_without.advance("detectIncident", c["principal"])
    rt_without.advance("notifyIncident", c["principal"])
    assert rt_without.advance("acknowledgeIncident", c["contact"]).outcome == "blocked"


# ── Probe: static builder reads `fills`; claim/decline; undeclared actions ──

_PROBE = """
enterprise specification RoleRuleProbe
agent Doer
agent Bystander

burden doBurden { for_action: "doIt" state: active discharge_mode: eventual }
burden pingBurden { for_action: "ping" state: pending triggered_by: poked discharge_mode: eventual }
burden claimBurden { for_action: "claimIt" state: claimable discharge_mode: eventual }

commitment DoerDoes { by: Doer obligation: "do it" creates_burden: doBurden }
commitment DoerPings { by: Doer obligation: "ping" creates_burden: pingBurden }

community C {
    objective: "probe the role rule"
    event poked
    FILLS
    role doerRole {
        action doIt { actor: doerRole }
        action ping { actor: doerRole }
        action claimIt { actor: doerRole }
    }
    role pokerRole {
        action poke { actor: pokerRole emits: poked }
    }
}
"""


def _probe(fills):
    return parse_string(_PROBE.replace("FILLS", fills), validate=False).model


def test_static_builder_restricts_performers_to_fillers():
    unfilled = _quiet(build_kripke_model, _probe("Doer fills doerRole"), horizon=3)
    assert "discharge:doBurden by Doer" in _labels(unfilled)
    assert not any("via poke" in l for l in _labels(unfilled))  # nobody fills pokerRole

    filled = _quiet(build_kripke_model, _probe("Doer fills doerRole\n    Bystander fills pokerRole"),
                    horizon=3)
    assert any("via poke" in l for l in _labels(filled))

    no_holder_role = _quiet(build_kripke_model, _probe("Bystander fills pokerRole"), horizon=3)
    assert "discharge:doBurden by Doer" not in _labels(no_holder_role)


def test_static_builder_without_fills_stays_unrestricted():
    km = _quiet(build_kripke_model, _probe(""), horizon=3)
    assert "discharge:doBurden by Doer" in _labels(km)
    assert any("via poke" in l for l in _labels(km))


def _claim_runtime(role):
    spec = _probe("")
    state = enroll(initial_state(), "Doer", role_name=role)
    state = grant_token(state, token_from_spec(spec, "claimBurden", "Doer", 0))
    return Runtime(state, spec)


@pytest.mark.parametrize("call", ["claim", "decline"])
def test_claim_and_decline_need_the_role(call):
    rec = getattr(_claim_runtime(None), call)("claimBurden", "Doer")
    assert _refused(rec, "Doer", "doerRole", "claimIt")
    assert getattr(_claim_runtime("doerRole"), call)("claimBurden", "Doer").outcome == "ok"


def test_undeclared_action_is_unrestricted():
    spec = _probe("")
    state = enroll(initial_state(), "Bystander")
    state = enroll(state, "Doer")
    rt = Runtime(state, spec)
    assert rt.advance("somethingUndeclared", "Bystander").outcome == "ok"
    assert _refused(rt.advance("doIt", "Doer"), "Doer", "doerRole", "doIt")
