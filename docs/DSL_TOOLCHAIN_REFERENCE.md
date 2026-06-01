# DSL-EL Toolchain — Technical Reference
## Validator, Reasoner, and Architecture Overview

This document describes what each component of the DSL-EL toolchain does,
how they relate to each other, and where they sit in the four-layer
ComputableGovernance stack. Intended as project context for future sessions.

---

## Component Overview

```
el_grammar.tx     — textX grammar defining the DSL syntax
el_parser.py      — loads grammar, parses .el files, invokes validator
el_validator.py   — 15 semantic rules checked at specification time
el_reasoner.py    — governance queries over the static model
el_kripke.py      — Layer 4 Kripke semantics (modal obligation verification)
example.el        — payment processing scenario exercising all constructs
```

---

## The Validator (`el_validator.py`)

### What it does

Runs at **specification time**, before any execution. Takes a parsed DSL-EL
model and checks 15 structural rules, each traced to a specific clause of
ISO/IEC 15414:2015. Analogous to a compiler's semantic phase — the grammar
checks syntax, the validator checks meaning.

Returns a list of error strings. Empty list = structurally sound specification.
Does not execute anything; reasons over the static model only.

### The 15 rules

| Rule | Clause | What it checks |
|------|--------|----------------|
| V-01 | §7.7   | Every community has exactly one objective |
| V-02 | §7.8.5 | Every process has at least one step |
| V-03 | §7.8.5 | Every step has at least one actor |
| V-04 | §7.8.5 | Process declares initiation and termination |
| V-05 | §7.8.2 | Assignment policy references an existing role |
| V-06 | §7.7   | Sub-objective assigned_to references existing role or process |
| V-07 | §7.10.1| Delegation from/to must be party or agent kind |
| V-08 | §7.10.1| Sub-delegation only if parent has sub_delegation_allowed: true |
| V-09 | §6.4.1 | A deontic token held by exactly one active enterprise object |
| V-10 | §6.6.2 | Commitment actor must be party or agent |
| V-11 | §7.10.5| Prescription actor must be party/agent or hold a permit |
| V-12 | §7.5.2 | Federation members reference declared communities |
| V-13 | §7.9.4 | Pessimistic enforcement must declare a mechanism |
| V-14 | §7.9.1 | PolicyRef target exists in community scope |
| V-15 | §7.10.1| Delegation obligation traces back to a CommitmentDecl |

### Usage

```python
from el_validator import validate_spec
errors = validate_spec(model)   # returns list[str]
```

Or via the parser (validation is on by default):

```python
from el_parser import parse
result = parse("my_spec.el")
if result.ok:
    print("Valid")
else:
    for err in result.errors:
        print(err)
```

---

## The Reasoner (`el_reasoner.py`)

### What it does

Also runs over the **static model**, but asks governance queries rather than
checking rules. Three queries are implemented. The reasoner does not execute
or simulate — it reasons over the declared structure.

### Query 1 — `ultimate_accountability()` (primary query)

**The question:** "Which party is ultimately accountable for obligation O
through the delegation chain?"

**Algorithm:**
1. Find all CommitmentDecls whose obligation text matches the query
2. Build a directed delegation graph: delegator → delegate
3. Walk the chain forward from the committing party to the current holder
4. Return an AccountabilityChain with root party, origin commitment,
   ordered delegation hops, and current holder

**Returns:** `List[AccountabilityChain]`

Each `AccountabilityChain` has:
- `obligation`: the obligation text
- `root_party`: the ultimately accountable party (root of chain)
- `root_commitment`: name of the CommitmentDecl that created the obligation
- `chain`: ordered list of `DelegationLink` objects (each hop)
- `current_holder`: who currently holds the obligation

Each `DelegationLink` records: delegation name, from/to names, obligation,
sub_delegation_allowed flag, revocable flag, duration, conditions,
creates_reporting_burden flag.

**Example output:**
```
Obligation : 'Process all customer payments within SLA'
Root party : MerchantParty  ← ULTIMATELY ACCOUNTABLE
Origin     : commitment 'merchantSLACommitment'
Chain      :
  [merchantToGatewayDelegation] MerchantParty ──► PaymentGatewayParty
                                 (12 months)  [sub-delegation allowed]  [reporting burden]
    [gatewayToProcessorDelegation] PaymentGatewayParty ──► PaymentProcessorAgent
                                   (6 months)  [reporting burden]
Holder now : PaymentProcessorAgent
```

**Usage:**
```python
from el_reasoner import ultimate_accountability
chains = ultimate_accountability(spec, "Process all customer payments within SLA")
for chain in chains:
    print(chain.render())
```

---

### Query 2 — `can_perform()` (deontic capability check)

**The question:** "Can actor X perform action Y given their current token holdings?"

Implements §6.4.6 conditional action semantics:
- Actor must hold required permits (requires_permit declarations)
- Actor must NOT hold active embargos for the action (inhibited_by_embargo)
- Burdens do not block but favouring burdens are noted

**Important limitation:** This is a *static* check against declared token
holdings in ObjectDecl bodies. Runtime token state changes (via speech acts)
are not modelled — this is structural, not operational. Sepanosian's engine
handles the dynamic/operational version.

**Returns:** `CanPerformResult` with:
- `permitted`: bool
- `blocking_embargos`: list of embargo names preventing action
- `missing_permits`: list of permit names required but not held
- `explanation`: human-readable reason

**Usage:**
```python
from el_reasoner import can_perform
result = can_perform(spec, "PaymentGatewayParty", "authoriseTransaction")
print(result.render())
```

---

### Query 3 — `policy_conflicts()` (cross-community conflict detection)

**The question:** "Are there conflicting policies across communities?"

Scans all communities and their policy references. Detects cases where one
community's policy creates an `obligation` on a target while another creates
a `prohibition` on the same target.

**Returns:** `List[PolicyConflict]`, each with community_a, community_b,
obligation text, and description.

**Usage:**
```python
from el_reasoner import policy_conflicts
conflicts = policy_conflicts(spec)
if conflicts:
    for c in conflicts:
        print(c.description)
```

---

## Relationship Between Components

```
Specification (.el file)
        │
        ▼
   el_parser.py  ──► el_validator.py (15 structural rules)
        │                    │
        │            errors or clean
        │
        ▼
   parsed model
        │
        ├──► el_reasoner.py  ──► ultimate_accountability()
        │                    ──► can_perform()
        │                    ──► policy_conflicts()
        │
        ├──► el_kripke.py    ──► build_kripke_model()
        │                    ──► check_obligation()   [AF φ]
        │                    ──► check_permission()   [EF φ]
        │                    ──► ranked_reachable()   [utility §C.3/C.4]
        │
        └──► Sepanosian's runtime engine (separate toolchain)
             ──► WorldState transitions
             ──► Deontic enforcement at runtime
             ──► Append-only ledger
             ──► (optional: ledger anchors el_kripke.py initial world)
```

**Key distinction:**
- Validator: *Is this specification internally consistent?*
- Reasoner: *Given consistency, what can we conclude about accountability?*
- Kripke (el_kripke.py): *Across all possible futures, will obligation O inevitably discharge?*
- Sepanosian's engine: *Given a valid specification, what happened when executed?*

---

## Position in the Four-Layer Stack

```
Layer 1 — computable-governance grammar (Igor Dejanovic)
          Core ODP-EL concepts: community, role, deontic token, policy
          Q: What is the governance structure?

Layer 2 — THIS TOOLCHAIN (el_grammar.tx + el_validator.py + el_reasoner.py)
          Structural governance and accountability tracing
          Q: Who is accountable for obligation O through the chain?

Layer 3 — Sepanosian runtime engine
          Operational execution: WorldState, transitions, ledger
          Q: What happened, and was each step permitted?
          Repos: github.com/Thomas-mp4/ODP-EL-textX
                 github.com/Thomas-mp4/ODP-EL-Toolchain

Layer 4 — el_kripke.py (implemented May 2026)
          Kripke semantics (Annex C of ISO/IEC 15414:2015)
          AF φ (obligation), EF φ (permission), AG φ (invariant), utility §C.3/C.4
          Q: Across all possible futures, will obligation O
             eventually be discharged?
```

---

## The Kripke Verifier (`el_kripke.py`)

### What it does

Implements **all four sections of Annex C of ISO/IEC 15414:2015** as Layer 4
of the ComputableGovernance stack. Builds a finite Kripke model M = (W, R, V, w₀)
from a parsed DSL-EL spec and provides verification, utility scoring, and
action recommendation over it.

This is believed to be the first complete implementation of Annex C in a
working toolchain connected to a real ODP-EL grammar and parser.

### Reachability relation R

R is built **from the DSL-EL delegation structure alone** — obligations,
deadlines, and actor assignments generate the full branching tree of possible
futures. Three transition rules expand the model from the initial world:
- **T1 DISCHARGE** — active holder performs the obligated action → DISCHARGED
- **T2 VIOLATION** — deadline steps elapsed, obligation still PENDING → VIOLATED
- **T3 TICK**      — time passes (suppressed if any strict obligation is pending
                     and its holder is active)

An optional **hybrid mode** (not yet implemented) allows a Sepanosian Layer 3
ledger to anchor the initial world and prune unreachable branches.

### Modal operators (§C.2)

| Operator | CTL | Meaning | Used for |
|----------|-----|---------|----------|
| `AF φ` | Along all paths, Finally φ | φ on every possible future eventually | Obligation verification |
| `EF φ` | there Exists a path, Finally φ | φ on some possible future | Permission verification |
| `AG φ` | Along all paths, Generally φ | φ in every reachable world | Invariant checking |

### Utility function (§C.3)

`utility(world)` is a **priority-weighted average** over obligation outcomes:

```
utility(w) = Σ(score_i × weight_i) / Σ(weight_i)
```

Outcome scores: DISCHARGED=+1.0, PENDING=+0.3, EXPIRED=0.0, VIOLATED=-1.0.

Priority weights from AM-15 `PriorityLevel` on `DeonticTokenDecl`:
- `critical`=1.00, `high`=0.75, `normal`=0.50 (default), `low`=0.25

Result normalised to [-1, +1]. Priority weighting means a violated critical
obligation dominates even when all low-priority obligations are discharged.

### BDI recommender (§C.4)

`expected_future_utility(world)` — mean utility over all worlds reachable
from w; captures long-run quality of a choice, not just the immediate outcome.

`recommend_action(world)` — ranks all available transitions by expected future
utility. Rank 1 is the advised action. This is the BDI connection:
- Beliefs  = current world
- Desires  = priority-weighted utility function
- Intention = rank-1 recommended action

`walk_recommended_path()` / `render_recommended_path()` — follows the greedy
best-action sequence from the initial world, showing alternatives at each step.

### DSL grammar additions (AM-13, AM-15)

```
burden seekConsentObligation {
    state: active
    deadline: "clinical session"
    discharge_mode: strict     ← AM-13: AF holds by construction
    priority: critical         ← AM-15: feeds weighted utility
}
```

### Key finding (consent scenario — two obligations)

```
[seekConsentObligation]  priority=critical  mode=strict    AF=✓  EF=✓
[reportingObligation]    priority=low       mode=eventual  AF=✗  EF=✓
```

Recommender output from initial world:
```
Step 1: ★ discharge:seekConsentObligation by AIDiagnosticAgent  (EFU=+0.870)
        Alternative: discharge:reportingObligation by GPPracticeParty (EFU=+0.720)
Step 2: ★ discharge:reportingObligation by GPPracticeParty  (EFU=+1.000)
Final:  both discharged, utility=+1.000
```

The recommender derived "consent first" from the DSL structure and priority
weights alone — not from any hard-coded ordering rule.

### Usage

```python
from el_parser import parse
from el_kripke import build_kripke_model

result = parse("consent_scenario.el")
km     = build_kripke_model(result.model, horizon=10)

print(km.render_summary())

# §C.2 — modal verification
print(km.check_obligation("seekConsentObligation").render())
print(km.check_permission("seekConsentObligation").render())

# §C.3 — utility-ranked worlds
for world, score in km.ranked_reachable(km.initial):
    print(f"  utility={score:+.3f}  {world.obligation_dict()}")

# §C.4 — BDI action recommendation
print(km.render_recommended_path())
```

### Standalone test (no parser required)

```bash
python el_kripke.py    # runs synthetic consent scenario (§C.2 only)
```

---

## Known Limitations and Open Issues

**Validator:**
- V-03 uses items*=StepBodyItem structure; checks ActorRef in items list
- V-15 checks obligation text against CommitmentDecl only (not mid-chain);
  this is intentional but means obligations that enter only via delegation
  (no explicit commitment) will trigger the rule

**Reasoner:**
- `can_perform()` is static only — does not model runtime token changes
- Delegation chain walk is depth-first, follows first matching link;
  multiple parallel chains are each returned as separate AccountabilityChain
- `policy_conflicts()` uses simple obligation/prohibition text matching;
  does not handle semantic equivalence of differently-worded rules

**Grammar (known textX/arpeggio issues):**
- FederationDecl uses per-line `member:` declarations (not comma list)
  due to arpeggio cross-reference list resolution bug
- DomainDecl uses `controlled_object:` per line for same reason
- Boolean flags use `key: true` style (absence = false); `key: false`
  is not valid syntax — simply omit the flag

---

## CLI Quick Reference

```bash
# Parse and validate a specification
python el_parser.py my_spec.el

# Trace accountability chain
python el_reasoner.py my_spec.el "obligation text here"

# Detect policy conflicts
python el_reasoner.py my_spec.el --policy-conflicts

# Run Kripke modal verification (Layer 4 — full Annex C)
python el_kripke.py                        # synthetic consent scenario (standalone)

# In Python — full Layer 4 pipeline
# from el_parser import parse
# from el_kripke import build_kripke_model
# km = build_kripke_model(parse("consent_scenario.el").model)
# km.check_obligation("seekConsentObligation").render()   # §C.2 AF
# km.ranked_reachable(km.initial)                         # §C.3 utility
# km.render_recommended_path()                            # §C.4 BDI planner

# Run the worked example
python el_parser.py example.el
python el_reasoner.py example.el "Process all customer payments within SLA"
```

---

## Dependencies

```bash
pip install textX   # version 4.3.0 confirmed working
```

No other dependencies beyond the Python standard library.
