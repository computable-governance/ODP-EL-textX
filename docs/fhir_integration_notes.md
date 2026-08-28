# FHIR ↔ Governed Autonomy: Mini Architecture Note

*Written to document a real, working pipeline built and verified in this
session — every claim below was run and checked, not assumed. Grounds the
architecture diagram alongside this note.*

---

## 1. The one-sentence architecture

**FHIR defines the data — what a clinical request, task, or consent looks
like, and how systems exchange it. Governed Autonomy reads that same data
and derives who is accountable, what obligations exist, and what
restrictions apply — without requiring any change to the FHIR data model
itself.**

## 2. The three components, concretely

| Component | What it is | What it holds |
|---|---|---|
| **FHIR server** | HAPI FHIR (Docker container, `localhost:8081`), loaded with the real AU Core and AU eRequesting Implementation Guides | Real, IG-validated resources: `Patient`, `Organization` (×2), `Practitioner`, `PractitionerRole`, `Encounter`, `ServiceRequest`, `Task`, `Consent` |
| **FHIR mapper** | `fhir_mapper.py`, part of the ODP-EL-textX toolchain | A set of numbered mapping rules (R05, R07, R09, R17, …) that each recognise one FHIR pattern and produce one governance construct |
| **DSL governance toolchain** | The ODP-EL grammar, live engine, and Kripke verifier | The generated `.el` governance specification — parties, commitments, delegations, burdens, embargoes — plus the machinery to reason over it |

## 3. What each mapping rule does, based on what was actually observed

- **R05** — a `ServiceRequest` becomes a `Commitment`: someone committed to
  a clinical request.
- **R07** — the same `ServiceRequest` also produces a `Burden`: the
  obligation that commitment creates.
- **R09** — a `Task` becomes a `Delegation`: fulfilment responsibility
  passed from one party to another.
- **R17** — a `Consent` becomes an `Embargo` (when the consent denies) or a
  `Permit` (when it grants): a restriction or allowance derived directly
  from the patient's real, recorded consent decision.

## 4. The accountability-resolution finding (the most important one)

`ServiceRequest.requester` in FHIR is deliberately about *who placed the
order* — usually the individual clinician. Legal/governance accountability
is often a level higher: the *organisation* that clinician works for.

The mapper handles this with two resolution paths, both verified directly
against real data this session:

- If `requester` already points at a `PractitionerRole`, the mapper uses
  that reference as-is.
- If `requester` points at a **bare `Practitioner`**, the mapper searches
  the bundle for a `PractitionerRole` linking that practitioner to an
  `Organization`, and resolves accountability **up to the organisation**.

Verified outcome: changing `ServiceRequest.requester` from
`PractitionerRole/generalpractitioner-guthridge-jarred` to
`Practitioner/guthridge-jarred` (with the `PractitionerRole` present in the
bundle) changed the generated `commitment.by` from
`GeneralpractitionerGuthridgeJarred` to `ElimbahMedicalCentre` — the
correct legal party, not the individual clinician.

## 5. The live pipeline, as it actually runs today

An ad-hoc local script (`run_live_mapper.py`, not committed to this
repo — session-local only):
1. Fetches `ServiceRequest`, `Task`, `Consent`, and `PractitionerRole` live
   from the HAPI server via ordinary HTTP `GET` requests.
2. Assembles them into a FHIR `Bundle`.
3. Passes that bundle to `FHIRConsentMapper.map_bundle()`.
4. Prints the generated `.el` governance specification.

This is a genuinely direct connection — no manual data reconstruction, no
intermediary. Run it again after changing anything on the HAPI server (a
new `Task`, an updated `Consent`) and the governance spec regenerates
accordingly. If this pipeline is needed again, the script should be
recreated (or a committed equivalent written) rather than assumed present.

## 6. What this pipeline does *not* yet do (named honestly, not implied)

- **It is one-directional.** The governance layer reads from FHIR; it
  never writes back. A governance decision (e.g. a claim being resolved)
  does not currently update any FHIR resource.
- **It is pull, not push.** Someone (or a script on a timer) has to run
  the mapper. There is no live event subscription yet connecting a FHIR
  change to an automatic re-run — though the toolchain already has one
  working live push mechanism elsewhere (FHIR `Consent` → `el_api.py`'s
  `POST /fhir/consent-events` → `revoke_authorization()`), which is the
  template for extending this further.
- **`R07`'s `for_action` mapping has a known, reproducible gap** — SNOMED
  code `26604007` ("Complete blood count") isn't yet in the mapper's
  action-lookup table, so it falls back to a slug with an explicit
  `UNRESOLVED` flag in the description rather than guessing. This was
  found independently twice this session (once against the two official
  published IG examples, once against this live pipeline) — a real,
  confirmed gap, not a one-off glitch.

## 7. Why this is a meaningful demonstration, not just a technical exercise

It shows, concretely, the core Governed Autonomy claim: **FHIR resources
carry the operational facts; the governance layer derives the
accountability facts from them** — and does so correctly even when the
naive, surface-level reading (accountability = whoever's named in
`requester`) would get it wrong. The `PractitionerRole` resolution is a
small, precise example of exactly that gap between operational data and
legal responsibility, solved by a few lines of real, tested code.

## 8. HAPI persistence — a real root cause, worth recording precisely

*Added 2026-08-28. Two prior attempts at this failed silently; recorded
here so the actual fix, and the reasoning behind it, isn't lost.*

**The symptom:** every `docker stop`/`docker rm`/`docker run` cycle wiped
all data, even after mounting `-v ~/hapi-data:/app/data`.

**The wrong diagnosis (tried first, didn't work):** assumed the volume
was mounted to the wrong internal path. Fixing the path made no
difference — because the mount location was never the actual problem.

**The real root cause:** HAPI's own default `application.yaml` configures
an **in-memory** H2 database:
```yaml
datasource:
    url: jdbc:h2:mem:test_mem
```
`jdbc:h2:mem:` means the entire database lives in the JVM's RAM. Nothing
is ever written to any file, on any path, mounted or not. A volume mount
can only persist data that gets written to disk in the first place — no
mount location could have fixed this, because the problem was never
about *where* the data was being saved, only *that* it never was.

**The actual fix:** override the datasource in the local
`~/hapi-config/application.yaml`, adding a top-level `spring:` block
(sibling to the existing `hapi:` block) pointing at a **file-based** H2
database inside the mounted volume:
```yaml
spring:
  datasource:
    url: jdbc:h2:file:/app/data/h2
    username: sa
    password: null
    driver-class-name: org.h2.Driver
```

**Verified, not assumed:** created a throwaway `Basic` resource,
restarted the container immediately via `~/start-hapi.sh`, and confirmed
the resource came back with its *original* `versionId` and
`lastUpdated` timestamp unchanged — proof it survived rather than got
silently recreated. This is the standard of evidence any future
persistence claim about this server should be held to; "it looks fine"
was insufficient twice in a row before this.

**Practical note:** `docker run --restart unless-stopped` (also added to
`~/start-hapi.sh`) is a separate, complementary fix — it tells Docker to
auto-restart the container when the Docker daemon itself comes back
(e.g. after a Mac reboot), so the container process returns on its own.
It does nothing for data persistence by itself; both fixes were needed
together.
