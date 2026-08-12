"""
fhir_event_handler.py
======================
Layer 1 -> Layer 3 bridge: FHIR R4 Consent/Encounter resource events ->
runtime authorization/token state changes.

Standard reference: ISO/IEC 15414:2015 §6.6.4 (Authorization), §6.4/§7.8
(DeonticToken lifecycle, AM-22 triggered_by/EventDecl). AM-31
(Runtime.revoke_authorization, toolchain/el_engine.py) and Runtime.fire_event()
(toolchain/el_engine.py/el_runtime.py, built on the AM-22 triggered_by
mechanism) are the underlying engine primitives this module calls into —
this module does not duplicate that logic, it only decides when to call it
from a FHIR event.

Scope (rule numbers per FHIR_ODP_EL_Positioning_Notes):

R31 — Consent.status: active -> inactive (implemented here in full).
  A FHIR Consent resource transitioning to status "inactive" represents
  patient withdrawal of consent. handle_consent_event() calls
  Runtime.revoke_authorization("patientDataAuthorization") directly
  (in-process; this module does not itself make an HTTP call) — the same
  engine path already exercised by POST /authorizations/{name}/revoke in
  el_api.py. This supersedes patientRecordAccessPermitByAuthorization and
  activates patientRecordAccessEmbargo (see AM-31, AM-31b). The FHIR
  Consent.id is carried through as fhir_provenance on the result.

R30 — Consent.status: active (Option B, live grant/reinstate; implemented
  here in full, 2026-08-13).
  A FHIR Consent bundle with status="active" received AFTER runtime
  construction calls Runtime.reinstate_authorization(authorization_name)
  directly (in-process, the same pattern R31 already established for
  revoke). reinstate_authorization() (AM-31 mirror, el_engine.py) handles
  both directions with a single branch: if the permit was previously
  granted (most likely 'superseded' from a prior revoke), it is
  transitioned back to 'active'; if it was never granted at all, it is
  instantiated and granted fresh to the Authorization's to_agent. Either
  way, if an on_revocation embargo is currently 'active' for this
  authorization, it is transitioned to 'lifted' — a state distinct from
  'superseded' (which means a Permit lost governance to an Embargo, the
  opposite relationship). The FHIR Consent.id is carried through as
  fhir_provenance on the result, mirroring R31.
  A FHIR Consent bundle with status="active" received BEFORE runtime
  construction still determines the initial authorization state via
  build_from_spec()/build_from_federation() or the hand-written scenario
  builders in el_api.py, as before — this section only concerns events
  arriving after construction.

R26-R29 probe — Encounter.status: finished -> fires 'encounterConcluded'
  event (probe-tier; see docs/CONCEPTS_INDEX.md "Toolchain implementation
  priority sequencing", item #1). handle_encounter_event() calls
  Runtime.fire_event() directly (in-process), activating any token whose
  triggered_by matches the fired event name — currently only
  referralInitiationBurden in scenarios/referral/referral_scenario.el,
  via the AM-22 triggered_by/EventDecl mechanism (el_engine.py Step 7c /
  _activate_triggered_tokens(), shared with action-driven emits).

  Unlike R31's revoke_authorization(), fire_event() never raises for an
  unrecognised event name — a mismatched or unwired event is silently a
  no-op at the engine level (empty triggered set, empty effects log).
  handle_encounter_event() does NOT collapse this into the same
  action_taken as a genuine activation: it inspects the returned
  TransitionRecord.effects and reports three distinct outcomes —
    "fired"           — event fired AND at least one token's triggered_by
                         matched (transition.effects non-empty).
    "fired_no_match"  — event genuinely fired via Runtime.fire_event()
                         (tick advances, a ledger entry is recorded) but no
                         token in the current spec has triggered_by set to
                         this event name, so transition.effects is empty.
                         This is the case that would otherwise be a silent
                         no-op if action_taken were not distinguished from
                         "fired".
    "no_op"           — status is not "finished"/"cancelled"/
                         "entered-in-error"; fire_event() is never called
                         at all, and transition stays None.
  event_name/transition are set for both "fired" and "fired_no_match"
  (fire_event() was actually called in both cases); only "no_op" leaves
  them None.

  status="cancelled"/"entered-in-error" raise ValueError — no clinical
  decision occurred; this is a bootstrap-time integrity gap, not a
  recoverable no-op (mirrors extract_encounter_context's existing error
  philosophy, fhir_mapper.py).

  This is a probe-only wiring of the fire_event()/triggered_by mechanism —
  it does NOT implement the full Encounter.status-driven token-state
  seeding design (status -> state mapping table, deadline computation,
  etc.) tracked as item #1 in docs/CONCEPTS_INDEX.md's priority
  sequencing; that remains future work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from el_engine import TransitionRecord
from el_runtime import Runtime

# Scenario-specific: the single patient-consent Authorization declared in
# scenarios/referral/referral_scenario.el (and gp_referral_scenario.el).
# Passed as a default parameter rather than hardwired so callers targeting
# a different scenario's authorization name can override it.
PATIENT_DATA_AUTHORIZATION = "patientDataAuthorization"

# Scenario-specific: the single Encounter-triggered event declared in
# scenarios/referral/referral_scenario.el (GPPracticeCommunity's events
# list, R26-R29 probe). Passed as a default parameter rather than hardwired
# so callers targeting a different scenario's event name can override it.
ENCOUNTER_CONCLUDED_EVENT = "encounterConcluded"


@dataclass(frozen=True)
class ConsentEventResult:
    """Outcome of feeding one FHIR Consent resource to handle_consent_event()."""
    fhir_consent_id: str
    fhir_status: str
    action_taken: str              # "revoked" | "reinstated" | "already_active" | "no_op"
    message: str
    fhir_provenance: str           # == fhir_consent_id; carried for API-layer stamping
    authorization_name: Optional[str] = None   # set when action_taken in ("revoked", "reinstated", "already_active")
    transition: Optional[TransitionRecord] = None   # set when action_taken in ("revoked", "reinstated", "already_active")


@dataclass(frozen=True)
class EncounterEventResult:
    """Outcome of feeding one FHIR Encounter resource to handle_encounter_event().

    action_taken is one of "fired" | "fired_no_match" | "no_op" — see the
    module docstring's R26-R29 probe section for exactly what each means.
    event_name/transition are set for "fired" and "fired_no_match" alike
    (fire_event() was actually called in both); only "no_op" leaves them None.
    """
    fhir_encounter_id: str
    fhir_status: str
    action_taken: str              # "fired" | "fired_no_match" | "no_op"
    message: str
    fhir_provenance: str           # == fhir_encounter_id; carried for API-layer stamping
    event_name: Optional[str] = None                # None only when action_taken == "no_op"
    transition: Optional[TransitionRecord] = None    # None only when action_taken == "no_op"


def handle_consent_event(
    consent: dict,
    runtime: Runtime,
    authorization_name: str = PATIENT_DATA_AUTHORIZATION,
) -> ConsentEventResult:
    """
    Apply a FHIR R4 Consent resource event to `runtime`.

    status == "inactive" (R31): revokes `authorization_name` via
      Runtime.revoke_authorization(), which supersedes the permit it
      grants and activates its on_revocation embargo.
    status == "active" (R30 Option B): (re-)establishes `authorization_name`
      via Runtime.reinstate_authorization(). reinstate_authorization()
      never raises for an already-active permit, so this branch inspects
      the returned TransitionRecord.effects to distinguish a genuine
      reinstatement ("reinstated") from a call that found the permit
      already active with nothing to change ("already_active") — the same
      effects-inspection mechanism handle_encounter_event() (below) uses
      to distinguish "fired" from "fired_no_match", verified by reading
      that function directly. There is no API endpoint wrapping
      handle_encounter_event() to compare against, so this is a mechanism
      match at the handler level only, not a verified match to any
      existing API response shape — el_api.py's decision to give
      "already_active" the same full response shape as "reinstated"
      (tick/authority/outcome all populated) was made on its own merits
      (a real TransitionRecord exists either way), not against precedent.
      Both outcomes carry the real transition on the result; only the
      true no-op below (status not "active"/"inactive") leaves transition
      as None.
    any other status: no-op; not a recognised event by this handler.

    Raises ValueError if the Consent resource is missing 'id' or 'status'.
    Raises KeyError if authorization_name is not declared in the runtime's
    spec, or has no on_revocation embargo — the same failure mode as
    Runtime.revoke_authorization() itself (AM-31); callers (e.g. the
    POST /fhir/consent-events endpoint) are expected to translate this to
    an error response the same way revoke_authorization_endpoint() does.
    """
    consent_id = consent.get("id")
    status = consent.get("status")
    if not consent_id:
        raise ValueError("Consent resource missing required 'id' field")
    if not status:
        raise ValueError("Consent resource missing required 'status' field")

    if status == "inactive":
        tr = runtime.revoke_authorization(authorization_name)
        return ConsentEventResult(
            fhir_consent_id=consent_id,
            fhir_status=status,
            action_taken="revoked",
            message=(
                f"Consent '{consent_id}' status=inactive: revoked "
                f"authorization '{authorization_name}'."
            ),
            fhir_provenance=consent_id,
            authorization_name=authorization_name,
            transition=tr,
        )

    if status == "active":
        tr = runtime.reinstate_authorization(authorization_name)
        if tr.effects:
            return ConsentEventResult(
                fhir_consent_id=consent_id,
                fhir_status=status,
                action_taken="reinstated",
                message=(
                    f"Consent '{consent_id}' status=active: reinstated "
                    f"authorization '{authorization_name}', "
                    f"{'; '.join(tr.effects)}."
                ),
                fhir_provenance=consent_id,
                authorization_name=authorization_name,
                transition=tr,
            )
        return ConsentEventResult(
            fhir_consent_id=consent_id,
            fhir_status=status,
            action_taken="already_active",
            message=(
                f"Consent '{consent_id}' status=active: authorization "
                f"'{authorization_name}' was already active — nothing "
                "changed."
            ),
            fhir_provenance=consent_id,
            authorization_name=authorization_name,
            transition=tr,
        )

    return ConsentEventResult(
        fhir_consent_id=consent_id,
        fhir_status=status,
        action_taken="no_op",
        message=(
            f"Consent '{consent_id}' status='{status}' is not handled by "
            "this event handler (only 'active' and 'inactive' are wired; "
            "R31 handles 'inactive', R30 handles 'active' as a no-op)."
        ),
        fhir_provenance=consent_id,
    )


def handle_encounter_event(
    encounter: dict,
    runtime: Runtime,
    event_name: str = ENCOUNTER_CONCLUDED_EVENT,
) -> EncounterEventResult:
    """
    Apply a FHIR R4 Encounter resource event to `runtime`.

    status == "finished" (R26-R29 probe): fires `event_name` (default
      'encounterConcluded') via Runtime.fire_event(). Runtime.fire_event()
      never raises for an unmatched event name, so this branch inspects the
      returned TransitionRecord.effects to distinguish a genuine activation
      ("fired") from a fire that matched no token's triggered_by
      ("fired_no_match") — see module docstring for full detail. Both
      outcomes carry the real transition on the result; only the true
      no-op below (status not "finished") leaves transition as None.
    status == "cancelled" or "entered-in-error": raises ValueError — no
      clinical decision occurred; this is a bootstrap-time integrity gap,
      not a recoverable no-op (mirrors extract_encounter_context's
      existing error philosophy, fhir_mapper.py).
    any other status (planned/arrived/triaged/in-progress/onleave/unknown):
      no-op; not yet handled by this handler. fire_event() is not called.

    Raises ValueError if the Encounter resource is missing 'id' or 'status',
    or if status is 'cancelled'/'entered-in-error'.
    """
    encounter_id = encounter.get("id")
    status = encounter.get("status")
    if not encounter_id:
        raise ValueError("Encounter resource missing required 'id' field")
    if not status:
        raise ValueError("Encounter resource missing required 'status' field")

    if status == "finished":
        tr = runtime.fire_event(event_name, source=f"fhir:Encounter/{encounter_id}")
        if tr.effects:
            return EncounterEventResult(
                fhir_encounter_id=encounter_id,
                fhir_status=status,
                action_taken="fired",
                message=(
                    f"Encounter '{encounter_id}' status=finished: fired event "
                    f"'{event_name}', activating: {'; '.join(tr.effects)}."
                ),
                fhir_provenance=encounter_id,
                event_name=event_name,
                transition=tr,
            )
        return EncounterEventResult(
            fhir_encounter_id=encounter_id,
            fhir_status=status,
            action_taken="fired_no_match",
            message=(
                f"Encounter '{encounter_id}' status=finished: fired event "
                f"'{event_name}', but no token in the current spec has "
                f"triggered_by='{event_name}' — nothing was activated."
            ),
            fhir_provenance=encounter_id,
            event_name=event_name,
            transition=tr,
        )

    if status in ("cancelled", "entered-in-error"):
        raise ValueError(
            f"Encounter '{encounter_id}' status='{status}': no clinical "
            "decision occurred — this is a bootstrap-time integrity gap, "
            "not a recoverable no-op (mirrors extract_encounter_context's "
            "error philosophy, fhir_mapper.py)."
        )

    return EncounterEventResult(
        fhir_encounter_id=encounter_id,
        fhir_status=status,
        action_taken="no_op",
        message=(
            f"Encounter '{encounter_id}' status='{status}' is not handled "
            "by this event handler (only 'finished' fires an event; "
            "'cancelled' and 'entered-in-error' raise ValueError)."
        ),
        fhir_provenance=encounter_id,
    )
