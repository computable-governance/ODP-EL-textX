"""
Holds-clause emission fix verification (fhir_mapper.py, R05-R08 path).

Fixes the gap documented in docs/CONCEPTS_INDEX.md's "Mapper-generated
burdens are declared but never granted (no live TokenInstance)"
(2026-08-30), scoped to the R05-R08 ServiceRequest -> Commitment + Burden
path specifically. Before this fix, _render_object never emitted a
`holds` clause for any burden, so Runtime.build_from_spec() (which grants
tokens exclusively by reading EnterpriseObject.holds_tokens — confirmed
by reading el_runtime.py's build_from_spec() directly) produced zero live
TokenInstances for any mapper-generated burden, no matter how the spec
was constructed.

The fix reuses exactly the accountable party _map_service_request already
resolves for commitment.by (via _resolve_commitment_accountable_party,
fixed in AM-71) as the burden's holder — but only when that el_id
actually names a declared ELObject (spec.objects is fully populated by
demographics mapping before ServiceRequest mapping runs, so this check is
made at map time). When it doesn't (AM-71's tier 0c: a dangling
PractitionerRole reference, or similar), the burden stays ungranted —
never fabricate a holder the bundle doesn't support — but the gap is
made visible via an [R06] tag on the burden's own description, not
silently dropped.

Reuses tests/fixtures/practitioner_role_requester_bundle.json (built for
AM-71, still fully current) rather than inventing a new fixture — it
already has exactly the three cases this fix needs: ServiceRequest/554
(requester resolves cleanly to a declared Organization — tier 0a),
ServiceRequest/555 (requester resolves via the practitioner fallback —
tier 0b, still a declared object), and ServiceRequest/560 (requester is a
dangling PractitionerRole reference — tier 0c, no declared object at
all).
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "practitioner_role_requester_bundle.json"

sys.path.insert(0, str(TOOLCHAIN))

from fhir_mapper import FHIRConsentMapper  # noqa: E402


def _load_bundle() -> dict:
    return json.loads(FIXTURE.read_text())


def _generate(bundle: dict) -> str:
    mapper = FHIRConsentMapper()
    return mapper.map_bundle(bundle)


def _drop_service_request(bundle: dict, sr_id: str) -> dict:
    """Filter out one ServiceRequest (and nothing else) — used to isolate
    the tier-0c dangling case, which is independently known (AM-71) to
    fail validation for its own commitment.by, from the regression check
    this file's core test performs."""
    kept = [
        e for e in bundle["entry"]
        if not (e["resource"]["resourceType"] == "ServiceRequest" and e["resource"]["id"] == sr_id)
    ]
    return {**bundle, "entry": kept}


def test_resolved_holder_gets_a_holds_clause():
    """[Tier 0a] ServiceRequest/554's requester resolves cleanly to
    BrisbaneEndocrinology — its burden gets `holds Id554Obligation` inside
    that object's body."""
    el = _generate(_load_bundle())
    assert "party BrisbaneEndocrinology" in el
    block = el.split("party BrisbaneEndocrinology")[1].split("party RobertsFred")[0]
    assert "holds Id554Obligation" in block


def test_fallback_resolved_holder_also_gets_a_holds_clause():
    """[Tier 0b] ServiceRequest/555's requester resolves via the
    practitioner fallback (AM-71) to OconnorLiam — still a declared
    object, so it also gets `holds Id555Obligation`, despite carrying an
    [R06] warning in its commitment's description."""
    el = _generate(_load_bundle())
    assert "party OconnorLiam" in el
    block = el.split("party OconnorLiam")[1].split("// ── Deontic Tokens")[0]
    assert "holds Id555Obligation" in block


def test_unresolved_holder_gets_no_holds_clause_but_is_tagged():
    """[Tier 0c] ServiceRequest/560's requester is a dangling
    PractitionerRole reference — DanglingNotInBundle is never declared as
    an object at all, so no `holds Id560Obligation` appears anywhere.
    The gap is visible via an [R06] tag on the burden's own description,
    not silently dropped."""
    el = _generate(_load_bundle())
    assert "holds Id560Obligation" not in el
    assert "burden Id560Obligation {" in el
    block = el.split("burden Id560Obligation {")[1].split("}")[0]
    assert "[R06] UNRESOLVED holder" in block
    assert "not granted to any declared object" in block


def test_holds_clause_produces_a_real_live_token_instance():
    """The regression check that actually closes the gap: parsing the
    generated output and building a live Runtime via
    Runtime.build_from_spec() must produce real TokenInstances for the
    resolved burdens — not just plausible-looking `holds` text. Filtered
    to drop ServiceRequest/560 (tier 0c is independently known, per
    AM-71, to fail validation on its own commitment.by — unrelated to
    this fix, and would mask the regression check below)."""
    from el_parser import parse_string
    from el_runtime import Runtime

    bundle = _drop_service_request(_load_bundle(), "560")
    el = _generate(bundle)

    result = parse_string(el, validate=True)
    assert result.ok, f"Validation errors: {result.errors}"

    rt = Runtime.build_from_spec(result.model)
    tokens = {t.token_name: t for t in rt.current_state().tokens}

    assert "Id554Obligation" in tokens
    assert tokens["Id554Obligation"].holder == "BrisbaneEndocrinology"
    assert tokens["Id554Obligation"].kind == "burden"
    assert tokens["Id554Obligation"].state == "active"

    assert "Id555Obligation" in tokens
    assert tokens["Id555Obligation"].holder == "OconnorLiam"
    assert tokens["Id555Obligation"].state == "active"
