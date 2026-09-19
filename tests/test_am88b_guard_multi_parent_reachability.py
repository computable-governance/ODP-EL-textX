"""
Layer 4 — AM-88b: `el_kripke.py`'s `_delegation_chain_for_token()` AM-52
guard becomes a multi-parent search, and the function switches to
`el_engine.py`'s `_commitment_root_for_token()` (AM-88a) instead of keeping
its own copy.

Problem: the guard's reachability check ("is this Delegation's delegator
reachable from the token's Commitment actor via principal_of structural
edges?") chased a single pointer through `structural_parent`, a dict built
with `setdefault` — when one agent had TWO `principal_of` parents, only the
first-declared one was ever considered. Whether the guard trusted a
`transfers_token_group` match at all — and therefore whether the whole
chain extended past that agent — silently depended on which of the two
parties happened to be declared first in the file.

Repro (GuardProbe, `docs/CONCEPTS_INDEX.md`, AM-88): `P1`/`P2` are both
`principal_of AgentA`; only `P2` has the Commitment for `burdenT`, which
`AgentA` transfers onward to `AgentB` via `transfers_token_group`. Pre-fix:
`_delegation_chain_for_token(model, "burdenT", "AgentB")` gave `['AgentB']`
(guard wrongly rejected the match) when `P1` was declared before `P2`, and
the correct `['P2', 'AgentA', 'AgentB']` when declared the other way round.

Fix: `structural_parents_multi` (every `principal_of` parent per agent) plus
a BFS `_reachable()` over it, replacing the single-pointer version. The
pre-existing, separate, single-valued `structural_parent` map used by this
same function's own *final chain-extension* loop is unchanged — which
principal the *exported* chain continues through when an agent has more
than one is a narrower, out-of-scope limitation (`docs/CONCEPTS_INDEX.md`),
not something this fix touches. So GuardProbe's chain is now correctly
length 3 in BOTH declaration orders (the bug this amendment fixes), even
though which of P1/P2 appears as chain[0] still depends on declaration
order (the separate, still-open limitation) — the tests below assert
exactly that combination, not full chain equality across orders.

Regression: every existing scenario's `_delegation_chain_for_token()`
output is pinned against a pre-fix snapshot
(tests/fixtures/am88b_delegation_chain_for_token_snapshot.json) — zero
diffs, confirming this is a pure bug fix with no behavioural change to any
existing scenario (none exercises the two-`principal_of`-parents case).
"""
import json
import os

import pytest

from el_engine import _build_obligation_descriptors, grant_token, token_from_spec
from el_kripke import _delegation_chain_for_token, build_kripke_from_runtime
from el_parser import parse, parse_string
from el_runtime import Runtime


_SNAPSHOT_PATH = "tests/fixtures/am88b_delegation_chain_for_token_snapshot.json"


# ── Byte-identical regression over the full corpus ─────────────────────────

def test_delegation_chain_for_token_byte_identical_to_pre_fix_snapshot():
    """Every (scenario, token) pair listed in the snapshot, compared
    against the pre-AM-88b chain. Confirms the multi-map reachability
    rewrite changes nothing for any existing scenario.

    Iterates the snapshot's own file/token list rather than globbing
    scenarios/**/*.el and re-deriving tokens from live descriptors — see
    tests/test_am88a_multi_parent_tracing.py's identical fix for why: some
    local development checkouts have additional, untracked scenario files
    a public clone never has, and a glob-based count would pass locally but
    fail on a clean clone."""
    with open(_SNAPSHOT_PATH) as fh:
        snapshot = json.load(fh)

    expected_total = sum(len(tokens) for tokens in snapshot.values())
    checked = 0
    for f in sorted(snapshot):
        assert os.path.exists(f), f"snapshot references missing file {f}"
        result = parse(f, validate=False)
        assert result.model is not None, f"failed to parse {f}: {result.errors}"
        descriptors = _build_obligation_descriptors(result.model)
        for token_name in sorted(snapshot[f]):
            assert token_name in descriptors, f"no descriptor for {f}::{token_name}"
            result2 = parse(f, validate=False)
            chain = _delegation_chain_for_token(result2.model, token_name, descriptors[token_name].holder)
            assert chain == snapshot[f][token_name], f"chain mismatch for {f}::{token_name}"
            checked += 1

    assert checked == expected_total


# ── GuardProbe — the multi-parent reachability fix ─────────────────────────

def _guard_probe(order_swapped):
    p1 = "party P1 { principal_of AgentA }"
    p2 = "party P2 { principal_of AgentA }"
    parties = (p2, p1) if order_swapped else (p1, p2)
    return f"""
enterprise specification GuardProbe
{parties[0]}
{parties[1]}
agent AgentA
agent AgentB

burden burdenT {{ state: active }}
burden burdenU {{ state: active }}

token_group grpTU {{
    member: burdenT
    member: burdenU
}}

commitment cT {{ by: P2 obligation: "Handle referral" creates_burden: burdenT }}

delegation grpDel {{ from: AgentA to: AgentB obligation: "Handle referral onward" transfers_token_group: grpTU }}
"""


@pytest.mark.parametrize("order_swapped", [False, True])
def test_guardprobe_reachability_guard_is_order_independent(order_swapped):
    """Pre-fix, order_swapped=False (P1 declared before P2) gave chain
    ['AgentB'] — the guard rejected the transfer entirely because AgentA's
    single-pointer structural_parent happened to point at P1, not P2, so
    reachability to P2 (the real Commitment actor) failed. Fixed: the guard
    now searches all of AgentA's principal_of parents, so it correctly
    finds P2 and trusts the transfer in both declaration orders.

    chain[0] itself (P1 vs P2) is NOT asserted to be order-independent —
    that is the separate, deliberately out-of-scope final-chain-extension
    limitation (see module docstring and docs/CONCEPTS_INDEX.md)."""
    result = parse_string(_guard_probe(order_swapped), validate=False)
    assert result.ok, result.errors

    chain = _delegation_chain_for_token(result.model, "burdenT", "AgentB")
    assert len(chain) == 3
    assert chain[0] in ("P1", "P2")
    assert chain[1:] == ["AgentA", "AgentB"]


def test_guardprobe_reachability_guard_finds_correct_root_when_declared_first():
    """Direct positive check (not just length/shape): when the real
    Commitment actor (P2) is declared before the unrelated principal (P1),
    the chain resolves to the fully correct, expected root."""
    result = parse_string(_guard_probe(order_swapped=True), validate=False)
    assert result.ok, result.errors
    chain = _delegation_chain_for_token(result.model, "burdenT", "AgentB")
    assert chain == ["P2", "AgentA", "AgentB"]


@pytest.mark.parametrize("order_swapped", [False, True])
def test_guardprobe_hybrid_mode_chain_is_order_independent(order_swapped):
    """Same guard fix, reached via build_kripke_from_runtime() (hybrid
    mode), which calls _delegation_chain_for_token() directly
    (el_kripke.py:2903 area) for every live burden token. burdenT is
    granted directly to AgentB here (no root construct grants it via
    holds_tokens), mirroring the recon verification done for this probe."""
    result = parse_string(_guard_probe(order_swapped), validate=False)
    assert result.ok, result.errors

    rt = Runtime.build_from_spec(result.model)
    state = rt.current_state()
    state = grant_token(state, token_from_spec(result.model, "burdenT", "AgentB", state.tick))
    rt._state = state

    km = build_kripke_from_runtime(rt, horizon=10)
    desc = km.obligation_descriptors["burdenT"]
    assert desc.holder == "AgentB"
    assert len(desc.chain) == 3
    assert desc.chain[0] in ("P1", "P2")
    assert desc.chain[1:] == ["AgentA", "AgentB"]
