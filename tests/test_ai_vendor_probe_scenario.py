"""
AM-59: scenario-level confirmation for ai_vendor_probe.el, the first named
scenario exercising AM-40's role-based Domain syntax (controlling_role/
controlled_role/DomainRoleFiller with via=[Federation]) and demonstrating
the AIVendor two-construct shape (peer contract federations for the
pre-deployment provider duty, one shared subordination domain for the
in-use processor duty) identified as a gap 2026-07-09
(docs/CONCEPTS_INDEX.md).

Deliberately structural only -- no burdens, commitments, or Kripke
verification. The AIVendor gap is about provenance and role correctness,
not discharge semantics, so this file checks parse/validate cleanliness
and that each deployed agent's `via` resolves to the correct, distinct
Federation -- the actual N-peer provenance claim -- against the real
parsed model, not just a parse-success check.
"""
from el_parser import parse


def _spec():
    result = parse("scenarios/vendor/ai_vendor_probe.el", validate=True)
    assert result.ok, result.errors
    return result.model


def _find(model, cls_name, name=None):
    matches = [e for e in model.elements if type(e).__name__ == cls_name]
    if name is None:
        return matches
    return next(e for e in matches if e.name == name)


def test_ai_vendor_probe_scenario_parses_and_validates_cleanly():
    """Zero errors -- confirms V-NEW-21 passes using only the new
    role-based syntax (no controlling_object/controlled_object)."""
    result = parse("scenarios/vendor/ai_vendor_probe.el", validate=True)
    assert result.ok, result.errors


def test_deployed_agents_via_resolves_to_distinct_originating_federations():
    """Each DomainRoleFiller's `via` traces back to the correct vendor
    federation, by identity -- the actual N-peer provenance claim."""
    spec = _spec()
    domain = _find(spec, "Domain", "AIVendorGovernanceDomain")
    alpha_fed = _find(spec, "Federation", "AIVendorAlphaSupplyFederation")
    beta_fed = _find(spec, "Federation", "AIVendorBetaSupplyFederation")

    fillers_by_obj = {rf.obj.name: rf for rf in domain.role_fillers}

    assert fillers_by_obj["DiagnosticImagingAIAgent"].via is alpha_fed
    assert fillers_by_obj["TriageAIAgent"].via is beta_fed
    assert fillers_by_obj["DiagnosticImagingAIAgent"].via is not beta_fed
    assert fillers_by_obj["TriageAIAgent"].via is not alpha_fed


def test_controlling_filler_has_no_via():
    """GPPractice fills the controlling role directly -- it is not routed
    through any vendor federation, so `via` must be None."""
    spec = _spec()
    domain = _find(spec, "Domain", "AIVendorGovernanceDomain")

    fillers_by_obj = {rf.obj.name: rf for rf in domain.role_fillers}
    assert fillers_by_obj["GPPractice"].via is None
