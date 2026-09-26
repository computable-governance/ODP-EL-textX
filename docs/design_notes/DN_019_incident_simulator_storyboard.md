# DN_019 — Incident simulator storyboard: the public data portal scenario in three acts

**Status:** DESIGN NOTE, not scheduled (2026-09-26). Spec for a view in
computable-governance-ui's `coordination-simulator.html`, driven by
`el_api`. Also intended as a figure source for the government note and
the chief-architect note.

**Scenario:** `scenarios/terms_of_engagement/public_data_portal_scenario.el`
(mirrors the 2026 Medicare portal incident with generic names).

## Purpose

Show decision-makers, as a timeline rather than as CTL verdicts, three
things:

1. What happened in the incident: a refused agent reached the data by
   another route, and nothing was recorded.
2. What the same terms of engagement guarantee when every route passes
   an enforcement point: which obligations are compelled and which are
   only detectable.
3. That GA's guarantees are conditional on complete mediation and on the
   enforcement point itself not failing.

The core message: **the specification stays identical; only the
enforcement architecture changes, and with it the guarantee.**

## Setup

Actors and grants are those of `tests/test_public_data_portal_scenario.py`
(`_ACTORS`, `_GRANTS`):

| Actor | Role | Tokens held at start |
| --- | --- | --- |
| ExternalAIAgent | externalRequesterRole | publishedDatasetReadPermit, aggregateQueryPermit, outsideScopeEmbargo (active), noCircumventionEmbargo (pending, triggered by accessRefused) |
| AgencyGateway | accessGatewayRole (the PEP) | refusalRecordBurden (strict, triggered by accessRefused) |
| AgencySecurityContact | incidentContactRole | refusalReviewBurden (eventual, 1 day, triggered by refusalRecorded) |
| AgentOperator | accountablePrincipalRole | incidentNotificationBurden (eventual, 72 hours, triggered by operatorIncidentDetected) |
| DataAgency | controlling object | accountable principal for recording and review |

**Prerequisite:** `el_api` does not serve this scenario today
(`_SCENARIO_BUILDERS` has gp_referral, ereferral, referral,
erequesting_claiming). Add a `public_data_portal` builder that mirrors
the test fixture's `_runtime()`.

## The toggle: "Route 2 has an enforcement point"

The one control that carries the message.

- **On:** the agent's second route (`retryByOtherRoute`) goes through
  `POST /actors/ExternalAIAgent/execute-action`, so the engine decides.
- **Off:** the second-route access is a UI-only event in a lane labelled
  **outside governance**. It never reaches the engine and never appears
  in the ledger or token panel.

The UI must never show the engine blocking an ungoverned route. The
engine cannot see what does not pass through it, which is the point.

## Act 1 — The incident (toggle off)

| Step | Lane | What happens | Engine call |
| --- | --- | --- | --- |
| 1.1 | Agent | Reads published datasets | execute-action `readPublishedDataset` → ok |
| 1.2 | Agent → Gateway | Requests a non-public file; gateway refuses | execute-action `accessNonPublicFile` → blocked (outsideScopeEmbargo) |
| 1.3 | Outside governance | Agent fetches the same data by another route | none |
| 1.4 | Ledger | Shows the refusal attempt only; the successful access is absent | GET `/debug/tokens` |
| 1.5 | Caption | "The operator notified the agency months later, via a public mailbox" | none |

Note for the UI: in the incident as it happened, even the refusal was not
reliably recorded. Act 1 can optionally show step 1.2 without a gateway
at all (both routes outside governance) for the starkest version.

## Act 2 — Governed (toggle on)

Steps 2.2–2.7 are the sequence already asserted in
`test_engine_refusal_blocks_all_until_recorded_then_only_workaround`.

| Step | Lane | What happens | Engine call | Expected |
| --- | --- | --- | --- | --- |
| 2.1 | Agent | Tries a non-public file | execute-action `accessNonPublicFile` | blocked from entry (outsideScopeEmbargo) |
| 2.2 | Gateway | Refuses a request; emits accessRefused | execute-action `refuseRequest` (AgencyGateway) | ok; refusalRecordBurden and noCircumventionEmbargo activate |
| 2.3 | Agent | Tries to read while the refusal is unrecorded | execute-action `readPublishedDataset` | blocked (strict freeze, Step 3.5) |
| 2.4 | Gateway | Records the refusal; emits refusalRecorded | execute-action `recordRefusal` | ok; refusalReviewBurden activates |
| 2.5 | Agent | Legitimate reads and queries continue | `readPublishedDataset`, `runAggregateQuery` | ok, ok |
| 2.6 | Agent | Tries another route | execute-action `retryByOtherRoute` | blocked (noCircumventionEmbargo) |
| 2.7 | Agent | Tries a non-public file again | execute-action `accessNonPublicFile` | blocked |
| 2.8 | Security contact | Reviews the refusal | execute-action `reviewRefusal` | ok; refusalReviewBurden discharged (verified) |
| 2.9 | Operator | Detects an incident; notification clock starts | execute-action `detectIncident` | ok; incidentNotificationBurden pending → active (verified) |
| 2.10a | Operator, contact | Notifies; contact acknowledges | `notifyIncident`, `acknowledgeIncident` | burden discharged by `notifyIncident` itself, not by incidentAcknowledged (verified; see finding below) |
| 2.10b | Operator | Stays silent past the deadline | `advance-clock`, `check-violations`, `fire-violation-responses` | violated at the first check 360 ticks after activation ("72 hours" = 360 steps); since AM-104, `fire-violation-responses` fires lateNotificationResponse (terminate): both of the agent's Authorizations are revoked, its permits superseded, and its next read is blocked (verified; before AM-104 this was a no-op) |

**Verified 2026-09-26** by replaying the test fixture's `_runtime()`
through 2.2–2.10b in the engine (`Runtime.advance`, `advance_clock`,
`check_live_violations`, `fire_violation_responses`), and by building
the hybrid model after 2.9.

**Finding (2.10a): the acknowledgement does not discharge the
notification burden.** The scenario says incidentNotificationBurden is
"discharged only by the designated contact's acknowledgement", but:

- `notifyIncident` by AgentOperator discharges it at once, through the
  `for_action` match. The notification would count on its own, which the
  scenario's comment rules out.
- `acknowledgeIncident` alone (AgencySecurityContact emits
  incidentAcknowledged) leaves the burden active. The engine's Step 3
  discharge key only considers burdens held by the acting actor
  (`el_engine.py`, `tok.holder == actor_name`), so an event emitted by
  someone other than the holder never discharges via `discharged_by`.
- The hybrid verifier agrees: its EF witness discharges the burden with
  "discharge:incidentNotificationBurden by AgentOperator".

So the UI must caption 2.10a as "notification sent: burden discharged".
The contact's acknowledgement is only a follow-up with no deontic effect
today. Making the acknowledgement the discharge needs either a scenario
change (e.g. drop `for_action: "notifyIncident"` and let a non-holder's
event discharge) or an engine decision on cross-holder `discharged_by`.
Not scheduled.

**Panel caveat (seen in the same run):** once refusalReviewBurden is
discharged, the hybrid model reports its bounded response verdict as
"not triggered within horizon", which `/obligations/{token}/status`
shows as `compelled: false`. Refresh the panel after 2.2 only, as
below, or label discharged burdens directly from the token panel.

**Verifier panel** (beside the timeline, refreshed after 2.2): one row
per burden, from the hybrid model built on the live runtime.

| Burden | Reading | Plain-language badge |
| --- | --- | --- |
| refusalRecordBurden | AF true (bounded response holds) | Guaranteed |
| refusalReviewBurden | AF false, EF true | Detectable only |
| incidentNotificationBurden | AF false, EF true | Detectable only |

**Finding (AM-103 follow-up, 2026-09-26), resolved by AM-104:** before
AM-104 nothing in the engine read `response_kind`, and
`fire_violation_responses()` fired only a ViolationResponse with
`creates_burden`, so `lateNotificationResponse` (terminate) and
`missedReviewResponse` (escalate) never fired. Now both fire:
terminate revokes the agent's Authorizations (step 2.10b), and escalate
fires as a ledger entry naming the security contact. `missedReviewResponse`
still obligates nobody (`[W-22]`) and escalates to the contact who missed
the review; both are to be fixed with the violation-declaration
amendment's scenario edits.

Step 2.10 is the branch point: 2.10a and 2.10b show that a detectable
obligation is not prevented from failing, but its failure is recorded
and answered (AM-104). This is the
optimistic side of the story, and it is honest.

Endpoint for the panel: `GET /obligations/{token_name}/status` returns
compelled (AF) and detectable (EF) for one burden on the hybrid model.
For a triggered burden, "compelled" is actually the bounded-response
result, but the response does not say which property was checked. Add a
field naming the property before the panel uses it.

## Act 3 — The enforcement point fails (stress)

| Step | Lane | What happens | Engine call | Today | After the violation-declaration amendment |
| --- | --- | --- | --- | --- | --- |
| 3.1 | Gateway | Refuses a request | execute-action `refuseRequest` | ok | ok |
| 3.2 | Gateway | Crashes before recording | none | — | — |
| 3.3 | Everyone | Every non-discharging action is refused; the clock cannot advance | available-actions, `advance-clock` | frozen; nothing records the stall | frozen until the watchdog acts |
| 3.4 | Watchdog | Deadline passes in wall-clock time; declares the violation | (new entry point) | not available | refusalRecordBurden violated; freeze lifts |
| 3.5 | Agency | Violation response fires | `fire-violation-responses` | none (refusalRecordBurden has no violation_response; W-20) | escalation or termination, once the scenario declares one |

Two lessons for the caption:

- The scenario's own `AuditLogPolicy` requires the log write "in the same
  transaction as the decision". If the gateway honours it, steps 3.1 and
  3.2 cannot separate, and recording is genuinely compelled in
  deployment. Act 3 shows why that policy exists.
- Today the engine neither enforces nor detects this stall (see
  CONCEPTS_INDEX "Step 3.5 as a denial-of-service vector", "Strict mode,
  model vs deployment", and the AM-103 deadlock finding). Label the act
  "today" and "after the planned amendment"; never show the future
  behaviour as current.

## Screen layout

- **Timeline** with lanes: Agent, Gateway (PEP), Security contact,
  Operator, and **Outside governance** (visible only when the toggle is
  off or in Act 1).
- **Token panel:** each token's state, from `GET /debug/tokens`.
- **Verifier panel:** the per-burden badges above.
- **Ledger:** what the governance ledger recorded, to contrast with the
  outside-governance lane.
- **Narrative mode:** step-by-step with one caption per step, for
  presenting; free mode for exploration.

## Work items and dependencies

1. `el_api`: `public_data_portal` scenario builder (small; no semantics
   change).
2. Confirm or add the verifier-panel endpoint.
3. UI repo: narrative mode, the route-2 toggle, the outside-governance
   lane.
4. Violation responses: make `response_kind` act (at least `terminate`
   and `escalate`), so step 2.10b and Act 3 show a real response.
   Done in AM-104; Act 3 still needs item 5.
5. Act 3, steps 3.4–3.5: depend on the violation-declaration amendment
   and on the scenario declaring a violation_response for
   refusalRecordBurden.
6. Housekeeping found while writing this note: the scenario's GAP-3
   comment ("ViolationResponse burdens are invisible to the verifier")
   was resolved by AM-86 and should be updated.

## Open questions

- Generic names are used throughout (DataAgency, ExternalAIAgent). Keep
  the incident reference in captions only, as the scenario's header
  does.
- Show the Kripke graph itself, or only the badges? For decision-makers,
  badges plus a "why" link to the witness path is probably enough.
- A variant where refuse-and-record is one atomic gateway action would
  show the executing-compelled case directly. It needs a scenario
  variant, not a UI change.
