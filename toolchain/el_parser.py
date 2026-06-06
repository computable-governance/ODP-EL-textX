"""
el_parser.py
============
Core parsing entry-point for DSL-EL.

Loads el_grammar.tx via textX, creates a metamodel, and exposes
a clean parse() function that returns a validated, typed model.

Usage
-----
    from el_parser import parse, ParseResult

    result = parse("my_spec.el")
    if result.ok:
        spec = result.model
    else:
        for err in result.errors:
            print(err)

Dependencies
------------
    pip install textX
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

try:
    from textx import metamodel_from_file
    from textx.exceptions import TextXError, TextXSemanticError, TextXSyntaxError
except ImportError as exc:
    raise ImportError(
        "textX is required: pip install textX"
    ) from exc

# textX get_model() walks via hasattr(p, 'parent'); root objects must not
# declare parent — use _ELNode for roots, _ELParentable for contained objects.
# See el_domain.py base class hierarchy and Igor Dejanovic's recommendation (June 2026).

from el_domain import DOMAIN_CLASSES

# ── Path resolution ──────────────────────────────────────────────────────────

_HERE = Path(__file__).parent
GRAMMAR_PATH = _HERE.parent / "grammar" / "v2" / "el_grammar.tx"


# ── Result type ──────────────────────────────────────────────────────────────

@dataclass
class ParseResult:
    """Holds a parsed model or a list of error strings."""
    model: Optional[Any] = None
    errors: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


# ── Object processors ────────────────────────────────────────────────────────

def _inject_token_defaults(token):
    """Shared default injection for DeonticToken and InlineToken."""
    if not token.discharge_mode:
        token.discharge_mode = 'eventual'
    if not token.priority:
        token.priority = 'normal'
    # AM-22: triggered_by / discharged_by default to None (already set by
    # dataclass, but explicit here for documentation and future processors).
    if not hasattr(token, 'triggered_by'):
        token.triggered_by = None
    if not hasattr(token, 'discharged_by'):
        token.discharged_by = None


def process_deontic_token(token):
    """P1: inject discharge_mode and priority defaults when absent."""
    _inject_token_defaults(token)


def process_inline_token(token):
    """P1b: same defaults as P1 for role-scoped InlineToken (AM-24)."""
    _inject_token_defaults(token)


def process_enterprise_object(obj):
    """P2: flatten ObjectBody fields into EnterpriseObject; discard wrapper."""
    if obj.body:
        obj.holds_tokens = [ht.token for ht in obj.body.holds_tokens]
        if obj.body.delegated_from:
            obj.delegated_from = obj.body.delegated_from.delegator
            obj.delegation_duration = obj.body.delegated_from.duration
        obj.principal_of = [po.agent for po in obj.body.principal_of]
        obj.body = None


def process_role(role):
    """P3: split role.items into typed sublists."""
    for item in role.items:
        cls = type(item).__name__
        if cls == 'HoldsToken':
            role.holds_tokens.append(item.token)
        elif cls == 'InlineToken':
            # AM-24: InlineToken is the token itself (not a wrapper around a ref)
            role.holds_tokens.append(item)
        elif cls == 'PolicyRef':
            role.policy_refs.append(item)
        elif cls == 'SubObjectiveRef':
            role.satisfies_objectives.append(item.objective)
        elif cls == 'Action':
            role.actions.append(item)
        elif cls == 'ConditionalAction':
            role.conditional_actions.append(item)
    role.items = []


def process_action(action):
    """P4: unwrap description; split items into typed sublists."""
    if action.description:
        action.description = action.description.value
    for item in action.items:
        cls = type(item).__name__
        if cls == 'ActorRef':
            action.actors.append(item.role_name)
        elif cls == 'ArtefactRef':
            action.artefacts.append(item.ref_name)
        elif cls == 'ResourceRef':
            action.resources.append(item)
        elif cls == 'PreconditionDecl':
            action.preconditions.append(item.description)
        elif cls == 'DeonticRequirement':
            action.deontic_requirements.append(item)
        elif cls == 'DeonticEffect':
            action.deontic_effects.append(item)
        elif cls == 'EmitsDecl':
            # AM-22: last EmitsDecl wins if multiple appear (grammar allows only one)
            action.emits = item.event
    action.items = []


def process_conditional_action(ca):
    """P5: unwrap description; split items into typed sublists."""
    if ca.description:
        ca.description = ca.description.value
    for item in ca.items:
        cls = type(item).__name__
        if cls == 'RequiresPermitItem':
            ca.requires_permits.append(item.token)
        elif cls == 'InhibitedByItem':
            ca.inhibited_by.append(item.token)
        elif cls == 'FavouredByItem':
            ca.favoured_by.append(item.token)
        elif cls == 'ActorRef':
            ca.actors.append(item.role_name)
        elif cls == 'DeonticEffect':
            ca.deontic_effects.append(item)
    ca.items = []


def process_step(step):
    """P6: split items; extract nested Steps as sub_steps."""
    for item in step.items:
        cls = type(item).__name__
        if cls == 'DescriptionAttr':
            step.description = item.value
        elif cls == 'ActorRef':
            step.actors.append(item.role_name)
        elif cls == 'ArtefactRef':
            step.artefacts.append(item.ref_name)
        elif cls == 'ResourceRef':
            step.resources.append(item)
        elif cls == 'PreconditionDecl':
            step.preconditions.append(item.description)
        elif cls == 'DeonticRequirement':
            step.deontic_requirements.append(item)
        elif cls == 'DeonticEffect':
            step.deontic_effects.append(item)
        elif cls == 'Step':
            step.sub_steps.append(item)
    step.items = []


def process_process(proc):
    """P7: unwrap SatisfiesObjective wrappers to direct SubObjective refs."""
    proc.satisfies_objectives = [s.objective for s in proc.satisfies_objectives]


def process_domain(domain):
    """P8: split body_items into typed sublists."""
    for item in domain.body_items:
        cls = type(item).__name__
        if cls == 'DomainControllingObj':
            domain.controlling_objects.append(item.obj)
        elif cls == 'DomainControlledObj':
            domain.controlled_objects.append(item.obj)
        elif cls == 'PolicyRef':
            domain.policy_refs.append(item)
    domain.body_items = []


def process_federation(fed):
    """P9: split body_items into typed sublists; unwrap thin wrappers.

    AM-25: objective is set directly by textX (direct grammar attribute, not in
    body_items). EventDecl items are now collected into fed.events.
    """
    for item in fed.body_items:
        cls = type(item).__name__
        if cls == 'FedSharedObjective':
            fed.shared_objectives.append(item.description)
        elif cls == 'MemberRef':
            fed.members.append(item.community)
        elif cls == 'PolicyRef':
            fed.policy_refs.append(item)
        elif cls == 'Invariant':
            fed.invariants.append(item)
        elif cls == 'WithdrawalBehaviour':
            fed.withdrawal_behaviour = item.description
        elif cls == 'ConflictResolution':
            fed.conflict_resolution = item
        elif cls == 'EventDecl':              # AM-25
            fed.events.append(item)
    fed.body_items = []


# ── Metamodel builder ─────────────────────────────────────────────────────────

def _build_metamodel():
    """
    Build the textX metamodel from the grammar file.

    textX options used:
      auto_init_obj  — textX pre-populates list attributes to []
                        so validators never see None for empty lists.
      global_model_params — exposed to custom obj processors if needed.
    """
    mm = metamodel_from_file(str(GRAMMAR_PATH), classes=DOMAIN_CLASSES)
    mm.register_obj_processors({
        'DeonticToken':       process_deontic_token,       # P1
        'InlineToken':        process_inline_token,        # P1b (AM-24)
        'EnterpriseObject':   process_enterprise_object,   # P2
        'Role':               process_role,                # P3
        'Action':             process_action,              # P4
        'ConditionalAction':  process_conditional_action,  # P5
        'Step':               process_step,                # P6
        'Process':            process_process,             # P7
        'Domain':             process_domain,              # P8
        'Federation':         process_federation,          # P9
    })
    return mm


_METAMODEL = None   # lazy singleton


def _get_metamodel():
    global _METAMODEL
    if _METAMODEL is None:
        _METAMODEL = _build_metamodel()
    return _METAMODEL


# ── Public API ────────────────────────────────────────────────────────────────

def parse(source: str | Path, *, validate: bool = True) -> ParseResult:
    """
    Parse a DSL-EL specification file.

    Parameters
    ----------
    source   : path to a .el file OR a raw string containing EL text.
    validate : run semantic validation after parsing (recommended).

    Returns
    -------
    ParseResult with .model (EnterpriseSpec) on success, or .errors list.
    """
    mm = _get_metamodel()
    result = ParseResult()

    try:
        if isinstance(source, (str, Path)) and os.path.isfile(str(source)):
            model = mm.model_from_file(str(source))
        else:
            model = mm.model_from_str(str(source))
    except TextXSyntaxError as exc:
        result.errors.append(f"[SYNTAX] {exc}")
        return result
    except TextXSemanticError as exc:
        result.errors.append(f"[SEMANTIC] {exc}")
        return result
    except TextXError as exc:
        result.errors.append(f"[PARSE ERROR] {exc}")
        return result

    result.model = model

    if validate:
        from el_validator import validate_spec
        semantic_errors = validate_spec(model)
        result.errors.extend(semantic_errors)

    return result


def parse_string(text: str, *, validate: bool = True) -> ParseResult:
    """Convenience wrapper for in-memory EL text."""
    return parse(text, validate=validate)


# ── Model introspection helpers ───────────────────────────────────────────────

def collect(model, cls_name: str) -> List[Any]:
    """
    Collect all objects of a given class name from the flat element list.

    Works on an EnterpriseSpec model returned by parse().
    """
    return [
        e for e in model.elements
        if type(e).__name__ == cls_name
    ]


def find_by_name(model, cls_name: str, name: str) -> Optional[Any]:
    """Return the first element of cls_name whose .name == name."""
    for e in collect(model, cls_name):
        if getattr(e, "name", None) == name:
            return e
    return None


# ── CLI entry-point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys, json

    if len(sys.argv) < 2:
        print("Usage: python el_parser.py <spec.el>")
        sys.exit(1)

    result = parse(sys.argv[1])
    if result.ok:
        spec = result.model
        print(f"✓ Parsed '{spec.name}' successfully.")
        print(f"  Elements: {len(spec.elements)}")
        counts = {}
        for e in spec.elements:
            t = type(e).__name__
            counts[t] = counts.get(t, 0) + 1
        for t, n in sorted(counts.items()):
            print(f"    {t}: {n}")
    else:
        print("✗ Parse/validation errors:")
        for err in result.errors:
            print(f"  {err}")
        sys.exit(1)
