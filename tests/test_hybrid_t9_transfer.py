"""
Layer 4 — hybrid-mode Rule T9 (Transfer), AM-82 (2026-09-14).

Formal-verification counterpart to the already-live `transfer`
DeonticEffect (el_engine.py, `elif op == "transfer":`) — Layer 3 is
untouched by this amendment; this is purely additive to el_kripke.py,
same spirit as T7/T8's port of already-live engine behavior (AM-79).

Scoped narrowly: Burden-kind tokens only (Permit/Embargo transfers are
out of scope — their per-world state tracks activity, not holder
identity). Single-source, single-target only: a `transfer` DeonticEffect
is included only when BOTH `from_role` and `to_role` resolve to exactly
one actor via current role membership; a `transfer` with no `from_role`
at all is skipped entirely (no live acting-actor to fall back on, unlike
el_engine.py's own `eff.from_role or actor_name`). Hybrid mode only
(`build_kripke_from_runtime()`) — `build_kripke_model()` is untouched,
same convention as T4/T7/T8.

There is zero live usage of `effect transfer` anywhere in
referral_scenario.el (confirmed: `grep -n "effect.*transfer"` returns
nothing there), so this file exercises T9 against a dedicated synthetic
probe instead: scenarios/probes/transfer_probe.el. That probe covers the
happy path plus every T9 skip case in one file — see its own header
comment for the full layout. Role membership (which actor fills which
role) has no grammar construct in this DSL at all (see the probe's own
comment, DOC-03) — it is assigned here in Python via
el_engine.enroll(state, actor_name, role_name=...), the same pattern
el_api.py's own scenario builders use.
"""
from pathlib import Path

from el_engine import discharge_burden, enroll
from el_kripke import build_kripke_from_runtime
from el_parser import parse
from el_runtime import Runtime

_PROBE = Path(__file__).resolve().parent.parent / "scenarios" / "probes" / "transfer_probe.el"


def _build_probe_runtime(discharge_strict: bool = True) -> Runtime:
    """Parses transfer_probe.el, enrolls role membership (ActorA/roleA,
    ActorB/roleB, ActorC+ActorD/roleC — deliberately two fillers, proving
    the ambiguous-from_role skip case; roleUnfilled gets nobody, proving
    the zero-actors skip case), and by default discharges strictBurden
    first so the strict-burden guard doesn't mask every other test.
    Pass discharge_strict=False for the guard test itself.
    """
    result = parse(_PROBE, validate=True)
    assert result.ok, result.errors
    model = result.model

    rt = Runtime.build_from_spec(model)
    state = rt.current_state()
    state = enroll(state, "ActorA", role_name="roleA")
    state = enroll(state, "ActorB", role_name="roleB")
    state = enroll(state, "ActorC", role_name="roleC")
    state = enroll(state, "ActorD", role_name="roleC")  # roleC: TWO fillers, deliberately
    # roleUnfilled: nobody enrolled, deliberately

    if discharge_strict:
        state, record = discharge_burden(state, model, "strictBurden")
        assert record.outcome == "ok"

    return Runtime(state, model)


def _edges_from(km, w):
    return {km.labels[(w, w2)] for w2 in km.edges.get(w, set())}


# ── Happy path ───────────────────────────────────────────────────────────────

def test_t9_transfer_edge_present_and_reassigns_holder():
    rt = _build_probe_runtime()
    km = build_kripke_from_runtime(rt, horizon=5)
    w0 = km.initial

    w0_edges = _edges_from(km, w0)
    assert "transfer:probeBurden via performTransfer (ActorA→ActorB)" in w0_edges

    w_transferred = next(
        w for w in km.edges[w0]
        if km.labels[(w0, w)] == "transfer:probeBurden via performTransfer (ActorA→ActorB)"
    )
    assert w_transferred.get_holder_override("probeBurden") == "ActorB"
    assert w_transferred.has_occurred("performTransfer")


def test_t9_rewires_t1_discharge_label_to_the_transferred_holder():
    rt = _build_probe_runtime()
    km = build_kripke_from_runtime(rt, horizon=5)
    w0 = km.initial

    w0_edges = _edges_from(km, w0)
    assert "discharge:probeBurden by ActorA" in w0_edges

    w_transferred = next(
        w for w in km.edges[w0]
        if km.labels[(w0, w)].startswith("transfer:probeBurden")
    )
    post_edges = _edges_from(km, w_transferred)
    assert "discharge:probeBurden by ActorB" in post_edges
    assert "discharge:probeBurden by ActorA" not in post_edges

    # No self-loop: the same transfer can't fire twice from the world it produced.
    assert not any(l.startswith("transfer:probeBurden") for l in post_edges)


# ── Skip cases ───────────────────────────────────────────────────────────────

def test_t9_skips_transfer_effect_with_no_from_role():
    rt = _build_probe_runtime()
    km = build_kripke_from_runtime(rt, horizon=5)
    w0 = km.initial
    edges = _edges_from(km, w0)
    assert not any("noFromRoleBurden" in l and l.startswith("transfer:") for l in edges)


def test_t9_skips_transfer_effect_with_ambiguous_from_role():
    """roleC is filled by both ActorC and ActorD — from_role does not
    resolve to exactly one actor."""
    rt = _build_probe_runtime()
    km = build_kripke_from_runtime(rt, horizon=5)
    w0 = km.initial
    edges = _edges_from(km, w0)
    assert not any("ambiguousFromBurden" in l and l.startswith("transfer:") for l in edges)


def test_t9_skips_transfer_effect_with_unfilled_to_role():
    """roleUnfilled has zero fillers — to_role does not resolve to
    exactly one actor."""
    rt = _build_probe_runtime()
    km = build_kripke_from_runtime(rt, horizon=5)
    w0 = km.initial
    edges = _edges_from(km, w0)
    assert not any("unfilledToBurden" in l and l.startswith("transfer:") for l in edges)


def test_t9_skips_permit_kind_transfer_effect():
    """probePermit is a Permit, not a Burden — out of scope for T9."""
    rt = _build_probe_runtime()
    km = build_kripke_from_runtime(rt, horizon=5)
    w0 = km.initial
    edges = _edges_from(km, w0)
    assert not any("probePermit" in l and l.startswith("transfer:") for l in edges)


# ── Strict-burden guard ───────────────────────────────────────────────────────

def test_t9_absent_from_w0_while_strict_burden_outstanding():
    """Mirrors T4/T7/T8's own guard test: strictBurden (discharge_mode:
    strict) is PENDING and ActorA ACTIVE by construction — no transfer:
    edge may appear from w0 at all while it's outstanding."""
    rt = _build_probe_runtime(discharge_strict=False)
    km = build_kripke_from_runtime(rt, horizon=5)
    w0 = km.initial
    edges = _edges_from(km, w0)
    assert not any(l.startswith("transfer:") for l in edges)


def test_t9_transfer_edge_present_once_strict_burden_clears():
    rt = _build_probe_runtime(discharge_strict=True)
    km = build_kripke_from_runtime(rt, horizon=5)
    w0 = km.initial
    edges = _edges_from(km, w0)
    assert any(l.startswith("transfer:probeBurden") for l in edges)
