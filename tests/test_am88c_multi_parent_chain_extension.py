"""
Layer 4 — AM-88c: `el_kripke.py`'s `_delegation_chain_for_token()` final
chain-extension loop learns to pick the RIGHT principal_of parent for a
Commitment-rooted token, closing the residual AM-88b deliberately left
open.

Problem AM-88b left behind: its BFS reachability fix made the AM-52 guard
correctly *trust* a token_group transfer regardless of declaration order,
but the function's separate final chain-extension loop still picked
whichever of an agent's multiple principal_of parents was declared first
in the file (the pre-existing, single-valued `structural_parent` map,
untouched by AM-88b by design). For GuardProbe (`P1`/`P2` both
`principal_of AgentA`; `P2` is the real Commitment actor for `burdenT`),
that meant: declare `P1` first and the exported chain became
`['P1', 'AgentA', 'AgentB']` — a full-length, structurally "valid-looking"
chain naming the WRONG root. That is worse than AM-88b's own pre-fix
symptom (a visibly truncated `['AgentB']`), because a full-length chain
with a plausible-looking root gives no signal that anything is wrong.

Fix: when an agent has more than one `principal_of` parent AND the token
has its own Commitment, the loop now prefers the parent that either IS the
Commitment's actor, or from which that actor is reachable (via the same
BFS the AM-52 guard already uses), breaking ties via `sorted()` for
determinism. A token with NO Commitment of its own has no actor to prefer
against — for that case the pre-AM-88c first-declared-wins behaviour is
UNCHANGED and REMAINS order-dependent; a future validator warning for a
genuinely ambiguous multi-parent join is the honest fix there, not a
default resolution rule (see `docs/CONCEPTS_INDEX.md`, AM-88).

Regression: byte-identical against the AM-88b snapshot (no existing
scenario has an agent with more than one principal_of parent, so nothing
changes for the real corpus).
"""
import json
import os

import pytest

from el_engine import _build_obligation_descriptors, grant_token, token_from_spec
from el_kripke import _delegation_chain_for_token, build_kripke_from_runtime
from el_parser import parse, parse_string
from el_runtime import Runtime


_SNAPSHOT_PATH = "tests/fixtures/am88b_delegation_chain_for_token_snapshot.json"


def test_delegation_chain_for_token_still_byte_identical_to_am88b_snapshot():
    """AM-88c only changes behaviour for an agent with more than one
    principal_of parent AND a Commitment-rooted token reaching it — no
    scenario in the corpus has that shape, so nothing changes here.

    Iterates the snapshot's own file/token list rather than globbing
    scenarios/**/*.el — see tests/test_am88a_multi_parent_tracing.py's
    identical fix for why: some local development checkouts have
    additional, untracked scenario files a public clone never has."""
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
def test_guardprobe_full_chain_is_order_independent_direct(order_swapped):
    """Pre-AM-88c, order_swapped=False (P1 declared before P2) gave the
    wrong-but-full-length ['P1', 'AgentA', 'AgentB'] — P1 has nothing to do
    with burdenT's Commitment. Fixed: the loop now prefers P2 (the actual
    Commitment actor) regardless of declaration order."""
    result = parse_string(_guard_probe(order_swapped), validate=False)
    assert result.ok, result.errors
    chain = _delegation_chain_for_token(result.model, "burdenT", "AgentB")
    assert chain == ["P2", "AgentA", "AgentB"]


@pytest.mark.parametrize("order_swapped", [False, True])
def test_guardprobe_full_chain_is_order_independent_hybrid(order_swapped):
    """Same fix, reached through build_kripke_from_runtime() (hybrid
    mode), which calls _delegation_chain_for_token() directly for every
    live burden token."""
    result = parse_string(_guard_probe(order_swapped), validate=False)
    assert result.ok, result.errors

    rt = Runtime.build_from_spec(result.model)
    state = rt.current_state()
    state = grant_token(state, token_from_spec(result.model, "burdenT", "AgentB", state.tick))
    rt._state = state

    km = build_kripke_from_runtime(rt, horizon=10)
    desc = km.obligation_descriptors["burdenT"]
    assert desc.holder == "AgentB"
    assert desc.chain == ["P2", "AgentA", "AgentB"]


# ── Documented residual: a multi-principal token with NO Commitment ────────

def _no_commitment_probe(order_swapped):
    p1 = "party P1 { principal_of AgentA }"
    p2 = "party P2 { principal_of AgentA }"
    parties = (p2, p1) if order_swapped else (p1, p2)
    return f"""
enterprise specification NoCommitmentMultiParentProbe
{parties[0]}
{parties[1]}
agent AgentA
agent AgentB

permit facilitatePermit {{
    state: active
}}

burden burdenNoCommit {{
    state: active
}}

token_group grpNC {{
    member: burdenNoCommit
}}

authorization authNC {{
    authority: P1
    grants_permit: facilitatePermit
    creates_burden_on_authority: burdenNoCommit
}}

delegation grpDel {{
    from: AgentA
    to: AgentB
    obligation: "Handle onward"
    transfers_token_group: grpNC
}}
"""


def test_no_commitment_multi_parent_token_remains_order_dependent():
    """AM-88c deliberately does NOT resolve this case: burdenNoCommit is
    rooted at Authorization.auth_burden (P1), not a Commitment, so
    _commitment_root_for_token() returns None for it and the loop has no
    actor to prefer against — it falls back to the pre-AM-88c
    first-declared-wins structural_parent map, unchanged. The chain
    genuinely still depends on declaration order here, which is why this
    is documented as an OPEN residual in docs/CONCEPTS_INDEX.md (AM-88)
    rather than silently resolved: with no Commitment to anchor against,
    picking a default parent would be a guess, not a fix. A future
    validator warning for a genuinely ambiguous multi-principal_of join is
    the honest next step, not a default resolution rule here."""
    result_first = parse_string(_no_commitment_probe(order_swapped=False), validate=False)
    result_second = parse_string(_no_commitment_probe(order_swapped=True), validate=False)
    assert result_first.ok and result_second.ok

    chain_p1_first = _delegation_chain_for_token(result_first.model, "burdenNoCommit", "AgentB")
    chain_p2_first = _delegation_chain_for_token(result_second.model, "burdenNoCommit", "AgentB")

    assert chain_p1_first == ["P1", "AgentA", "AgentB"]
    assert chain_p2_first == ["P2", "AgentA", "AgentB"]
    assert chain_p1_first != chain_p2_first
