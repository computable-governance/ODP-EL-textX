"""
Layer 2 — AM-94: `[W-16f]` — an Action requires part of a set of
co-granted permits and leaves a granting authority unconsulted.

Substitution failure on the permit side: an agent (or role) is authorized
by two distinct authorities, each granting its own permit, and an Action
requires only one authority's permit — so the other authority is never
consulted, and the Action still runs if that authority's authorization is
revoked. Composition is application-defined; the toolchain only flags the
omission. Advisory, never an error (AM-89 warnings channel).

Co-granted set (`el_reasoner.co_granted_permit_sets`): Authorizations with
the same TARGET (a to_agent name, or a to_role name — separate
namespaces) and the same NON-EMPTY domain_scope (trimmed, case-
insensitive), from >=2 DISTINCT authorities. A warning is one per
(action, set) and fires only when the Action requires >=1 permit of the
set AND some authority of the set has NONE of its permits (within the
set) required by that Action (authority-based, not "any permit missing").

Scope: role Action bodies only (Community / Domain / Federation roles).
ConditionalAction is deliberately not covered — nothing reads its
requires_permit, so "add the missing requires_permit" would change
nothing (open finding in docs/CONCEPTS_INDEX.md). Permits obtained by
role `holds` are not Authorizations and never form a set.

Inline specs, or NAMED tracked scenario files, only.
"""
import itertools
import re

import pytest

from el_kripke import _build_permit_requirement_index
from el_parser import parse, parse_string
from el_reasoner import (
    co_granted_permit_sets,
    permit_omissions,
    required_permits_by_action,
)

HAND_OFF = (
    "If every listed authority must approve this action, add the missing "
    "requires_permit; if any one suffices, this is intended. How these "
    "authorities combine is application-defined; the toolchain does not "
    "compose them."
)

A1 = ("a1", "Auth1", "to_agent", "Ag", "P1", "S")
A2 = ("a2", "Auth2", "to_agent", "Ag", "P2", "S")
A3 = ("a3", "Auth3", "to_agent", "Ag", "P3", "S")


def _spec(auths, actions, role_holds=(), cond=()):
    """auths: (name, authority, 'to_agent'|'to_role', target, permit, scope|None)
    actions: [(name, [required permits])] in ONE role 'R' of community 'C'.
    role_holds: permits the role holds. cond: ConditionalActions (name, [permits])."""
    lines = ["enterprise specification P94"]
    lines += [f"party Auth{i}" for i in (1, 2, 3)]
    lines += ["agent Ag", "agent Other"]
    lines += [f"permit P{i} {{ state: active }}" for i in (1, 2, 3)]
    body = [f"        holds {p}" for p in role_holds]
    for n, ps in actions:
        reqs = "\n".join(f"            requires_permit {p}" for p in ps)
        body.append(f"        action {n} {{\n            actor: R\n{reqs}\n        }}")
    for n, ps in cond:
        reqs = "\n".join(f"            requires_permit {p}" for p in ps)
        body.append(f"        conditional_action {n} {{\n{reqs}\n        }}")
    lines.append(
        'community C {\n    objective: "o"\n    role R\n        description: "r"\n    {\n'
        + "\n".join(body) + "\n    }\n}"
    )
    for n, auth, kw, tgt, permit, scope in auths:
        sc = f'\n    domain_scope: "{scope}"' if scope is not None else ""
        lines.append(
            f"authorization {n} {{\n    authority: {auth}\n    {kw}: {tgt}\n"
            f"    grants_permit: {permit}{sc}\n}}"
        )
    return "\n".join(lines)


def _w16f(auths, actions, **kw):
    result = parse_string(_spec(auths, actions, **kw), validate=True)
    assert result.ok, result.errors
    return result, [w for w in result.warnings if w.startswith("[W-16f]")]


# ── the basic shape, exact wording, and .ok ───────────────────────────────

def test_requires_only_p1_warns_naming_auth2_and_its_authorization():
    result, w = _w16f([A1, A2], [("act", ["P1"])])
    assert w == [
        "[W-16f] Action 'act' (role 'R', community 'C') requires 'P1' from the "
        "permits co-granted to agent 'Ag' in domain_scope 'S' by 2 distinct "
        "authorities (Auth1, Auth2). Not consulted: authority 'Auth2' "
        "(Authorization 'a2': permit 'P2'). " + HAND_OFF
    ]
    assert result.ok is True              # warnings never affect .ok


def test_requires_only_p2_warns_naming_auth1():
    _, w = _w16f([A1, A2], [("act", ["P2"])])
    assert len(w) == 1
    assert "Not consulted: authority 'Auth1' (Authorization 'a1': permit 'P1')." in w[0]


def test_requires_both_or_neither_no_warning():
    assert _w16f([A1, A2], [("act", ["P1", "P2"])])[1] == []
    assert _w16f([A1, A2], [("act", ["P3"])])[1] == []


def test_different_or_missing_domain_scope_never_joins_a_set():
    assert _w16f([A1, ("a2", "Auth2", "to_agent", "Ag", "P2", "T")], [("act", ["P1"])])[1] == []
    assert _w16f([A1, ("a2", "Auth2", "to_agent", "Ag", "P2", None)], [("act", ["P1"])])[1] == []
    assert _w16f([A1, ("a2", "Auth2", "to_agent", "Ag", "P2", "   ")], [("act", ["P1"])])[1] == []


def test_scope_variants_differing_only_in_case_and_whitespace_are_grouped():
    result, w = _w16f([A1, ("a2", "Auth2", "to_agent", "Ag", "P2", "  s ")], [("act", ["P1"])])
    assert len(w) == 1
    # display uses the smallest trimmed spelling actually declared
    assert "in domain_scope 'S' by 2 distinct authorities" in w[0]


def test_one_authority_granting_two_permits_is_not_two_authorities():
    auths = [A1, ("a2", "Auth1", "to_agent", "Ag", "P2", "S")]
    assert _w16f(auths, [("act", ["P1"])])[1] == []
    assert co_granted_permit_sets(_w16f(auths, [("act", ["P1"])])[0].model) == []


# ── to_role, and the two namespaces ───────────────────────────────────────

def test_to_role_variant_warns():
    auths = [("a1", "Auth1", "to_role", "RoleX", "P1", "S"),
             ("a2", "Auth2", "to_role", "RoleX", "P2", "S")]
    _, w = _w16f(auths, [("act", ["P1"])])
    assert len(w) == 1
    assert "co-granted to role 'RoleX'" in w[0]


def test_to_agent_and_to_role_with_the_same_name_are_not_conflated():
    auths = [A1, ("a2", "Auth2", "to_role", "Ag", "P2", "S")]      # agent 'Ag' vs role 'Ag'
    assert _w16f(auths, [("act", ["P1"])])[1] == []


# ── authority-based omission ─────────────────────────────────────────────

def test_three_authorities_action_requires_two_names_the_one_omitted():
    _, w = _w16f([A1, A2, A3], [("act", ["P1", "P2"])])
    assert len(w) == 1
    assert "requires 'P1', 'P2'" in w[0]
    assert "by 3 distinct authorities (Auth1, Auth2, Auth3)" in w[0]
    assert "Not consulted: authority 'Auth3' (Authorization 'a3': permit 'P3')." in w[0]


_TWO_PERMITS_ONE_AUTHORITY = [
    ("a1", "Auth1", "to_agent", "Ag", "P1", "S"),
    ("a2", "Auth1", "to_agent", "Ag", "P2", "S"),     # Auth1 grants P1 + P2
    ("a3", "Auth2", "to_agent", "Ag", "P3", "S"),     # Auth2 grants P3
]


def test_action_requiring_one_permit_of_each_authority_is_not_flagged():
    """Auth1 grants P1+P2, Auth2 grants P3; requires P1+P3 -> both consulted."""
    assert _w16f(_TWO_PERMITS_ONE_AUTHORITY, [("act", ["P1", "P3"])])[1] == []


@pytest.mark.parametrize("required", [["P1"], ["P1", "P2"]])
def test_action_leaving_auth2_unconsulted_names_auth2_and_p3(required):
    """Requires only P1, or P1+P2 (both Auth1's): Auth2 (P3) is never consulted.
    Auth1's OTHER permit being unrequired is not, by itself, a reason to warn."""
    _, w = _w16f(_TWO_PERMITS_ONE_AUTHORITY, [("act", required)])
    assert len(w) == 1
    assert "Not consulted: authority 'Auth2' (Authorization 'a3': permit 'P3')." in w[0]
    assert "authority 'Auth1'" not in w[0].split("Not consulted:")[1]


def test_an_omitted_authority_lists_every_grant_it_made_in_the_set():
    auths = [A1,
             ("a2", "Auth2", "to_agent", "Ag", "P2", "S"),
             ("a3", "Auth2", "to_agent", "Ag", "P3", "S")]
    _, w = _w16f(auths, [("act", ["P1"])])
    assert len(w) == 1
    assert ("Not consulted: authority 'Auth2' (Authorization 'a2': permit 'P2'; "
            "Authorization 'a3': permit 'P3').") in w[0]


def test_an_authority_is_consulted_if_it_granted_the_required_permit_too():
    """P1 granted by BOTH authorities (plus P2 by Auth2): requiring P1
    consults both — nothing is omitted."""
    auths = [A1,
             ("a2", "Auth2", "to_agent", "Ag", "P1", "S"),
             ("a3", "Auth2", "to_agent", "Ag", "P2", "S")]
    assert _w16f(auths, [("act", ["P1"])])[1] == []


# ── scope boundaries (documented) ─────────────────────────────────────────

def test_conditional_action_is_not_covered():
    """Documented exclusion: ConditionalAction.requires_permits is read by
    nothing, so advising 'add the missing requires_permit' would change
    nothing. See the open finding in docs/CONCEPTS_INDEX.md."""
    result = parse_string(_spec([A1, A2], [], cond=[("cact", ["P1"])]), validate=True)
    assert result.ok, result.errors
    assert [w for w in result.warnings if w.startswith("[W-16f]")] == []
    assert required_permits_by_action(result.model) == []


def test_permit_obtained_only_via_role_holds_is_not_covered():
    """Documented gap: `holds` is not an Authorization, so it never forms a
    co-granted set — even when the Action's other permit comes from one."""
    _, w = _w16f([A1], [("act", ["P1"])], role_holds=["P2"])
    assert w == []


def test_same_named_actions_in_different_roles_stay_separate_records():
    txt = _spec([A1, A2], [("act", ["P1"])]).replace(
        "    }\n}\nauthorization a1",
        '    }\n    role S2\n        description: "s"\n    {\n'
        "        action act {\n            actor: S2\n            requires_permit P2\n        }\n    }\n}\n"
        "authorization a1", 1)
    result = parse_string(txt, validate=True)
    assert result.ok, result.errors
    reqs = required_permits_by_action(result.model)
    assert [(r.role, r.name, r.permits) for r in reqs] == [("R", "act", ("P1",)), ("S2", "act", ("P2",))]
    assert len([w for w in result.warnings if w.startswith("[W-16f]")]) == 2


# ── determinism ───────────────────────────────────────────────────────────

def test_order_invariant_over_all_permutations_of_authorizations_and_actions():
    auths = [A1, A2, A3]
    acts = [("actA", ["P1"]), ("actB", ["P2", "P3"]), ("actC", ["P3"])]
    outputs, queries = set(), set()
    for pa in itertools.permutations(auths):
        for pb in itertools.permutations(acts):
            result, w = _w16f(list(pa), list(pb))
            outputs.add(tuple(w))
            queries.add(repr(permit_omissions(result.model)))
    assert len(outputs) == 1 and len(next(iter(outputs))) == 3
    assert len(queries) == 1


# ── query output == what the message lists ───────────────────────────────

def test_message_lists_exactly_what_the_query_returns():
    auths = [A1,
             ("a2", "Auth2", "to_agent", "Ag", "P2", "S"),
             ("a3", "Auth2", "to_agent", "Ag", "P3", "S")]
    result, w = _w16f(auths, [("actA", ["P1"]), ("actB", ["P2"]), ("actC", ["P1", "P3"])])
    omissions = permit_omissions(result.model)
    assert len(w) == len(omissions) == 2          # actC consults both authorities
    for msg, om in zip(w, omissions):
        assert f"Action '{om.action.name}' (role '{om.action.role}', community '{om.action.community}')" in msg
        tail = msg.split("Not consulted: ")[1].split(". If every")[0]
        parsed = re.findall(r"authority '([^']+)' \(([^)]*)\)", tail)
        expected = [
            (o.authority, "; ".join(f"Authorization '{g.authorization_name}': permit '{g.permit}'" for g in o.grants))
            for o in om.omitted
        ]
        assert parsed == expected
        assert f"requires {', '.join(repr(p) for p in om.required)}" in msg


# ── named tracked scenarios ──────────────────────────────────────────────

_NAMED = (
    "scenarios/referral/referral_scenario.el",
    "scenarios/consent/consent_scenario.el",
    "scenarios/consent/federation_consent_scenario.el",
)
_PARITY_NAMED = _NAMED + (
    "scenarios/gp_referral/gp_referral_scenario.el",
    "scenarios/ereferral/ereferral_model.el",
)


def test_named_scenarios_have_no_w16f_and_no_co_granted_set():
    for path in _NAMED:
        result = parse(path, validate=True)
        assert result.ok, result.errors
        assert not any(w.startswith("[W-16f]") for w in result.warnings), path
        assert co_granted_permit_sets(result.model) == [], path
        assert permit_omissions(result.model) == [], path


def test_required_permit_sets_match_the_verifier_index_for_unique_action_names():
    """Parity with el_kripke._build_permit_requirement_index — the helper is
    an independent (fourth) extraction, so this is what stops it drifting.
    Compared only for action names that occur once (the index is keyed by
    bare action name, last wins)."""
    compared = 0
    for path in _PARITY_NAMED:
        result = parse(path, validate=False)
        assert result.model is not None, (path, result.errors)
        mine = required_permits_by_action(result.model)
        counts = {}
        for r in mine:
            counts[r.name] = counts.get(r.name, 0) + 1
        mine_unique = {r.name: set(r.permits) for r in mine if counts[r.name] == 1}
        index = _build_permit_requirement_index(result.model)
        index_unique = {k: set(v) for k, v in index.items() if counts.get(k) == 1}
        assert mine_unique == index_unique, path
        compared += len(mine_unique)
    assert compared > 0            # not vacuous: the named files do use requires_permit


def test_required_permit_sets_match_the_verifier_index_on_a_multi_permit_action():
    """Every tracked action names a single permit, so the named-file parity
    above cannot see a drift on actions that list several. This inline spec
    does (an Action may list any number of requires_permit clauses)."""
    result = parse_string(_spec([A1, A2], [("multi", ["P1", "P2", "P3"]), ("single", ["P2"])]),
                          validate=False)
    assert result.model is not None
    mine = {r.name: set(r.permits) for r in required_permits_by_action(result.model)}
    index = {k: set(v) for k, v in _build_permit_requirement_index(result.model).items()}
    assert mine == index == {"multi": {"P1", "P2", "P3"}, "single": {"P2"}}
