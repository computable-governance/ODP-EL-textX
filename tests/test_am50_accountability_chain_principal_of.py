"""
AM-50: bridge one-sided principal_of standing affiliation into the
delegation-chain walk (el_reasoner.ultimate_accountability /
el_kripke._delegation_chain_for_token).

Closes Problem 3 of the paused "Delegation holder/chain resolution"
finding (docs/CONCEPTS_INDEX.md, 2026-08-19): walk_chain()/
_delegation_chain_for_token() only ever followed Delegation elements,
never principal_of — so referral_scenario.el's GPPractice { principal_of
GPClinician } link (deliberately one-sided, no reciprocal delegated_from
— see that file's own header comment, lines 41-84) was structurally
invisible, and ultimate_accountability("...referralResponseBurden...")
stopped dead at GPPractice despite gpToSpecialistDelegation existing one
hop further down (GPClinician -> SpecialistClinician).

Standard grounding: §7.10.1 ("the parties (collectively) become
principal of that object") and §6.6.8 NOTE 3 (paired principal_of +
delegated_from as the standard's own signal for genuine delegated
agency) — see el_reasoner._is_standing_affiliation()'s docstring for the
full discriminator rationale: only ONE-SIDED principal_of (no reciprocal
delegated_from) is added as a new, unconditionally-matching edge; PAIRED
principal_of+delegated_from is deliberately not duplicated, since it's
already a genuine Delegation with its own obligation-scoped text.

Real-scenario tests parse scenarios/referral/referral_scenario.el
directly (not a probe fixture) — this bug and its fix are both about
that file's specific, documented accountability shape.
"""
from el_kripke import _delegation_chain_for_token
from el_parser import parse, parse_string
from el_reasoner import delegation_graph, ultimate_accountability


def _referral_model():
    result = parse("scenarios/referral/referral_scenario.el", validate=False)
    assert result.ok, result.errors
    return result.model


def test_referral_response_burden_chain_reaches_specialist_clinician():
    model = _referral_model()
    chains = ultimate_accountability(
        model,
        "Respond to the specialist referral within the agreed timeframe and schedule assessment",
    )
    assert len(chains) == 1
    chain = chains[0]

    assert chain.root_party == "GPPractice"          # unchanged — see test below
    assert chain.current_holder == "SpecialistClinician"

    hops = [(link.from_obj, link.to_obj) for link in chain.chain]
    assert hops == [("GPPractice", "GPClinician"), ("GPClinician", "SpecialistClinician")]


def test_referral_initiation_burden_holder_corrected_to_gpclinician():
    """Previously reported holder: GPPractice — already wrong against the
    live runtime, where _build_referral_runtime() (el_api.py) grants
    referralInitiationBurden directly to GPClinician (referring_practitioner
    defaults to "GPClinician", not "GPPractice"). This fix happens to
    correct that pre-existing inaccuracy too, since the bridge to
    GPClinician is now walkable for any obligation, not just
    referralResponseBurden's."""
    model = _referral_model()
    chains = ultimate_accountability(
        model,
        "Initiate specialist referral and provide clinical handover for the patient",
    )
    assert len(chains) == 1
    chain = chains[0]

    assert chain.root_party == "GPPractice"           # root commitment unchanged
    assert chain.current_holder == "GPClinician"       # corrected: was "GPPractice"
    assert [(link.from_obj, link.to_obj) for link in chain.chain] == [("GPPractice", "GPClinician")]


def test_clinical_handover_burden_does_not_over_extend_to_specialist():
    """Discriminator-safety test: clinicalHandoverBurden is held by
    GPClinician alone (never delegated further — no Delegation transfers
    it). If the fix added principal_of edges unconditionally (including
    the PAIRED GPClinician -> SpecialistClinician relationship, which is
    already a genuine Delegation for a DIFFERENT obligation), this chain
    would incorrectly extend to SpecialistClinician too. It must not."""
    model = _referral_model()
    chains = ultimate_accountability(
        model,
        "Provide complete clinical handover documentation to specialist",
    )
    assert len(chains) == 1
    chain = chains[0]

    assert chain.root_party == "GPPractice"
    assert chain.current_holder == "GPClinician"
    assert chain.current_holder != "SpecialistClinician"


def test_delegation_chain_for_token_mirrors_reasoner_for_referral_response():
    """Layer 4 hybrid mode (el_kripke) must agree with Layer 2 (el_reasoner)
    on the same scenario — the whole point of fixing both files together."""
    model = _referral_model()
    chain = _delegation_chain_for_token(model, "referralResponseBurden", "SpecialistClinician")
    assert chain == ["GPPractice", "GPClinician", "SpecialistClinician"]


_NO_PRINCIPAL_OF_PROBE = """
enterprise specification NoPrincipalOfProbe

party Alice {
    holds someBurden
}

party Bob {
}

burden someBurden {
    state: active
    deadline: "1 hour"
    discharge_mode: eventual
}

commitment aliceCommitment {
    by: Alice
    obligation: "Do the thing"
    creates_burden: someBurden
}

delegation aliceToBob {
    from: Alice
    to: Bob
    obligation: "Do the thing"
    transfers_burden: someBurden
}
"""


def test_no_principal_of_is_a_pure_regression_guard():
    """No party in this probe declares principal_of/delegated_from at all —
    delegation_graph()'s new second pass must contribute nothing, and
    both functions' output must be identical to their pre-AM-50 behaviour."""
    result = parse_string(_NO_PRINCIPAL_OF_PROBE, validate=True)
    assert result.ok, result.errors
    model = result.model

    graph = delegation_graph(model)
    all_links = [link for links in graph.values() for link in links]
    assert len(all_links) == 1
    assert all_links[0].structural is False

    chains = ultimate_accountability(model, "Do the thing")
    assert len(chains) == 1
    assert chains[0].root_party == "Alice"
    assert chains[0].current_holder == "Bob"

    assert _delegation_chain_for_token(model, "someBurden", "Bob") == ["Alice", "Bob"]
