"""
fhir_mapper.py
==============
FHIR R4 → DSL-EL Governance Mapping

Implements the formal mapping between FHIR R4 resources and ODP-EL
governance constructs (ISO/IEC 15414:2015), as specified in Table 2
of the position paper "DSL + LLM as Complementary Layers" (May 2026).

Mapping coverage (22 rules):
  R01  Organization             → party (data controller)
  R02  Patient                  → party (data subject)
  R03  Practitioner             → party or agent (role-dependent)
  R04  Device                   → agent (AI system)
  R05  ServiceRequest           → CommitmentDecl
  R06  ServiceRequest.requester → commitment.by
  R07  ServiceRequest.code/note → obligation text + burden token
  R08  ServiceRequest.occurrence→ deadline on burden
  R09  Task                     → DelegationDecl
  R10  Task.requester           → delegation.from
  R11  Task.owner               → delegation.to
  R12  Task.basedOn             → traces to root commitment
  R13  Task.partOf              → sub-delegation
  R14  Task.restriction.period  → deadline on burden
  R15  Task.status              → ObligationState lifecycle note
  R16  Consent.provision=permit → permit token + AuthorizationDecl
  R17  Consent.provision=deny   → embargo token
  R18  Consent creation         → AuthorizationDecl
  R19  Consent.performer        → authorization.to_agent
  R20  Consent.organization     → authorization.authority
  R21  Consent.provision.period → deadline on token
  R22  Consent.status=inactive  → DeclarationDecl (withdrawal)

Also (separate entry point, not part of FHIRConsentMapper.map_bundle —
see extract_federation_from_contract() below):
  R23+R24  Contract.signer/.term → FederationDecl membership + normative_policy refs
           EXTRACTION direction (FHIR → ODP-EL), standing/static structure,
           not wired into el_api.py. See
           FHIR_ODP_EL_Positioning_Notes_2026-06-26.md §2 for the full
           rationale (supersedes the earlier OrganizationAffiliation- and
           Consent.policyRule-based R23/R24 proposals).

Deferred (later sessions):
  R32  AuditEvent               → governance ledger entry
  Bidirectional mapping (DSL speech act → FHIR update)

Usage
-----
    from fhir_mapper import FHIRConsentMapper

    mapper = FHIRConsentMapper()
    el_spec = mapper.map_bundle_file("ai_diagnostic_bundle.json")
    print(el_spec)

    # Or from a dict already loaded
    import json
    bundle = json.loads(open("ai_diagnostic_bundle.json").read())
    el_spec = mapper.map_bundle(bundle)

    # Write to file and parse
    with open("generated_governance.el", "w") as f:
        f.write(el_spec)

    from el_parser import parse
    result = parse("generated_governance.el")
"""

from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ══════════════════════════════════════════════════════════════════════════════
# Mapping rules — each rule is a named constant for traceability
# ══════════════════════════════════════════════════════════════════════════════

MAPPING_RULES = {
    "R01": ("Organization",              "party (data controller)"),
    "R02": ("Patient",                   "party (data subject)"),
    "R03": ("Practitioner",              "party or agent (role-dependent)"),
    "R04": ("Device",                    "agent (AI system)"),
    "R05": ("ServiceRequest",            "CommitmentDecl"),
    "R06": ("ServiceRequest.requester",  "commitment.by"),
    "R07": ("ServiceRequest.code/note",  "obligation text + burden token"),
    "R08": ("ServiceRequest.occurrence", "deadline on burden"),
    "R09": ("Task",                      "DelegationDecl"),
    "R10": ("Task.requester",            "delegation.from"),
    "R11": ("Task.owner",                "delegation.to"),
    "R12": ("Task.basedOn",              "traces to root commitment"),
    "R13": ("Task.partOf",               "sub-delegation flag"),
    "R14": ("Task.restriction.period",   "deadline on burden"),
    "R15": ("Task.status",               "ObligationState lifecycle note"),
    "R16": ("Consent.provision=permit",  "permit token + AuthorizationDecl"),
    "R17": ("Consent.provision=deny",    "embargo token"),
    "R18": ("Consent creation",          "AuthorizationDecl"),
    "R19": ("Consent.performer",         "authorization.to_agent"),
    "R20": ("Consent.organization",      "authorization.authority"),
    "R21": ("Consent.provision.period",  "deadline on token"),
    "R22": ("Consent.status=inactive",   "DeclarationDecl (withdrawal)"),
    "R23+R24": ("Contract.signer/.term", "FederationDecl membership + normative_policy refs"),
}


# ══════════════════════════════════════════════════════════════════════════════
# Internal representation — intermediate between FHIR and .el text
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ELObject:
    """Corresponds to ObjectDecl in the grammar (party or agent)."""
    el_id: str
    kind: str                    # "party" | "agent"
    description: str
    delegated_from: Optional[str] = None    # el_id of principal
    principal_of: List[str] = field(default_factory=list)
    fhir_ref: str = ""           # original FHIR reference for provenance

@dataclass
class ELToken:
    """Corresponds to DeonticTokenDecl in the grammar."""
    el_id: str
    kind: str                    # "burden" | "permit" | "embargo"
    for_action: str
    deadline: str = ""
    discharge_mode: str = "eventual"
    priority: str = "normal"
    description: str = ""
    fhir_ref: str = ""

@dataclass
class ELCommitment:
    """Corresponds to CommitmentDecl."""
    el_id: str
    by: str                      # el_id of committing party
    obligation: str
    creates_burden: str          # el_id of burden token
    description: str = ""
    fhir_ref: str = ""

@dataclass
class ELDelegation:
    """Corresponds to DelegationDecl."""
    el_id: str
    from_obj: str                # el_id
    to_obj: str                  # el_id
    obligation: str
    transfers_burden: str        # el_id of burden token
    duration: str = ""
    revocable: bool = True
    sub_delegation_allowed: bool = False
    creates_reporting_burden: bool = True
    description: str = ""
    fhir_ref: str = ""

@dataclass
class ELAuthorization:
    """Corresponds to AuthorizationDecl."""
    el_id: str
    authority: str               # el_id
    to_agent: str                # el_id
    grants_permit: str           # el_id of permit token
    duration: str = ""
    revocable: bool = True
    on_revocation: str = ""      # el_id of embargo token (AM-31-V2 fix)
    description: str = ""
    fhir_ref: str = ""

@dataclass
class ELDeclaration:
    """Corresponds to DeclarationDecl — used for consent withdrawal (R22)."""
    el_id: str
    by: str                      # el_id
    state_of_affairs: str
    description: str = ""
    fhir_ref: str = ""

@dataclass
class ELSpec:
    """Complete intermediate representation of a generated governance spec."""
    spec_id: str
    description: str
    fhir_bundle_id: str
    objects: List[ELObject] = field(default_factory=list)
    tokens: List[ELToken] = field(default_factory=list)
    commitments: List[ELCommitment] = field(default_factory=list)
    delegations: List[ELDelegation] = field(default_factory=list)
    authorizations: List[ELAuthorization] = field(default_factory=list)
    declarations: List[ELDeclaration] = field(default_factory=list)
    mapping_log: List[Tuple[str, str, str]] = field(default_factory=list)
    # (rule_id, fhir_ref, el_id) — provenance trail

    def log(self, rule: str, fhir_ref: str, el_id: str) -> None:
        self.mapping_log.append((rule, fhir_ref, el_id))


# ══════════════════════════════════════════════════════════════════════════════
# ID sanitisation
# ══════════════════════════════════════════════════════════════════════════════

def _sanitize_id(raw: str) -> str:
    """
    Convert a FHIR reference or display string to a valid textX identifier.

    textX identifiers must match /[^\\d\\W]\\w*/ — start with letter/underscore,
    contain only alphanumerics and underscores. No hyphens, slashes, spaces.

    Examples:
      "Organization/gp-practice-001"  → "GPPractice001"
      "Practitioner/dr-chen"          → "DrChen"
      "Device/ai-diagnostic-agent-001"→ "AiDiagnosticAgent001"
      "Patient/patient-jane-smith"    → "PatientJaneSmith"
    """
    # Strip resource type prefix (e.g. "Organization/")
    if "/" in raw:
        raw = raw.split("/", 1)[1]

    # Title-case each hyphen/underscore-separated segment, then join
    parts = re.split(r"[-_\s]+", raw)
    result = "".join(p.capitalize() for p in parts if p)

    # Ensure starts with letter
    if result and result[0].isdigit():
        result = "Id" + result

    # Remove any remaining invalid chars
    result = re.sub(r"[^\w]", "", result)

    return result or "UnknownId"


def _ref_id(ref_dict: Optional[dict]) -> str:
    """Extract and sanitise the 'reference' field from a FHIR reference object."""
    if not ref_dict:
        return ""
    return _sanitize_id(ref_dict.get("reference", ""))


def _text(obj: Optional[dict], *keys: str) -> str:
    """Safely extract nested text from a FHIR dict."""
    if not obj:
        return ""
    for k in keys:
        obj = obj.get(k, {}) if isinstance(obj, dict) else {}
    return obj if isinstance(obj, str) else ""


def _coding_display(coding_list: Optional[list]) -> str:
    """Get first display text from a coding array."""
    if not coding_list:
        return ""
    first = coding_list[0] if coding_list else {}
    return first.get("display", first.get("code", ""))


def _period_to_deadline(period: Optional[dict]) -> str:
    """Convert a FHIR Period to a deadline string."""
    if not period:
        return ""
    end = period.get("end", "")
    start = period.get("start", "")
    if end:
        return f"by {end}"
    if start:
        return f"from {start}"
    return ""


_VALID_TEXTX_ID_RE = re.compile(r"^[^\d\W]\w*$")


def _preserve_or_sanitize(raw: str) -> str:
    """
    [R23+R24] Return raw unchanged if it is already a valid textX identifier;
    otherwise fall back to _sanitize_id's lossy hyphen/space-splitting
    sanitiser.

    Used where the FHIR source value (an Organization.name or a coding.code)
    is expected to already carry DSL-EL naming convention by construction —
    e.g. a governance-oriented bundle authored to name an organisation
    "GPPractice" to match its DSL-EL community counterpart directly.
    _sanitize_id alone cannot reproduce that casing: its capitalize()-based
    splitter lowercases everything after each segment's first letter, so
    "GPPractice" would come back as "Gppractice".
    """
    if raw and _VALID_TEXTX_ID_RE.match(raw):
        return raw
    return _sanitize_id(raw)


def _role_id_from_coding(coding_list: Optional[list]) -> str:
    """
    [R23+R24] Derive an interface role identifier from a FHIR coding.

    Prefers coding.code, trusted to already be a camelCase role name by
    convention (e.g. "gpPracticeRole") and used verbatim when it is already
    a valid identifier. Falls back to coding.display, sanitised and then
    lower-camel-cased, only when code is absent or not already valid.
    """
    if not coding_list:
        return ""
    first = coding_list[0]
    raw = first.get("code") or first.get("display") or ""
    if not raw:
        return ""
    if _VALID_TEXTX_ID_RE.match(raw):
        return raw
    base = _sanitize_id(raw)
    return (base[0].lower() + base[1:]) if base else ""


def _legally_binding_source(contract: dict, by_ref: Dict[str, dict]) -> str:
    """
    [R23+R24] Resolve Contract.legallyBindingReference (if present) to a
    human-readable source citation, by looking at the referenced resource's
    'description' then 'title' field. Returns "" if there is no reference,
    it doesn't resolve within the bundle, or the resolved resource carries
    neither field — never fabricates a citation.
    """
    ref = contract.get("legallyBindingReference", {}).get("reference", "")
    if not ref:
        return ""
    target = by_ref.get(ref)
    if not target:
        return ""
    return target.get("description", "") or target.get("title", "")


# ══════════════════════════════════════════════════════════════════════════════
# Main mapper class
# ══════════════════════════════════════════════════════════════════════════════

class FHIRConsentMapper:
    """
    Maps a FHIR R4 Bundle (containing Consent, ServiceRequest, Task,
    and supporting resources) to a DSL-EL governance specification.

    The mapping implements the 22 rules defined in MAPPING_RULES, each
    traceable to the formal mapping table in the position paper (Table 2
    extended with ServiceRequest and Task).

    Usage:
        mapper = FHIRConsentMapper()
        el_text = mapper.map_bundle_file("bundle.json")
    """

    def map_bundle_file(self, path: str) -> str:
        """Load a FHIR Bundle JSON file and return the generated .el spec."""
        with open(path) as f:
            bundle = json.load(f)
        return self.map_bundle(bundle)

    def map_bundle(self, bundle: dict) -> str:
        """
        Map a FHIR Bundle dict to a DSL-EL governance specification string.

        Processes resources in dependency order:
          1. Demographics (Organization, Patient, Practitioner, Device)
          2. ServiceRequest (commitment root)
          3. Task (delegation chain)
          4. Consent (authorization + tokens)
        """
        spec = ELSpec(
            spec_id=_sanitize_id(bundle.get("id", "FHIRBundle")),
            description=f"Generated from FHIR Bundle/{bundle.get('id', 'unknown')}",
            fhir_bundle_id=bundle.get("id", ""),
        )

        entries = bundle.get("entry", [])
        resources = [e.get("resource", {}) for e in entries]

        # Index by resourceType for cross-reference resolution
        by_type: Dict[str, List[dict]] = {}
        by_ref: Dict[str, dict] = {}
        for r in resources:
            rt = r.get("resourceType", "")
            by_type.setdefault(rt, []).append(r)
            by_ref[f"{rt}/{r.get('id', '')}"] = r

        # Determine which Practitioners appear as Task owners
        # (agents) vs ServiceRequest requesters (parties)
        task_owners: set = set()
        for task in by_type.get("Task", []):
            owner_ref = task.get("owner", {}).get("reference", "")
            if owner_ref:
                task_owners.add(owner_ref)

        # 1 — Demographics
        for org in by_type.get("Organization", []):
            self._map_organization(org, spec)       # R01
        for pat in by_type.get("Patient", []):
            self._map_patient(pat, spec)            # R02
        for prac in by_type.get("Practitioner", []):
            ref = f"Practitioner/{prac.get('id', '')}"
            self._map_practitioner(prac, ref, task_owners, spec)  # R03
        for dev in by_type.get("Device", []):
            self._map_device(dev, spec)             # R04

        # 2 — ServiceRequest → commitment + burden
        for sr in by_type.get("ServiceRequest", []):
            self._map_service_request(sr, spec)     # R05–R08

        # 3 — Tasks → delegation chain
        # Sort: parent tasks (no partOf) first, then sub-tasks
        tasks = by_type.get("Task", [])
        parent_tasks = [t for t in tasks if not t.get("partOf")]
        child_tasks  = [t for t in tasks if t.get("partOf")]
        for task in parent_tasks + child_tasks:
            self._map_task(task, spec)              # R09–R15

        # 4 — Consent → tokens + authorization
        for consent in by_type.get("Consent", []):
            self._map_consent(consent, spec)        # R16–R22

        # Infer delegation relationships from object declarations
        self._infer_delegation_structure(spec)

        # Generate the .el text
        return self._render_el(spec)

    # ── R01 — Organization → party ────────────────────────────────────────────

    def _map_organization(self, org: dict, spec: ELSpec) -> None:
        el_id = _sanitize_id(f"Organization/{org.get('id', '')}")
        name  = org.get("name", el_id)
        obj = ELObject(
            el_id=el_id,
            kind="party",
            description=f"[R01] Data controller: {name}",
            fhir_ref=f"Organization/{org.get('id', '')}",
        )
        spec.objects.append(obj)
        spec.log("R01", f"Organization/{org.get('id', '')}", el_id)

    # ── R02 — Patient → party ─────────────────────────────────────────────────

    def _map_patient(self, pat: dict, spec: ELSpec) -> None:
        el_id = _sanitize_id(f"Patient/{pat.get('id', '')}")
        names = pat.get("name", [{}])
        given  = " ".join(names[0].get("given", [])) if names else ""
        family = names[0].get("family", "") if names else ""
        display = f"{given} {family}".strip() or el_id
        obj = ELObject(
            el_id=el_id,
            kind="party",
            description=f"[R02] Data subject (patient): {display}",
            fhir_ref=f"Patient/{pat.get('id', '')}",
        )
        spec.objects.append(obj)
        spec.log("R02", f"Patient/{pat.get('id', '')}", el_id)

    # ── R03 — Practitioner → party or agent ───────────────────────────────────

    def _map_practitioner(
        self,
        prac: dict,
        ref: str,
        task_owners: set,
        spec: ELSpec,
    ) -> None:
        el_id  = _sanitize_id(ref)
        names  = prac.get("name", [{}])
        given  = " ".join(names[0].get("given", [])) if names else ""
        family = names[0].get("family", "") if names else ""
        display = f"Dr {given} {family}".strip() or el_id

        qual = prac.get("qualification", [{}])
        role_display = _coding_display(qual[0].get("code", {}).get("coding", [])) if qual else ""

        # R03: practitioner is an agent if they appear as Task.owner,
        # otherwise a party (ordering clinician)
        kind = "agent" if ref in task_owners else "party"

        obj = ELObject(
            el_id=el_id,
            kind=kind,
            description=f"[R03] {'Agent' if kind == 'agent' else 'Party'}: {display} ({role_display})",
            fhir_ref=ref,
        )
        spec.objects.append(obj)
        spec.log("R03", ref, el_id)

    # ── R04 — Device → agent ──────────────────────────────────────────────────

    def _map_device(self, dev: dict, spec: ELSpec) -> None:
        el_id   = _sanitize_id(f"Device/{dev.get('id', '')}")
        names   = dev.get("deviceName", [{}])
        display = names[0].get("name", el_id) if names else el_id
        obj = ELObject(
            el_id=el_id,
            kind="agent",
            description=f"[R04] AI agent: {display}",
            fhir_ref=f"Device/{dev.get('id', '')}",
        )
        spec.objects.append(obj)
        spec.log("R04", f"Device/{dev.get('id', '')}", el_id)

    # ── R05–R08 — ServiceRequest → CommitmentDecl + burden token ──────────────

    def _map_service_request(self, sr: dict, spec: ELSpec) -> None:
        sr_id       = sr.get("id", "sr")
        el_id       = _sanitize_id(f"ServiceRequest/{sr_id}")
        fhir_ref    = f"ServiceRequest/{sr_id}"

        # R06 — requester
        requester_el = _ref_id(sr.get("requester"))                  # R06

        # R07 — obligation text from code + note
        code_text    = sr.get("code", {}).get("text", "")
        code_display = _coding_display(sr.get("code", {}).get("coding", []))
        notes        = sr.get("note", [{}])
        note_text    = notes[0].get("text", "") if notes else ""
        obligation   = note_text or code_text or code_display or "Fulfil service request"

        # R07 — burden token
        burden_id = f"{el_id}Obligation"
        action    = code_display or code_text or "perform_service"
        deadline  = sr.get("occurrenceDateTime", "")                 # R08

        # Annotate notes: if the obligation mentions "consent", make strict+critical
        consent_related = any(
            kw in (note_text + code_text).lower()
            for kw in ["consent", "inform", "seek"]
        )

        token = ELToken(
            el_id=burden_id,
            kind="burden",
            for_action=action.lower().replace(" ", "_"),
            deadline=deadline,
            discharge_mode="strict" if consent_related else "eventual",
            priority="critical" if consent_related else "normal",
            description=f"[R07] Obligation arising from ServiceRequest/{sr_id}",
            fhir_ref=fhir_ref,
        )
        spec.tokens.append(token)
        spec.log("R07", fhir_ref, burden_id)

        # R05 — commitment
        commitment = ELCommitment(
            el_id=f"{el_id}Commitment",
            by=requester_el,
            obligation=obligation,
            creates_burden=burden_id,
            description=f"[R05] Commitment from ServiceRequest/{sr_id}",
            fhir_ref=fhir_ref,
        )
        spec.commitments.append(commitment)
        spec.log("R05", fhir_ref, commitment.el_id)

    # ── R09–R15 — Task → DelegationDecl ───────────────────────────────────────

    def _map_task(self, task: dict, spec: ELSpec) -> None:
        task_id  = task.get("id", "task")
        el_id    = _sanitize_id(f"Task/{task_id}")
        fhir_ref = f"Task/{task_id}"

        # R10 — requester (delegator)
        from_el = _ref_id(task.get("requester"))                     # R10

        # R11 — owner (delegate)
        to_el   = _ref_id(task.get("owner"))                         # R11

        if not from_el or not to_el:
            return  # cannot map without both ends

        # R12 — trace back to ServiceRequest to find obligation and burden
        based_on  = task.get("basedOn", [{}])
        sr_ref    = based_on[0].get("reference", "") if based_on else ""
        sr_el     = _sanitize_id(sr_ref) if sr_ref else ""
        burden_id = f"{sr_el}Obligation" if sr_el else ""
        obligation = self._find_obligation_text(sr_el, spec) or "Fulfil delegated task"

        # R14 — deadline from restriction.period
        restriction = task.get("restriction", {})
        period      = restriction.get("period", {})
        deadline    = period.get("end", period.get("start", ""))     # R14

        # R13 — this task is a sub-task; find and mark the PARENT delegation
        # as sub_delegation_allowed (the parent must permit further delegation)
        part_of = task.get("partOf", [])
        if part_of:
            parent_ref = part_of[0].get("reference", "")
            parent_el  = _sanitize_id(parent_ref) if parent_ref else ""
            parent_del_id = f"{parent_el}Delegation"
            for d in spec.delegations:
                if d.el_id == parent_del_id:
                    d.sub_delegation_allowed = True
                    break

        # R15 — status note
        status = task.get("status", "requested")                     # R15
        desc   = task.get("description", "")
        note   = (task.get("note") or [{}])[0].get("text", "")

        delegation = ELDelegation(
            el_id=f"{el_id}Delegation",
            from_obj=from_el,
            to_obj=to_el,
            obligation=obligation,
            transfers_burden=burden_id,
            duration=deadline,
            revocable=True,
            sub_delegation_allowed=False,  # set to True by child task via R13
            creates_reporting_burden=True,
            description=f"[R09] Delegation from Task/{task_id} (status={status}). {desc or note}".strip(". "),
            fhir_ref=fhir_ref,
        )
        spec.delegations.append(delegation)
        spec.log("R09", fhir_ref, delegation.el_id)

        # Update agent's delegated_from (so ObjectDecl body is correct)
        self._set_delegated_from(to_el, from_el, spec)

    def _find_obligation_text(self, sr_el_id: str, spec: ELSpec) -> str:
        """Find the obligation text for a commitment matching this ServiceRequest el_id."""
        for c in spec.commitments:
            if sr_el_id and c.el_id.startswith(sr_el_id):
                return c.obligation
        return ""

    def _set_delegated_from(self, agent_id: str, principal_id: str, spec: ELSpec) -> None:
        """Set the delegated_from field on an agent object."""
        for obj in spec.objects:
            if obj.el_id == agent_id:
                obj.kind = "agent"
                if not obj.delegated_from:
                    obj.delegated_from = principal_id
                # Add to principal's principal_of list
                for principal in spec.objects:
                    if principal.el_id == principal_id:
                        if agent_id not in principal.principal_of:
                            principal.principal_of.append(agent_id)
                break

    # ── R16–R22 — Consent → tokens + AuthorizationDecl ────────────────────────

    def _map_consent(self, consent: dict, spec: ELSpec) -> None:
        consent_id = consent.get("id", "consent")
        fhir_ref   = f"Consent/{consent_id}"
        el_id      = _sanitize_id(fhir_ref)

        # R19 — performer → to_agent
        performers = consent.get("performer", [{}])
        to_agent   = _ref_id(performers[0]) if performers else ""    # R19

        # R20 — organization → authority
        orgs      = consent.get("organization", [{}])
        authority = _ref_id(orgs[0]) if orgs else ""                 # R20

        # R21 — provision period → deadline
        provision = consent.get("provision", {})
        period    = provision.get("period", {})
        deadline  = _period_to_deadline(period)                      # R21

        # R16/R17 — provisions → permit and embargo tokens
        prov_type = provision.get("type", "permit")
        actions   = provision.get("action", [{}])
        action_code = _coding_display(actions[0].get("coding", [])) if actions else "access"

        permit_id  = None
        embargo_id = None

        if prov_type == "permit":                                     # R16
            permit_id = f"{el_id}Permit"
            token = ELToken(
                el_id=permit_id,
                kind="permit",
                for_action=action_code.lower().replace(" ", "_"),
                deadline=deadline,
                description=f"[R16] Permit from Consent/{consent_id}",
                fhir_ref=fhir_ref,
            )
            spec.tokens.append(token)
            spec.log("R16", fhir_ref, permit_id)

        elif prov_type == "deny":                                     # R17
            embargo_id = f"{el_id}Embargo"
            token = ELToken(
                el_id=embargo_id,
                kind="embargo",
                for_action=action_code.lower().replace(" ", "_"),
                deadline=deadline,
                description=f"[R17] Embargo from Consent/{consent_id}",
                fhir_ref=fhir_ref,
            )
            spec.tokens.append(token)
            spec.log("R17", fhir_ref, embargo_id)

        # Sub-provisions (nested deny clauses)
        for sub_prov in provision.get("provision", []):
            sub_type = sub_prov.get("type", "deny")
            sub_actions = sub_prov.get("action", [{}])
            sub_action  = _coding_display(sub_actions[0].get("coding", [])) if sub_actions else "disclose"
            sub_id = f"{el_id}SubProv{len(spec.tokens)}Embargo" if sub_type == "deny" \
                     else f"{el_id}SubProv{len(spec.tokens)}Permit"
            sub_token = ELToken(
                el_id=sub_id,
                kind="embargo" if sub_type == "deny" else "permit",
                for_action=sub_action.lower().replace(" ", "_"),
                description=f"[R17] Sub-provision from Consent/{consent_id}",
                fhir_ref=fhir_ref,
            )
            spec.tokens.append(sub_token)
            spec.log("R17" if sub_type == "deny" else "R16", fhir_ref, sub_id)
            # AM-31-V2 fix: link the most recent deny sub-provision as the
            # on_revocation target. Known limitation: if a Consent has more
            # than one deny sub-provision, only the last is linked — a single
            # AuthorizationDecl can only reference one on_revocation embargo
            # (grammar §7.10.2), so a multi-embargo Consent would need either
            # a TokenGroup or a design decision on which embargo governs
            # withdrawal. Not currently exercised by any test bundle.
            if sub_type == "deny":
                embargo_id = sub_id

        # R18 — authorization speech act
        if authority and to_agent and permit_id:                      # R18
            has_embargo = embargo_id is not None
            auth = ELAuthorization(
                el_id=f"{el_id}Auth",
                authority=authority,
                to_agent=to_agent,
                grants_permit=permit_id,
                duration=deadline,
                # AM-31-V2: only mark revocable when an embargo exists to
                # activate on revocation — an authorization can't be
                # meaningfully "revocable" with no architectural consequence.
                revocable=has_embargo,
                on_revocation=embargo_id if has_embargo else "",
                description=f"[R18] Authorization from Consent/{consent_id}",
                fhir_ref=fhir_ref,
            )
            spec.authorizations.append(auth)
            spec.log("R18", fhir_ref, auth.el_id)

        # R22 — if consent is inactive, generate declaration (withdrawal)
        if consent.get("status") == "inactive":                       # R22
            performer_el = to_agent or authority
            if performer_el:
                decl = ELDeclaration(
                    el_id=f"{el_id}Withdrawal",
                    by=performer_el,
                    state_of_affairs=f"Consent {consent_id} has been withdrawn — all associated permits revoked",
                    description=f"[R22] Consent withdrawal from Consent/{consent_id}",
                    fhir_ref=fhir_ref,
                )
                spec.declarations.append(decl)
                spec.log("R22", fhir_ref, decl.el_id)

    # ── Infer delegation structure from object bodies ─────────────────────────

    def _infer_delegation_structure(self, spec: ELSpec) -> None:
        """
        Ensure every agent has a delegated_from set (required by grammar)
        and every party that is a principal has principal_of populated.
        This fills gaps where FHIR resources implied the relationship
        but did not state it explicitly.
        """
        # Build index of el_ids
        obj_index = {o.el_id: o for o in spec.objects}

        # For each delegation, ensure the structural body is consistent
        for d in spec.delegations:
            if d.from_obj in obj_index and d.to_obj in obj_index:
                agent   = obj_index[d.to_obj]
                principal = obj_index[d.from_obj]
                if not agent.delegated_from:
                    agent.delegated_from = d.from_obj
                if d.to_obj not in principal.principal_of:
                    principal.principal_of.append(d.to_obj)

    # ══════════════════════════════════════════════════════════════════════════
    # .el file renderer
    # ══════════════════════════════════════════════════════════════════════════

    def _render_el(self, spec: ELSpec) -> str:
        """Render the ELSpec intermediate representation as a .el file string."""
        lines: List[str] = []

        # Header comment
        lines += [
            "/*",
            f" * Generated governance specification",
            f" * Source: FHIR Bundle/{spec.fhir_bundle_id}",
            f" * Generator: fhir_mapper.py (ComputableGovernance toolchain)",
            f" * Mapping rules applied: {', '.join(sorted(set(r for r, _, _ in spec.mapping_log)))}",
            " *",
            " * This file is machine-generated. Do not edit manually.",
            " * Re-generate by running: python fhir_mapper.py",
            " */",
            "",
            f"enterprise specification {spec.spec_id}GovernanceSpec",
            f'    description: "{spec.description}"',
            f'    field_of_application: "Clinical AI governance — FHIR-sourced"',
            f'    scope: "Consent, delegation, and authorization governance for AI-assisted clinical workflows"',
            "",
        ]

        # Objects
        lines.append("// ── Parties and Agents " + "─" * 38)
        for obj in spec.objects:
            lines += self._render_object(obj)
            lines.append("")

        # Tokens
        lines.append("// ── Deontic Tokens " + "─" * 41)
        for tok in spec.tokens:
            lines += self._render_token(tok)
            lines.append("")

        # Community block (required by grammar — generated from obligations)
        lines.append("// ── Community (generated) " + "─" * 35)
        lines += self._render_community(spec)
        lines.append("")

        # Commitments
        lines.append("// ── Commitments " + "─" * 44)
        for c in spec.commitments:
            lines += self._render_commitment(c)
            lines.append("")

        # Delegations
        if spec.delegations:
            lines.append("// ── Delegations " + "─" * 44)
            for d in spec.delegations:
                lines += self._render_delegation(d)
                lines.append("")

        # Authorizations
        if spec.authorizations:
            lines.append("// ── Authorizations " + "─" * 41)
            for a in spec.authorizations:
                lines += self._render_authorization(a)
                lines.append("")

        # Declarations
        if spec.declarations:
            lines.append("// ── Declarations (consent withdrawal) " + "─" * 23)
            for d in spec.declarations:
                lines += self._render_declaration(d)
                lines.append("")

        # Provenance comment
        lines += self._render_provenance(spec)

        return "\n".join(lines)

    def _render_object(self, obj: ELObject) -> List[str]:
        lines = [
            f"{obj.kind} {obj.el_id}",
            f'    description: "{obj.description}"',
        ]
        has_body = obj.delegated_from or obj.principal_of
        if has_body:
            lines.append("    {")
            if obj.delegated_from:
                lines.append(f"        delegated_from {obj.delegated_from}")
            for p in obj.principal_of:
                lines.append(f"        principal_of {p}")
            lines.append("    }")
        return lines

    def _render_token(self, tok: ELToken) -> List[str]:
        lines = [f"{tok.kind} {tok.el_id} {{"]
        if tok.for_action:
            lines.append(f'    for_action: "{tok.for_action}"')
        # AM-31 convention: an embargo not yet triggered by an on_revocation
        # clause has no valid "not yet active" state in the current grammar;
        # 'pending' is used as the nearest fit (see AM-31, gp_referral_scenario.el).
        lines.append(f'    state: {"pending" if tok.kind == "embargo" else "active"}')
        if tok.deadline:
            lines.append(f'    deadline: "{tok.deadline}"')
        if tok.kind == "burden":
            lines.append(f'    discharge_mode: {tok.discharge_mode}')
            lines.append(f'    priority: {tok.priority}')
        if tok.description:
            lines.append(f'    description: "{tok.description}"')
        lines.append("}")
        return lines

    def _render_community(self, spec: ELSpec) -> List[str]:
        """
        Generate a minimal community block — required by the grammar.
        Derives the objective from the first commitment's obligation text.
        """
        objective = "Govern AI-assisted clinical workflow in accordance with consent obligations"
        if spec.commitments:
            objective = spec.commitments[0].obligation

        # Collect all burden token IDs for role requirements
        burden_ids = [t.el_id for t in spec.tokens if t.kind == "burden"]
        permit_ids = [t.el_id for t in spec.tokens if t.kind == "permit"]

        lines = [
            f"community {spec.spec_id}Community",
            f'    description: "Generated governance community for {spec.spec_id}"',
            "    {",
            f'        objective: "{objective[:120]}"',
            "",
            '        invariant consentBeforeAnalysis:',
            '            "AI diagnostic analysis must not proceed without documented patient consent"',
        ]

        # Assignment policies for agents holding burdens
        for obj in spec.objects:
            if obj.kind == "agent" and burden_ids:
                role_name = f"{obj.el_id[0].lower()}{obj.el_id[1:]}Role"
                lines += [
                    f"            assignment_policy for {role_name} {{",
                    f'                requires_capability: "Must hold delegated obligation"',
                ]
                if burden_ids:
                    lines.append(
                        f'                requires_token burden: "Must hold {burden_ids[0]}"'
                    )
                lines.append("            }")

        # Roles for each agent
        for obj in spec.objects:
            if obj.kind == "agent":
                role_name = f"{obj.el_id[0].lower()}{obj.el_id[1:]}Role"
                lines += [
                    f"        role {role_name}",
                    f'            description: "Role for {obj.el_id}"',
                    "            {}",
                ]

        lines.append("    }")
        return lines

    def _render_commitment(self, c: ELCommitment) -> List[str]:
        return [
            f"commitment {c.el_id} {{",
            f"    by: {c.by}",
            f'    obligation: "{c.obligation[:200]}"',
            f"    creates_burden: {c.creates_burden}",
            f'    description: "{c.description}"',
            "}",
        ]

    def _render_delegation(self, d: ELDelegation) -> List[str]:
        lines = [
            f"delegation {d.el_id} {{",
            f"    from: {d.from_obj}",
            f"    to: {d.to_obj}",
            f'    obligation: "{d.obligation[:200]}"',
        ]
        if d.transfers_burden:
            lines.append(f"    transfers_burden: {d.transfers_burden}")
        if d.creates_reporting_burden:
            lines.append("    creates_reporting_burden: true")
        if d.duration:
            lines.append(f'    duration: "{d.duration}"')
        if d.sub_delegation_allowed:
            lines.append("    sub_delegation_allowed: true")
        if d.revocable:
            lines.append("    revocable: true")
        if d.description:
            lines.append(f'    description: "{d.description[:200]}"')
        lines.append("}")
        return lines

    def _render_authorization(self, a: ELAuthorization) -> List[str]:
        lines = [
            f"authorization {a.el_id} {{",
            f"    authority: {a.authority}",
            f"    to_agent: {a.to_agent}",
            f"    grants_permit: {a.grants_permit}",
        ]
        if a.duration:
            lines.append(f'    duration: "{a.duration}"')
        if a.revocable:
            lines.append("    revocable: true")
        if a.on_revocation:
            lines.append(f"    on_revocation: activate {a.on_revocation}")
        if a.description:
            lines.append(f'    description: "{a.description}"')
        lines.append("}")
        return lines

    def _render_declaration(self, d: ELDeclaration) -> List[str]:
        return [
            f"declaration {d.el_id} {{",
            f"    by: {d.by}",
            f'    state_of_affairs: "{d.state_of_affairs[:200]}"',
            f'    description: "{d.description}"',
            "}",
        ]

    def _render_provenance(self, spec: ELSpec) -> List[str]:
        lines = [
            "",
            "/*",
            " * Mapping provenance — FHIR resource → DSL-EL construct",
            " *",
        ]
        for rule, fhir_ref, el_id in spec.mapping_log:
            rule_desc = MAPPING_RULES.get(rule, ("", ""))[1]
            lines.append(f" * [{rule}] {fhir_ref:45s} → {el_id}  ({rule_desc})")
        lines.append(" */")
        return lines


# ══════════════════════════════════════════════════════════════════════════════
# R23+R24 — Contract → contract federation (extraction, standalone entry point)
# ══════════════════════════════════════════════════════════════════════════════

def extract_federation_from_contract(bundle: dict) -> str:
    """
    [R23+R24] FHIR Contract → ODP-EL contract federation block (extraction).

    Maps a single FHIR R4 Contract resource — .signer, .term, and (read-only,
    provenance-only) .rule — to a standing ODP-EL federation structure, per
    FHIR_ODP_EL_Positioning_Notes_2026-06-26.md §2 (the R23+R24 merged rule,
    superseding the earlier OrganizationAffiliation- and
    Consent.policyRule-based R23/R24 proposals).

    Direction: EXTRACTION (FHIR → ODP-EL), same as R01-R22 in
    FHIRConsentMapper above — federation membership is standing/static
    structure (established once), not a runtime event stream, so this is a
    standalone function, not wired into el_api.py.

    Mapping
    -------
    Contract.signer[]  → one 'member:' declaration per entry:
        signer.party → resolved to an Organization in the same bundle;
            the Organization's name (preferred verbatim if already a valid
            identifier, else sanitised) names the member community
            ("<Org>Community") and its representing community_object
            ("<Org>Obj").
        signer.type  → coding.code (preferred, assumed already camelCase by
            convention) or coding.display (sanitised fallback) names the
            interface role the member fills.
    Contract.term[]     → normative_policy references. Each term's type
        coding names the referenced NormativePolicy. Where a source
        citation is independently derivable (Contract.term.text, else
        Contract.legallyBindingReference resolved to a description/title
        in-bundle), a *commented-out* normative_policy stub is also emitted
        with that citation pre-filled — see "What is NOT emitted" below for
        why 'kind' can never be filled in automatically.
    Contract.rule        → read for provenance only (logged in a trailing
        comment); does not affect the generated structure.

    What is NOT emitted (and why)
    ------------------------------
    - The member 'community' declarations themselves — Contract carries no
      data for a community's objective/roles/etc; fabricating one would
      misrepresent the source data.
    - Live 'normative_policy' declarations — 'source' (a real citation) can
      sometimes be recovered from the bundle (see above), but 'kind'
      (legislation | regulation | standard | guideline | contractual) is a
      DSL-specific classification with no FHIR field or coding system
      behind it. Grammar requires both 'source' and 'kind' on every
      NormativePolicy (grammar/v2/el_grammar.tx NormativePolicy rule) —
      there is no syntax for "kind: unknown" that still parses — so this
      function never emits a live normative_policy block. When a source
      citation is recoverable, a *commented-out* stub is emitted with
      'source' filled in and 'kind' marked for the caller to complete; the
      rest of the output remains genuinely parseable regardless.

    The returned text therefore references member communities and
    normative policies by name and assumes both are declared elsewhere in
    the target specification — exactly the arrangement in
    referral_scenario.el, where GPPracticeCommunity/SpecialistPracticeCommunity
    and MyHealthRecordsAct/NationalClinicalGovernance/AIMedicalDeviceRegulation
    are separate top-level elements alongside ReferralNetworkFederation.

    Error handling
    --------------
    - No Contract resource anywhere in the bundle → ValueError. A missing
      Contract means there is no federation to extract; returning an empty
      or partial string would silently produce ungoverned output.
    - A signer.party reference that does not resolve to an Organization in
      the bundle → ValueError (not skipped). A federation member that
      cannot be identified is a governance-integrity gap, not a
      recoverable/optional detail — unlike e.g. an unpaired Task in
      FHIRConsentMapper._map_task, which has legitimate reasons to be
      incomplete.

    Returns
    -------
    str — one 'community_object' declaration per signer, followed by a
    single 'contract federation { ... }' block, followed by any commented
    normative_policy stubs and a Contract.rule provenance comment. Not a
    full enterprise specification — concatenate into a spec that already
    declares the referenced Community and NormativePolicy elements.
    """
    entries = bundle.get("entry", [])
    resources = [e.get("resource", {}) for e in entries]

    contracts = [r for r in resources if r.get("resourceType") == "Contract"]
    if not contracts:
        raise ValueError(
            "extract_federation_from_contract: bundle contains no Contract "
            "resource — nothing to extract a federation from."
        )
    contract = contracts[0]
    contract_id = contract.get("id", "contract")

    by_ref: Dict[str, dict] = {
        f"{r.get('resourceType', '')}/{r.get('id', '')}": r for r in resources
    }

    # Federation name: prefer Contract.title (sanitised), suffixed with
    # "Federation" unless already present; fall back to Contract/<id>.
    if contract.get("title"):
        base_name = _sanitize_id(contract["title"])
    else:
        base_name = _sanitize_id(f"Contract/{contract_id}")
    fed_el_id = base_name if base_name.endswith("Federation") else f"{base_name}Federation"

    fed_description = contract.get("title") or f"Federation extracted from Contract/{contract_id}"
    objective = contract.get("title") or (
        "Ensure governed cooperation among federation member communities"
    )

    # ── signer[] → member communities + interface roles ────────────────────
    members: List[dict] = []
    for signer in contract.get("signer", []):
        party_ref = signer.get("party", {}).get("reference", "")
        org = by_ref.get(party_ref)
        if org is None or org.get("resourceType") != "Organization":
            raise ValueError(
                f"extract_federation_from_contract: Contract/{contract_id} "
                f"signer.party '{party_ref}' does not resolve to an "
                f"Organization resource in this bundle."
            )

        org_base = _preserve_or_sanitize(
            org.get("name") or f"Organization/{org.get('id', '')}"
        )
        community_id = f"{org_base}Community"
        object_id = f"{org_base}Obj"

        role_id = _role_id_from_coding(signer.get("type", {}).get("coding", []))
        if not role_id:
            role_id = f"{org_base[0].lower()}{org_base[1:]}Role"

        members.append({
            "community_id": community_id,
            "object_id": object_id,
            "role_id": role_id,
            "org_name": org.get("name", org_base),
        })

    # ── term[] → normative_policy references (+ stub where source found) ──
    policies: List[dict] = []
    for term in contract.get("term", []):
        codings = term.get("type", {}).get("coding", [])
        raw = codings[0].get("code") or codings[0].get("display") if codings else ""
        name = _preserve_or_sanitize(raw) if raw else ""
        if not name:
            continue
        source = term.get("text", "") or _legally_binding_source(contract, by_ref)
        policies.append({"name": name, "source": source})

    # ── rule[] → provenance only, never drives output ──────────────────────
    rule_refs = [
        r.get("contentReference", {}).get("reference", "")
        for r in contract.get("rule", [])
        if r.get("contentReference", {}).get("reference", "")
    ]

    lines: List[str] = []

    # community_object declarations — one per signer
    for m in members:
        lines.append(f"community_object {m['object_id']}")
        lines.append(
            f'    description: "[R23+R24] Community object representing '
            f'{m["community_id"]} in {fed_el_id}"'
        )
        lines.append("    {")
        lines.append(f"        abstracts: {m['community_id']}")
        lines.append("    }")
        lines.append("")

    # contract federation block
    lines.append(f"contract federation {fed_el_id}")
    lines.append(f'    description: "[R23+R24] {fed_description}"')
    lines.append("    {")
    lines.append(f'        objective: "{objective}"')
    lines.append("")

    for p in policies:
        lines.append(f"        normative_policy: {p['name']}")
    if policies:
        lines.append("")

    for m in members:
        lines.append(f"        interface role {m['role_id']}")
        lines.append(
            f'            description: "[R23+R24] {m["org_name"]} interface '
            f'role in {fed_el_id}"'
        )
        lines.append("            {}")
        lines.append("")

    for m in members:
        lines.append(f"        member: {m['community_id']}")
        lines.append(f"            represented_by {m['object_id']}")
        lines.append(f"            fills {m['role_id']}")
        lines.append("")

    lines.append("    }")

    # commented normative_policy stubs — only where a real source citation
    # was recoverable; 'kind' can never be filled in automatically (see
    # docstring "What is NOT emitted")
    stubs = [p for p in policies if p["source"]]
    if stubs:
        lines.append("")
        lines.append(
            "// [R23+R24] normative_policy stub(s) — 'source' derived from "
            "FHIR Contract; 'kind' requires human classification (no FHIR "
            "field or coding system backs this DSL taxonomy). Uncomment and "
            "complete before the target spec will parse."
        )
        for p in stubs:
            lines.append(f"// normative_policy {p['name']} {{")
            lines.append(f'//     source: "{p["source"]}"')
            lines.append(
                "//     kind: <FILL IN — legislation | regulation | standard "
                "| guideline | contractual>"
            )
            lines.append("// }")

    if rule_refs:
        lines.append("")
        lines.append(
            f"// [R23+R24 provenance] Contract/{contract_id}.rule → "
            f"{', '.join(rule_refs)} (traceability only; not rendered)"
        )

    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    bundle_file  = sys.argv[1] if len(sys.argv) > 1 else "ai_diagnostic_bundle.json"
    output_file  = sys.argv[2] if len(sys.argv) > 2 else "generated_governance.el"

    mapper   = FHIRConsentMapper()
    el_spec  = mapper.map_bundle_file(bundle_file)

    with open(output_file, "w") as f:
        f.write(el_spec)

    print(f"✓ Generated: {output_file}")
    print(f"  Source   : {bundle_file}")
    print()

    # Validate by parsing
    try:
        sys.path.insert(0, ".")
        from el_parser import parse
        result = parse(output_file)
        if result.ok:
            print(f"✓ Parsed successfully: {result.model.name}")
            print(f"  Elements : {len(result.model.elements)}")
        else:
            print("✗ Parse errors:")
            for e in result.errors:
                print(f"  {e}")
    except ImportError:
        print("  (el_parser not available — skipping parse validation)")
    except Exception as e:
        print(f"✗ Parse error: {e}")
