"""
el_domain.py
============
Domain classes for the DSL-EL computable governance toolchain.

Each class corresponds to a grammar rule in grammar/v2/el_grammar.tx and
is registered with textX via the ``classes=`` parameter in el_parser.py
(Step 3). textX instantiates these directly during parsing, replacing the
generic object model with typed domain objects — eliminating the separate
compilation/hydration step.

Design principles
-----------------
- Grammar is the schema: every class attribute name matches the
  corresponding grammar rule attribute exactly, so textX can populate
  fields without any renaming.
- Frozen dataclasses: ``frozen=True`` enforces immutability consistent
  with Thomas Sepanosian's WorldState design. Pydantic may replace
  dataclasses once structure stabilises (Step 5).
- Object processors (Step 4) handle post-parse work: injecting enum
  defaults, flattening body wrappers, splitting unified item lists into
  typed sublists, and unwrapping thin grammar artefacts.
- Stub classes: constructs with no current runtime role (Federation,
  Domain, Correspondence, Lifecycle sub-parts) are included as stubs so
  the parser never produces untyped generic objects.

Standard reference: ISO/IEC 15414:2015 (BS ISO/IEC 15414:2015)

Class inventory (mirrors STEP1_grammar_audit.md):
    Group A  — EnterpriseSpec
    Group B  — EnterpriseObject, ObjectBody, DelegatedFrom, PrincipalOf
    Group C  — DeonticToken, TokenGroup
    Group D  — Policy, PolicyRule, AffectedElement, SettingBehaviour,
               Enforcement, Duration, NumberInterval,
               PolicyEnvelope, EnvelopeRule,
               NormativePolicy, NormativePolicyRef (AM-28)
    Group E  — Community, EventDecl, Objective, SubObjective, Invariant,
               AssignmentPolicy, AssignmentRule subtypes, JoinLeaveEffect,
               CommunityInteraction
    Group F  — Role, InlineToken, Action, EmitsDecl, DeonticRequirement,
               DeonticEffect, ConditionalAction, Process, Step,
               ActorRef, ArtefactRef, ResourceRef, DescriptionAttr,
               SubObjectiveRef, SatisfiesObjective,
               RequiresPermitItem, InhibitedByItem, FavouredByItem
    Group G  — Lifecycle, Establishing, EmbeddedCommitment, Changes,
               Terminating
    Group H  — CommunityObject, Domain, DomainControllingObj, DomainControlledObj,
               Federation, FedSharedObjective, MemberRef,
               WithdrawalBehaviour, ConflictResolution
    Group I  — Commitment, Delegation, Authorization, Prescription,
               Declaration, Evaluation, ViolationResponse
    Group J  — Correspondence
    Group K  — PolicyRef
    Enums    — all enum types (incl. AM-23: DurationUnit, EnvelopeRuleKind)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, TYPE_CHECKING

# ---------------------------------------------------------------------------
# Enums
# All values are the exact keyword strings used in the grammar so that
# object processors can compare directly against parsed strings.
# ---------------------------------------------------------------------------

class ObjectKind(str, Enum):
    """§7.4 enterprise object taxonomy."""
    party           = "party"
    agent           = "agent"
    active_object   = "active_object"
    artefact_object = "artefact_object"
    resource_object = "resource_object"


class DeonticKind(str, Enum):
    """§6.4.3–6.4.5 deontic token types."""
    burden  = "burden"
    permit  = "permit"
    embargo = "embargo"


class TokenState(str, Enum):
    """§7.8.7 deontic token states."""
    active  = "active"
    pending = "pending"


class DischargeMode(str, Enum):
    """AM-13: controls Layer 4 AF verification.
    strict   — holder must act at first opportunity; AF holds by construction.
    eventual — holder may delay; AF may not hold (default).
    """
    eventual = "eventual"
    strict   = "strict"


class PriorityLevel(str, Enum):
    """AM-15: obligation priority for Layer 4 utility function (§C.3).
    Weights: critical=1.0, high=0.75, normal=0.5, low=0.25.
    """
    critical = "critical"
    high     = "high"
    normal   = "normal"
    low      = "low"


class DeonticRuleKind(str, Enum):
    """§6.5.1, §7.8.8 policy rule kinds."""
    obligation    = "obligation"
    permission    = "permission"
    prohibition   = "prohibition"
    authorization = "authorization"


class AffectedScope(str, Enum):
    """§6.5.2 scope of affected behaviour."""
    role      = "role"
    community = "community"
    process   = "process"
    action    = "action"
    object    = "object"


class EnforcementMode(str, Enum):
    """§7.9.4 policed enforcement modes."""
    optimistic  = "optimistic"
    pessimistic = "pessimistic"


class AssignableKind(str, Enum):
    """§7.7 sub-objective assignment targets."""
    role    = "role"
    process = "process"


class DeonticReqKind(str, Enum):
    """§6.4.6 conditional action requirement kinds."""
    requires_permit      = "requires_permit"
    inhibited_by_embargo = "inhibited_by_embargo"
    favoured_by_burden   = "favoured_by_burden"


class TokenOp(str, Enum):
    """§6.4.7, §7.8.7 deontic token lifecycle operations."""
    create   = "create"
    destroy  = "destroy"
    transfer = "transfer"
    activate = "activate"
    pend     = "pend"
    clone    = "clone"


class JoinLeaveKind(str, Enum):
    """§7.8.7 NOTE 3 — direction of join/leave token transfer."""
    join  = "join"
    leave = "leave"


class ConflictResolutionKind(str, Enum):
    """§7.9.2 NOTE 3 — federation conflict resolution strategies."""
    specification_time_assurance = "specification_time_assurance"
    runtime_prevention           = "runtime_prevention"
    runtime_resolution           = "runtime_resolution"
    failure_handling             = "failure_handling"


class ViewpointName(str, Enum):
    """§11 ODP viewpoint names for correspondence declarations."""
    information   = "information"
    computational = "computational"
    engineering   = "engineering"
    technology    = "technology"


class ViolationResponseKind(str, Enum):
    """§6.3.8, §7.8.6 NOTE 2 — prescribed response to a violation."""
    escalate  = "escalate"
    remediate = "remediate"
    penalise  = "penalise"
    terminate = "terminate"


class DurationUnit(str, Enum):
    """AM-23: time unit for Duration policy values."""
    minute  = "minute";  minutes = "minutes"
    hour    = "hour";    hours   = "hours"
    day     = "day";     days    = "days"
    week    = "week";    weeks   = "weeks"
    month   = "month";   months  = "months"
    year    = "year";    years   = "years"


class EnvelopeRuleKind(str, Enum):
    """AM-23: policy envelope constraint type."""
    one  = "one"
    set  = "set"
    list = "list"


# ---------------------------------------------------------------------------
# Base class hierarchy — Igor Dejanovic's recommendation
# textX get_model() walks via hasattr(p, 'parent'); root objects must not
# declare parent — use _ELNode for roots, _ELParentable for contained objects
# ---------------------------------------------------------------------------

@dataclass
class _ELNode:
    """Base for root-level domain objects that have no textX containment parent.

    textX 4.x get_model() loops `while hasattr(p, "parent"): p = p.parent`.
    Root objects must NOT declare parent — otherwise the loop overshoots the
    root and returns None, breaking get_location() and get_parser() for
    registered processors. Only EnterpriseSpec inherits this class.
    """


@dataclass
class _ELParentable(_ELNode):
    """Base for all contained domain objects.

    Declares the 'parent' field that textX 4.x injects into every custom
    class's __init__ call (_end_model_construction in textx/model.py).
    get_model() traversal stops at an _ELNode root (which has no 'parent'
    attribute). All domain classes except EnterpriseSpec inherit this class.
    """
    parent: Optional[Any] = field(default=None, repr=False, compare=False)


# ---------------------------------------------------------------------------
# Group A — Top-level container
# ---------------------------------------------------------------------------

@dataclass
class EnterpriseSpec(_ELNode):
    """§7.1, §7.2 — top-level enterprise specification container.

    Grammar rule: EnterpriseSpec
    textX registration: classes=[EnterpriseSpec, ...]
    """
    name:                str              = ""
    description:         Optional[str]   = None
    field_of_application: Optional[str]  = None
    scope:               Optional[str]   = None
    elements:            List            = field(default_factory=list)
    # elements is List[SpecElement union] — typed post-parse by object processor


# ---------------------------------------------------------------------------
# Group B — Enterprise objects
# ---------------------------------------------------------------------------

@dataclass
class DelegatedFrom(_ELParentable):
    """§6.6.8 NOTE 3 — static initial delegation declaration.

    Grammar rule: DelegatedFromDecl
    Folded into EnterpriseObject by object processor (P2).
    """
    delegator: Optional[object] = None   # → EnterpriseObject ref
    duration:  Optional[str]   = None


@dataclass
class PrincipalOf(_ELParentable):
    """Grammar rule: PrincipalOfDecl — inverse of delegated_from.

    Folded into EnterpriseObject by object processor (P2).
    """
    agent: Optional[object] = None       # → EnterpriseObject ref


@dataclass
class HoldsToken(_ELParentable):
    """Grammar rule: HoldsToken — token held by an enterprise object.

    Wrapper dissolved by object processor (P2/P3).
    """
    token: Optional[object] = None       # → DeonticToken ref


@dataclass
class ObjectBody(_ELParentable):
    """Grammar rule: ObjectBody — body of an EnterpriseObjectDecl.

    Wrapper dissolved by object processor (P2); fields folded into
    EnterpriseObject directly.
    """
    holds_tokens:    List = field(default_factory=list)  # List[HoldsToken]
    delegated_from:  Optional[DelegatedFrom] = None
    principal_of:    List = field(default_factory=list)  # List[PrincipalOf]


@dataclass
class EnterpriseObject(_ELParentable):
    """§6.3.1, §6.6.1, §6.6.8, §7.4 — enterprise object (party, agent, etc.).

    Grammar rule: EnterpriseObjectDecl (renamed from ObjectDecl per AM-15).
    Registered against 'EnterpriseObjectDecl' in textX classes= list.

    Cross-viewpoint naming convention (AM-15):
        EnterpriseObjectDecl → EnterpriseObject  (enterprise viewpoint)
        Future: ComputationalObjectDecl → ComputationalObject, etc.

    Object processor (P2) folds ObjectBody fields into this class directly
    and discards the ObjectBody wrapper.
    """
    kind:         str            = ""     # ObjectKind enum value
    name:         str            = ""
    type_ref:     Optional[object] = None  # → EnterpriseObject (isa)
    description:  Optional[str] = None
    body:         Optional[ObjectBody] = None  # dissolved by P2

    # Folded from ObjectBody by object processor P2:
    holds_tokens:   List = field(default_factory=list)  # List[DeonticToken]
    delegated_from: Optional[object] = None  # → EnterpriseObject
    delegation_duration: Optional[str] = None
    principal_of:   List = field(default_factory=list)  # List[EnterpriseObject]


# ---------------------------------------------------------------------------
# Group C — Deontic tokens
# ---------------------------------------------------------------------------

@dataclass
class DeonticToken(_ELParentable):
    """§6.4.3–6.4.5, §7.8.7 — deontic token (burden, permit, or embargo).

    Grammar rule: DeonticTokenDecl
    Single class covering all three kinds; discriminated by .kind field.

    Object processor (P1) injects defaults:
        discharge_mode = DischargeMode.eventual  (if absent)
        priority       = PriorityLevel.normal    (if absent)
    """
    kind:                 str            = ""      # DeonticKind
    name:                 str            = ""
    for_action:           Optional[str] = None
    state:                str            = ""      # TokenState
    deadline:             Optional[str] = None
    triggered_by:         Optional[object] = None  # AM-22: → EventDecl ref
    discharged_by:        Optional[object] = None  # AM-22: → EventDecl ref
    discharge_mode:       str            = "eventual"  # DischargeMode; P1 default
    priority:             str            = "normal"    # PriorityLevel; P1 default
    description:          Optional[str] = None
    requires_permit_for:  Optional[str] = None
    inhibited_by_embargo: Optional[str] = None
    favoured_by_burden:   Optional[str] = None


@dataclass
class TokenGroup(_ELParentable):
    """§6.4.2 — named group of deontic tokens.

    Grammar rule: TokenGroup
    """
    name:    str  = ""
    members: List = field(default_factory=list)  # List[TokenGroupMember]; cleared by P10
    tokens:  List = field(default_factory=list)  # List[DeonticToken]; populated by P10


@dataclass
class TokenGroupMember(_ELParentable):
    """§6.4.2 — thin wrapper for one member declaration in a TokenGroup.

    Grammar rule: TokenGroupMember
    Object processor P10 unwraps .token into TokenGroup.tokens and clears members.
    """
    token: Optional[object] = None   # → DeonticToken ref


# ---------------------------------------------------------------------------
# Group D — Policies
# ---------------------------------------------------------------------------

@dataclass
class PolicyRule(_ELParentable):
    """§6.5.1, §7.8.8 — a single deontic rule within a policy.

    Grammar rule: PolicyRule
    """
    kind:      str = ""   # DeonticRuleKind
    target:    str = ""   # plain ID — known design debt (should be cross-ref)
    rule_text: str = ""


@dataclass
class AffectedElement(_ELParentable):
    """§6.5.2 — identifies which roles/processes/actions a policy constrains.

    Grammar rule: AffectedElement
    """
    scope:    str = ""   # AffectedScope
    ref_name: str = ""   # plain ID — known design debt


@dataclass
class SettingBehaviour(_ELParentable):
    """§7.9.3 — behaviour that changes the policy value.

    Grammar rule: SettingBehaviourDecl
    """
    description:          Optional[str]  = None
    who_can_change:       Optional[str]  = None
    negotiation_required: bool           = False


@dataclass
class Enforcement(_ELParentable):
    """§7.9.4 — enforcement mode for a policy.

    Grammar rule: EnforcementDecl
    Object processor (P11) sets unpoliced=True when mode is absent.
    """
    mode:      Optional[str]  = None   # EnforcementMode; None = unpoliced
    mechanism: Optional[str]  = None
    unpoliced: bool            = False  # P11: derived from absent mode


@dataclass
class PolicyRef(_ELParentable):
    """Policy reference used inside Community, Role, Federation, Domain.

    Grammar rule: PolicyRef
    """
    policy:   Optional[object] = None   # → Policy ref
    scope:    Optional[str]    = None   # AffectedScope
    ref_name: Optional[str]    = None


@dataclass
class Duration(_ELParentable):
    """AM-23: typed duration value (e.g. 30 minutes). ISO 15414 Figure A.4."""
    value: int = 0
    unit:  str = ""   # DurationUnit


@dataclass
class NumberInterval(_ELParentable):
    """AM-23: integer range value (e.g. 7..10). ISO 15414 Figure A.4.
    Grammar attrs: lower=INT '..' upper=INT (renamed from from/to — Python keyword conflict).
    """
    lower: int = 0
    upper: int = 0


@dataclass
class EnvelopeRule(_ELParentable):
    """AM-23: single constraint inside a PolicyEnvelope."""
    kind:   str  = ""    # EnvelopeRuleKind
    values: List = field(default_factory=list)  # List[PolicyValue]


@dataclass
class PolicyEnvelope(_ELParentable):
    """AM-23, ISO 15414 Figure A.4, §7.9.2 — constrains the set of policy values."""
    envelope_rules: List = field(default_factory=list)  # List[EnvelopeRule]


@dataclass
class Policy(_ELParentable):
    """§6.5, §7.9 — governance policy declaration.

    Grammar rule: PolicyDecl
    """
    name:              str            = ""
    policy_type:       str            = ""      # AM-23: PolicyType keyword or user-defined ID
    description:       Optional[str] = None
    initial_value:     Optional[object] = None  # AM-23: PolicyValue (typed)
    envelope:          Optional[PolicyEnvelope] = None  # AM-23: replaces plain str
    rules:             List           = field(default_factory=list)  # List[PolicyRule]
    affected_elements: List           = field(default_factory=list)  # List[AffectedElement]
    setting_behaviour: Optional[SettingBehaviour] = None
    enforcement:       Optional[Enforcement]       = None


# ---------------------------------------------------------------------------
# AM-28 — NormativePolicy (DSL extension, §6.5 specialisation)
# ---------------------------------------------------------------------------

@dataclass
class NormativePolicy(_ELParentable):
    """AM-28 — DSL extension specialising §6.5 Policy for externally-
    grounded normative instruments.

    IS-A Policy in the standard sense: has value, envelope, and setting
    behaviour. The setting_behaviour refers to an external process
    (legislative amendment, standards review cycle) not an internal role.

    Valid only in Domain and Federation body items (V-NEW-20).

    kind values: legislation | regulation | standard | guideline | contractual
    """
    name:              str            = ""
    description:       Optional[str] = None
    source:            str            = ""     # citation — mandatory
    kind:              str            = ""     # NormativePolicyKind — mandatory
    policy_type:       Optional[str] = None
    initial_value:     Optional[object] = None
    review_cycle:      Optional[object] = None  # Duration
    setting_behaviour: Optional[str] = None     # prose — external process


@dataclass
class NormativePolicyRef(_ELParentable):
    """AM-28 — reference to a top-level NormativePolicy from a Domain
    or Federation body item.

    Grammar rule: NormativePolicyRef
    Object processors dissolve this into domain.normative_policies /
    federation.normative_policies.
    """
    policy: Optional[object] = None   # → NormativePolicy ref


# ---------------------------------------------------------------------------
# Group E — Community and its sub-parts
# ---------------------------------------------------------------------------

@dataclass
class SubObjective(_ELParentable):
    """§7.7 — sub-objective within a community objective.

    Grammar rule: SubObjectiveDecl
    """
    name:             str            = ""
    description:      str            = ""
    assigned_to_kind: Optional[str] = None   # AssignableKind
    assigned_to_name: Optional[str] = None   # plain ID — known design debt


@dataclass
class SubObjectiveRef(_ELParentable):
    """Grammar rule: SubObjectiveRef — wrapper dissolved by P3."""
    objective: Optional[object] = None   # → SubObjective ref


@dataclass
class InlineToken(_ELParentable):
    """AM-24, §6.4, §7.8.2 — token declared and held inline on a role.

    Scoped to one role; cannot be referenced from DelegationDecl,
    CommitmentDecl, or AuthorizationDecl (V-NEW-18).
    Object processor P3 adds InlineToken instances to Role.holds_tokens.
    """
    kind:          str            = ""      # DeonticKind
    name:          str            = ""
    for_action:    Optional[str] = None
    state:         str            = ""      # TokenState
    deadline:      Optional[str] = None
    triggered_by:  Optional[object] = None  # AM-22: → EventDecl ref
    discharged_by: Optional[object] = None  # AM-22: → EventDecl ref
    discharge_mode: str           = "eventual"   # DischargeMode; P1 default
    priority:      str            = "normal"     # PriorityLevel; P1 default
    description:   Optional[str] = None


@dataclass
class SatisfactionArg(_ELParentable):
    """AM-29 — thin wrapper for a single SatisfactionCondition argument.

    Grammar rule: SatisfactionArg
    Holds a plain ID string (not a typed cross-reference) so that
    el_kripke.py can resolve it as either a TokenGroup name or a
    DeonticToken name after the full model is available.
    """
    name: str = ""


@dataclass
class SatisfactionCondition(_ELParentable):
    """AM-27/AM-29 — machine-checkable objective satisfaction condition.

    Grammar rule: SatisfactionCondition
    raw_args holds SatisfactionArg objects parsed from the grammar.
    The resolution of whether each arg is a TokenGroup reference
    (AM-27, single arg matching a declared TokenGroup) or a direct
    DeonticToken name (AM-29, one or more token names) happens in
    el_kripke.py _build_satisfaction_conditions() and el_validator.py.
    """
    operator: str = ""
    raw_args: List = field(default_factory=list)  # List[SatisfactionArg]


@dataclass
class Objective(_ELParentable):
    """§6.2, §7.7 — community objective.

    Grammar rule: Objective
    """
    description:    str            = ""
    satisfaction:   Optional[object] = None  # → SatisfactionCondition (AM-27)
    sub_objectives: List           = field(default_factory=list)  # List[SubObjective]


@dataclass
class Invariant(_ELParentable):
    """Community or federation invariant.

    Grammar rule: InvariantDecl
    """
    name:        str = ""
    description: str = ""


@dataclass
class AssignmentPolicy(_ELParentable):
    """§7.6.2, §7.8.2 — rules governing role fulfilment.

    Grammar rule: AssignmentPolicyDecl
    """
    role_name: str  = ""    # plain ID — known design debt (should be Role ref)
    rules:     List = field(default_factory=list)  # List[AssignmentRule subtypes]


# AssignmentRule subtypes — four concrete alternatives

@dataclass
class RequiresCapabilityRule(_ELParentable):
    """Grammar rule: RequiresCapabilityRule"""
    description: str = ""

@dataclass
class ExcludesRoleRule(_ELParentable):
    """Grammar rule: ExcludesRoleRule"""
    excluded_role_name: str = ""

@dataclass
class RequiresTokenRule(_ELParentable):
    """Grammar rule: RequiresTokenRule"""
    kind:        str = ""   # DeonticKind
    description: str = ""

@dataclass
class RequiresRelationRule(_ELParentable):
    """Grammar rule: RequiresRelationRule"""
    description: str = ""


@dataclass
class JoinLeaveEffect(_ELParentable):
    """§7.8.7 NOTE 3 — token transfer when object fills or leaves a role.

    Grammar rule: JoinLeaveEffect
    Object processor (P10) infers .kind from parse tree structure.
    """
    role_name: str            = ""
    token:     Optional[object] = None   # → DeonticToken ref
    kind:      str            = ""       # JoinLeaveKind; P10 inferred


@dataclass
class CommunityInteraction(_ELParentable):
    """§7.3.2 — relationship between communities.

    Grammar rule: CommunityInteraction
    """
    other:          Optional[object] = None   # → Community ref
    common_policies: List = field(default_factory=list)  # List[PolicyRef]
    invariants:      List = field(default_factory=list)  # List[Invariant]
    description:     Optional[str]   = None


@dataclass
class EventDecl(_ELParentable):
    """ODP Part 2 §8.4 — named event scoped to a community.

    Events trigger and discharge deontic tokens (§6.4) and communicate
    state changes between roles (§6.3.6).
    Grammar rule: EventDecl
    """
    name:        str            = ""
    description: Optional[str] = None


@dataclass
class Community(_ELParentable):
    """§6.2, §7.3 — purpose-bound grouping with shared objective and contract.

    Grammar rule: Community
    AM-21: contract?='contract' qualifier promoted to boolean flag;
           invariants, assignment_policies, join_leave_effects promoted
           from Contract sub-block to direct community fields.
    AM-22: events list added for community-scoped EventDecl declarations.
    """
    contract:            bool           = False  # AM-21: optional 'contract' qualifier
    name:                str            = ""
    type_ref:            Optional[object] = None   # → Community (isa)
    description:         Optional[str]  = None
    objective:           Optional[Objective] = None
    events:              List = field(default_factory=list)  # AM-22: List[EventDecl]
    invariants:          List = field(default_factory=list)  # AM-21: List[Invariant]
    assignment_policies: List = field(default_factory=list)  # AM-21: List[AssignmentPolicy]
    join_leave_effects:  List = field(default_factory=list)  # AM-21: List[JoinLeaveEffect]
    roles:               List = field(default_factory=list)  # List[Role]
    processes:           List = field(default_factory=list)  # List[Process]
    policy_refs:         List = field(default_factory=list)  # List[PolicyRef]
    interactions:        List = field(default_factory=list)  # List[CommunityInteraction]
    lifecycle:           Optional[object] = None              # → Lifecycle


# ---------------------------------------------------------------------------
# Group F — Roles, Actions, Processes, Steps
# ---------------------------------------------------------------------------

@dataclass
class DescriptionAttr(_ELParentable):
    """Grammar artefact: DescriptionAttr wrapper.

    Dissolved by object processors P4/P5 — .value → parent.description.
    """
    value: str = ""


@dataclass
class ActorRef(_ELParentable):
    """Grammar rule: ActorRef — actor role reference inside an action/step."""
    role_name: str = ""


@dataclass
class ArtefactRef(_ELParentable):
    """Grammar rule: ArtefactRef — artefact reference inside an action/step."""
    ref_name: str = ""


@dataclass
class ResourceRef(_ELParentable):
    """Grammar rule: ResourceRef — resource reference inside an action/step."""
    ref_name:   str  = ""
    consumable: bool = False


@dataclass
class DeonticRequirement(_ELParentable):
    """§6.4.6 — deontic requirement on an action participant.

    Grammar rule: DeonticReqDecl
    """
    kind:      str            = ""    # DeonticReqKind
    token:     Optional[object] = None  # → DeonticToken ref
    role_name: Optional[str]  = None


@dataclass
class DeonticEffect(_ELParentable):
    """§6.4.7, §7.8.7 — effect on token lifecycle when action is performed.

    Grammar rule: DeonticEffectDecl
    """
    operation: str            = ""    # TokenOp
    token:     Optional[object] = None  # → DeonticToken ref
    from_role: Optional[str]  = None
    to_role:   Optional[str]  = None


@dataclass
class PreconditionDecl(_ELParentable):
    """Grammar rule: PreconditionDecl — action/step precondition."""
    description: str = ""


@dataclass
class EmitsDecl(_ELParentable):
    """AM-22, ODP Part 2 §8.4 — event raised when an action is performed.

    Grammar rule: EmitsDecl (ActionBodyItem alternative).
    Object processor P4 extracts .event into Action.emits.
    """
    event: Optional[object] = None   # → EventDecl ref


# ConditionalAction item wrappers — dissolved by P5

@dataclass
class RequiresPermitItem(_ELParentable):
    """Grammar rule: RequiresPermitItem"""
    token: Optional[object] = None   # → DeonticToken ref

@dataclass
class InhibitedByItem(_ELParentable):
    """Grammar rule: InhibitedByItem"""
    token: Optional[object] = None   # → DeonticToken ref

@dataclass
class FavouredByItem(_ELParentable):
    """Grammar rule: FavouredByItem"""
    token: Optional[object] = None   # → DeonticToken ref


@dataclass
class Action(_ELParentable):
    """§6.3.6, §7.8.4 — enterprise action.

    Grammar rule: ActionDecl
    Object processor (P4) splits .items and unwraps DescriptionAttr.
    """
    name:        str            = ""
    description: Optional[str] = None   # P4: unwrapped from DescriptionAttr
    items:       List           = field(default_factory=list)  # raw; P4 splits

    # Populated by object processor P4:
    actors:               List = field(default_factory=list)  # List[str] role_names
    artefacts:            List = field(default_factory=list)  # List[str] ref_names
    resources:            List = field(default_factory=list)  # List[ResourceRef]
    preconditions:        List = field(default_factory=list)  # List[str]
    deontic_requirements: List = field(default_factory=list)  # List[DeonticRequirement]
    deontic_effects:      List = field(default_factory=list)  # List[DeonticEffect]
    emits:                Optional[object] = None  # AM-22: → EventDecl ref; P4 from EmitsDecl
    favoured_by:          List = field(default_factory=list)  # List[DeonticToken]; P4 from FavouredByItem


@dataclass
class ConditionalAction(_ELParentable):
    """§6.4.6 — action whose occurrence depends on deontic state.

    Grammar rule: ConditionalActionDecl
    Object processor (P5) splits .items and unwraps DescriptionAttr.
    """
    name:        str            = ""
    description: Optional[str] = None   # P5: unwrapped
    items:       List           = field(default_factory=list)  # raw; P5 splits

    # Populated by object processor P5:
    requires_permits: List = field(default_factory=list)  # List[DeonticToken]
    inhibited_by:     List = field(default_factory=list)  # List[DeonticToken]
    favoured_by:      List = field(default_factory=list)  # List[DeonticToken]
    actors:           List = field(default_factory=list)  # List[str]
    deontic_effects:  List = field(default_factory=list)  # List[DeonticEffect]


@dataclass
class SatisfiesObjective(_ELParentable):
    """Grammar rule: SatisfiesObjective — wrapper dissolved by P7."""
    objective: Optional[object] = None   # → SubObjective ref


@dataclass
class Step(_ELParentable):
    """§6.3.7, §7.8.5 — abstraction of an action within a process.

    Grammar rule: StepDecl
    Object processor (P6) splits .items.
    """
    name:   str            = ""
    refines_step: Optional[object] = None   # → Step ref (refines)
    items:  List           = field(default_factory=list)  # raw; P6 splits

    # Populated by object processor P6:
    description:          Optional[str] = None
    actors:               List = field(default_factory=list)
    artefacts:            List = field(default_factory=list)
    resources:            List = field(default_factory=list)
    preconditions:        List = field(default_factory=list)
    deontic_requirements: List = field(default_factory=list)
    deontic_effects:      List = field(default_factory=list)
    sub_steps:            List = field(default_factory=list)  # List[Step]


@dataclass
class Process(_ELParentable):
    """§6.3.7, §7.8.5 — collection of steps in a prescribed manner.

    Grammar rule: ProcessDecl
    Object processor (P7) unwraps SatisfiesObjective wrappers.
    """
    name:                 str            = ""
    description:          Optional[str] = None
    satisfies_objectives: List           = field(default_factory=list)  # List[SubObjective] refs; P7
    initiation:           str            = ""
    termination:          str            = ""
    steps:                List           = field(default_factory=list)  # List[Step]


@dataclass
class Role(_ELParentable):
    """§6.3.5, §7.8.2, §7.8.3 — abstract position in a community.

    Grammar rule: RoleDecl
    Object processor (P3) splits .items into typed sublists.
    """
    interface:    bool          = False   # interface?='interface'
    name:         str           = ""
    type_ref:     Optional[object] = None  # → Role (isa)
    description:  Optional[str] = None
    items:        List          = field(default_factory=list)  # raw; P3 splits

    # Populated by object processor P3:
    holds_tokens:        List = field(default_factory=list)  # List[DeonticToken]
    policy_refs:         List = field(default_factory=list)  # List[PolicyRef]
    satisfies_objectives: List = field(default_factory=list)  # List[SubObjective]
    actions:             List = field(default_factory=list)  # List[Action]
    conditional_actions: List = field(default_factory=list)  # List[ConditionalAction]


# ---------------------------------------------------------------------------
# Group G — Community lifecycle
# ---------------------------------------------------------------------------

@dataclass
class EmbeddedCommitment(_ELParentable):
    """Inline commitment inside establishing behaviour.

    Grammar rule: EmbeddedCommitment
    actor_name is a plain ID — not a cross-ref (known design debt).
    """
    actor_name:  str = ""
    description: str = ""


@dataclass
class Establishing(_ELParentable):
    """§7.6.1 — community establishing behaviour.

    Grammar rule: EstablishingDecl
    """
    implicit:    bool = False
    description: Optional[str] = None
    commitments: List = field(default_factory=list)  # List[EmbeddedCommitment]


@dataclass
class Changes(_ELParentable):
    """§7.6.3 — dynamic changes allowed during community lifetime.

    Grammar rule: ChangesDecl
    """
    roles_dynamic:      bool         = False
    policies_dynamic:   bool         = False
    membership_dynamic: bool         = False
    description:        Optional[str] = None


@dataclass
class Terminating(_ELParentable):
    """§7.6.4 — community termination conditions.

    Grammar rule: TerminatingDecl
    on_objective maps to grammar attr on_objective (from on_objective_achieved).
    """
    on_objective: bool         = False
    permanent:    bool         = False
    description:  Optional[str] = None


@dataclass
class Lifecycle(_ELParentable):
    """§7.6 — community lifecycle declaration.

    Grammar rule: LifecycleDecl
    """
    establishing: Optional[Establishing] = None
    changes:      Optional[Changes]      = None
    terminating:  Optional[Terminating]  = None


# ---------------------------------------------------------------------------
# Group H — Domain and Federation (stub-level for now; extended in Step 7)
# ---------------------------------------------------------------------------

@dataclass
class DomainControllingObj(_ELParentable):
    """Grammar rule: DomainControllingObj"""
    obj: Optional[object] = None   # → EnterpriseObject ref

@dataclass
class DomainControlledObj(_ELParentable):
    """Grammar rule: DomainControlledObj"""
    obj: Optional[object] = None   # → EnterpriseObject ref


@dataclass
class CommunityObject(_ELParentable):
    """§6.2.2, §7.8.3 — active EO abstracting a community.

    A CommunityObject represents a community as a whole in another
    community's context. It fills roles in federations and other
    communities on behalf of the community it abstracts.
    Object processor P2 does not apply — CommunityObject is a
    SpecElement, not a community body item.
    """
    name:        str            = ""
    description: Optional[str] = None
    abstracts:   Optional[object] = None   # → Community/Domain/Federation ref


@dataclass
class Domain(Community):
    """§7.5.1 — <X>-domain community type.

    AM-25: inherits Community (§7.5 — domain IS a community type), so Domain
    instances satisfy [Community] cross-references in MemberRef via isinstance.
    name, description, policy_refs, events, invariants are inherited from
    Community and not redeclared here.

    Grammar rule: Domain
    Object processor (P8) splits body_items.
    """
    # Domain-specific fields only — Community fields inherited above
    relationship:        Optional[str] = None   # characterized_by
    body_items:          List = field(default_factory=list)  # raw; P8 splits
    controlling_objects:  List = field(default_factory=list)  # List[EnterpriseObject]
    controlled_objects:   List = field(default_factory=list)  # List[EnterpriseObject]
    normative_policies:   List = field(default_factory=list)  # List[NormativePolicy] (AM-28)


@dataclass
class FedSharedObjective(_ELParentable):
    """Grammar rule: FedSharedObjective — wrapper dissolved by P9."""
    description: str = ""

@dataclass
class MemberRef(_ELParentable):
    """Federation member reference — §7.5.2.

    Links a community to the federation, optionally specifying
    which CommunityObject represents it and which federation role it fills.
    P9 stores MemberRef objects directly in Federation.members (not dissolved).
    """
    community:      Optional[object] = None   # → Community/Domain ref
    represented_by: Optional[object] = None   # → CommunityObject (AM-26)
    fills:          Optional[object] = None   # → Role (federation role, AM-26)

@dataclass
class WithdrawalBehaviour(_ELParentable):
    """Grammar rule: WithdrawalBehaviour — wrapper dissolved by P9."""
    description: str = ""


@dataclass
class ConflictResolution(_ELParentable):
    """§7.9.2 NOTE 3 — federation conflict resolution strategy.

    Grammar rule: ConflictResolutionDecl
    """
    kind:        str            = ""    # ConflictResolutionKind
    description: Optional[str] = None


@dataclass
class Federation(_ELParentable):
    """§7.5.2, §7.9.2 — federation of pre-existing communities.

    AM-25: contract qualifier, mandatory objective (§7.7), and events list added.

    Grammar rule: Federation
    Object processor (P9) splits body_items.
    """
    contract:    bool           = False               # AM-25: optional 'contract' qualifier
    name:        str            = ""
    description: Optional[str] = None
    objective:   Optional[Objective] = None           # AM-25: mandatory per §7.7; set by grammar directly
    body_items:  List           = field(default_factory=list)  # raw; P9 splits

    # Populated by object processor P9:
    roles:                List = field(default_factory=list)  # List[Role] (AM-26)
    shared_objectives:    List = field(default_factory=list)  # List[str]
    members:              List = field(default_factory=list)  # List[MemberRef] (AM-26)
    policy_refs:          List = field(default_factory=list)  # List[PolicyRef]
    invariants:           List = field(default_factory=list)  # List[Invariant]
    events:               List = field(default_factory=list)  # AM-25: List[EventDecl]
    normative_policies:   List = field(default_factory=list)  # List[NormativePolicy] (AM-28)
    withdrawal_behaviour: Optional[str] = None
    conflict_resolution:  Optional[ConflictResolution] = None


# ---------------------------------------------------------------------------
# Group I — Accountability speech acts
# ---------------------------------------------------------------------------

@dataclass
class Commitment(_ELParentable):
    """§6.6.2, §7.10.3 — speech act creating an obligation.

    Grammar rule: CommitmentDecl
    The created burden is the root anchor for delegation chain tracing.
    V-10: actor must be a party.
    V-15: every delegation obligation must trace to a root commitment.
    """
    name:        str            = ""
    actor:       Optional[object] = None   # → EnterpriseObject (party)
    obligation:  str            = ""
    burden:      Optional[object] = None   # → DeonticToken (burden)
    principals:  List           = field(default_factory=list)  # List[EnterpriseObject]
    description: Optional[str] = None


@dataclass
class Delegation(_ELParentable):
    """§6.6.6, §7.10.1 — speech act transferring obligation to an agent.

    Grammar rule: DelegationDecl
    Key construct for accountability chain reasoning.
    """
    name:                    str            = ""
    delegator:               Optional[object] = None   # → EnterpriseObject
    delegate:                Optional[object] = None   # → EnterpriseObject
    obligation:              str            = ""
    burden:                  Optional[object] = None   # → DeonticToken
    token_group:             Optional[object] = None   # → TokenGroup
    creates_reporting_burden: bool          = False
    duration:                Optional[str] = None
    conditions:              Optional[str] = None
    sub_delegation_allowed:  bool          = False
    revocable:               bool          = False
    description:             Optional[str] = None


@dataclass
class Authorization(_ELParentable):
    """§6.6.4, §7.10.2, §7.8.8.4 — speech act granting a permission.

    Grammar rule: AuthorizationDecl
    An empowerment (unlike mere permission): authority grants a permit
    AND undertakes a burden to facilitate.
    """
    name:                  str            = ""
    authority:             Optional[object] = None   # → EnterpriseObject
    authorized_agent:      Optional[object] = None   # → EnterpriseObject
    permit:                Optional[object] = None   # → DeonticToken (permit)
    auth_burden:           Optional[object] = None   # → DeonticToken (burden)
    duration:              Optional[str]   = None
    conditions:            Optional[str]   = None
    sub_delegation_allowed: bool           = False
    revocable:             bool            = False
    domain_scope:          Optional[str]   = None
    description:           Optional[str]   = None


@dataclass
class Prescription(_ELParentable):
    """§6.6.3, §7.10.5 — speech act establishing a rule.

    Grammar rule: PrescriptionDecl
    Actor must be a party by nature, or delegated the permit to prescribe.
    """
    name:                    str            = ""
    actor:                   Optional[object] = None   # → EnterpriseObject
    rule_text:               str            = ""
    permit:                  Optional[object] = None   # → DeonticToken
    creates_oversight_burden: bool          = False
    description:             Optional[str] = None


@dataclass
class Declaration(_ELParentable):
    """§6.6.5, §7.10.4 — speech act establishing a state of affairs.

    Grammar rule: DeclarationDecl
    Requires a permit; effective only after an interaction.
    """
    name:                   str            = ""
    actor:                  Optional[object] = None   # → EnterpriseObject
    state_of_affairs:       str            = ""
    permit:                 Optional[object] = None   # → DeonticToken
    effective_on_interaction: bool         = False
    description:            Optional[str] = None


@dataclass
class Evaluation(_ELParentable):
    """§6.6.7 — assessment of value or system state.

    Grammar rule: EvaluationDecl
    """
    name:        str            = ""
    evaluator:   Optional[object] = None   # → EnterpriseObject
    target:      str            = ""
    result:      str            = ""
    description: Optional[str] = None


@dataclass
class ViolationResponse(_ELParentable):
    """§6.3.8, §7.8.6, §7.8.6 NOTE 2 — prescribed obligation upon violation.

    Grammar rule: ViolationResponseDecl (AM-17)

    §7.8.6 NOTE 2: "A rule prescribing types of actions to be taken by
    an object in the event of certain types of violations. That rule is
    an obligation, which applies to that object."

    The violation response is itself a burden on the responding actor.
    V-NEW-15: violated_burden must be a burden token (not permit/embargo).
    V-NEW-16: if response_kind is escalate, escalate_to must be a party.
    """
    name:             str            = ""
    violated_burden:  Optional[object] = None   # → DeonticToken (burden)
    responding_actor: Optional[object] = None   # → EnterpriseObject
    response_kind:    str            = ""        # ViolationResponseKind
    creates_burden:   Optional[object] = None   # → DeonticToken
    escalate_to:      Optional[object] = None   # → EnterpriseObject (party)
    description:      Optional[str]   = None


# ---------------------------------------------------------------------------
# Group J — Viewpoint correspondences
# ---------------------------------------------------------------------------

@dataclass
class Correspondence(_ELParentable):
    """§11.2–11.5 — correspondence between enterprise and other viewpoints.

    Grammar rule: CorrespondenceDecl
    enterprise_concept is a plain ID — known design debt (could be cross-ref).
    """
    enterprise_concept: str            = ""
    viewpoint:          str            = ""    # ViewpointName
    viewpoint_concept:  str            = ""
    description:        Optional[str] = None


# ---------------------------------------------------------------------------
# Class registry for textX registration (Step 3)
# ---------------------------------------------------------------------------

# All classes that textX needs to instantiate during parsing.
# Pass this list as: metamodel_from_file(grammar_path, classes=DOMAIN_CLASSES)
#
# Order does not matter for textX — it matches by class name against grammar
# rule names. The grammar rule name must equal the class name exactly, with
# one exception: EnterpriseObject is registered against EnterpriseObjectDecl
# (handled via textX obj_class parameter or renaming — confirm with Igor
# before Step 3).

DOMAIN_CLASSES = [
    # A
    EnterpriseSpec,
    # B
    EnterpriseObject, ObjectBody, DelegatedFrom, PrincipalOf, HoldsToken,
    # C
    DeonticToken, TokenGroup, TokenGroupMember,
    # D
    Policy, PolicyRule, AffectedElement, SettingBehaviour, Enforcement,
    PolicyRef,
    NormativePolicy, NormativePolicyRef,  # AM-28
    Duration, NumberInterval, EnvelopeRule, PolicyEnvelope,  # AM-23
    # E
    Community, EventDecl, SatisfactionCondition, SatisfactionArg, Objective, SubObjective, SubObjectiveRef, Invariant,
    AssignmentPolicy, RequiresCapabilityRule, ExcludesRoleRule,
    RequiresTokenRule, RequiresRelationRule,
    JoinLeaveEffect, CommunityInteraction,
    # F
    Role, InlineToken, Action, EmitsDecl, ConditionalAction, Process, Step,
    DeonticRequirement, DeonticEffect, PreconditionDecl,
    DescriptionAttr, ActorRef, ArtefactRef, ResourceRef,
    RequiresPermitItem, InhibitedByItem, FavouredByItem,
    SatisfiesObjective,
    # G
    Lifecycle, Establishing, EmbeddedCommitment, Changes, Terminating,
    # H
    CommunityObject,
    Domain, DomainControllingObj, DomainControlledObj,
    Federation, FedSharedObjective, MemberRef, WithdrawalBehaviour,
    ConflictResolution,
    # I
    Commitment, Delegation, Authorization, Prescription, Declaration,
    Evaluation, ViolationResponse,
    # J
    Correspondence,
]
