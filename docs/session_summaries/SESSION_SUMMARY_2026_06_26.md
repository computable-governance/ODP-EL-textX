# Session Summary — 2026-06-26

**Topic:** Federation architecture — AM-26 CommunityObject, AM-27/AM-28
NormativePolicy, eReferral three-level governance stack. Also: extensive
design discussion on DSL vs LLM, legitimacy gap, policy/standard alignment.

## Design discussions (Claude.ai)

### DSL vs LLM — legitimacy gap (new §3.4 in position note addendum)
Three structural reasons why AI cannot originate governance frameworks:
1. **Legitimacy problem** — frameworks require human endorsement; ISO/IEC
   15414 authority derives from decades of deliberation, not formal correctness
2. **Bootstrapping problem** — AI reasons from human normative concepts;
   ODP-EL is a formalisation of accumulated human knowledge, not a
   mathematical primitive
3. **Recursive verification problem** — verifying an AI-derived framework
   requires a human-auditable meta-governance layer — structurally a DSL

Addendum written to DSL_LLM_Governance_Position_Note (saved locally).
New paper angle identified: "Legitimacy, Bootstrapping, and Recursive
Verification: Why AI Cannot Originate Governance Frameworks."

### Policy / standard alignment (Clause 6.5 + SoSyM paper)
- V1 `odppolicy.tx` already had `PolicySettingBehaviour` — AM-23 had dropped
  it; AM-27 restored it as `SettingBehaviour.who_can_change STRING → ID`
- `TokenGroup` confirmed as standard concept (§6.4.2) — earlier inventory
  was incorrect
- `NormativePolicy` designed as IS-A §6.5 Policy specialisation for
  externally-grounded normative instruments; valid only in Domain/Federation

### Federation design (§7.5.2 + Linington book ch.11)
Key architectural decisions:
- `CommunityObject` (§6.2.2) is the bridge: active EO abstracting a community,
  fills federation roles on behalf of member communities
- Federation = durable pre-existing contract (GP's preferred specialist list
  analogy); Episode = transient instance governed by federation contract
- `NormativePolicy` at Domain/Federation level captures regulatory instruments
  (My Health Records Act, National Clinical Governance) that flow down the
  domain hierarchy via §7.9.2 policy inheritance
- International Patient Summary (IPS) identified as cross-border federation
  use case — same pattern applied across AU/US/EU/CA jurisdictions

### Standard-grounded vs extended constructs (DSL_DESIGN_NOTES §5)
Full inventory documented — distinguishes standard constructs, incomplete
implementations, computability extensions, and usability additions.

## Implementation commits

| Commit | Change |
|--------|--------|
| 339bd66 | `docs/DSL_DESIGN_NOTES.md` §5 — standard-grounded vs extended constructs |
| 461623a | AM-26: `CommunityObject` SpecElement, federation `roles`, enriched `MemberRef` (`represented_by`, `fills`), P9 processor, V-NEW-19 validator, `el_runtime.py` dereference |
| a0a6c55 | AM-27: `SettingBehaviour.who_can_change` STRING → ID (§7.9.3) |
| 54c0f64 | AM-28: `NormativePolicy` grammar rule + `NormativePolicyKind` + `NormativePolicyRef`; domain/federation body items; `el_domain.py` dataclasses; P8/P9 handlers; V-NEW-20 placement validator |
| 528e41f | eReferral model: `GPPracticeObj`, `SpecialistPracticeObj`, `MyHealthRecordsAct`, `NationalClinicalGovernance`, `ReferralNetworkFederation` — three-level governance stack complete |

All pushed to origin/main (41a73f8..528e41f).

## Three-level governance stack (eReferral)
