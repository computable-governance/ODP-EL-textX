"""
Task Group exclusion verification (toolchain/fhir_mapper.py's
TASK_GROUP_PROFILE filter in map_bundle(), ~line 672).

A Task Group resource (AU eRequesting Task Group profile,
`.../StructureDefinition/au-erequesting-task-group`) populates
requester/owner identically to its child fulfilment Task — same
PractitionerRole, same Organization, restated at container level, not a
different party. Confirmed 2026-09-12 against the real published AU
eRequesting IG examples (build v1.0.1, hl7.org.au) — reproduced verbatim
below, not invented:

  Task-taskgroup-imaging-1        — the Task Group (excluded)
  Task-taskfulfilment-imaging-1   — its child fulfilment Task, linked via
                                     partOf: Task/taskgroup-imaging-1
                                     (mapped normally)

Both examples' `requester`/`owner` are identical
(PractitionerRole/generalpractitioner-guthridge-jarred,
Organization/mount-charlton-radiology) — mapping both would produce two
delegations for what is really one governance-relevant relationship.
`meta.profile` is the only structural marker distinguishing the two
(the fulfilment Task carries
`.../StructureDefinition/au-erequesting-task-diagnosticrequest` instead).

PractitionerRole/generalpractitioner-guthridge-jarred's real
`.organization` (confirmed live against localhost:8081/fhir, same
session) is Organization/elimbah-medical-centre — reused here as the
fetched value, not guessed.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"

sys.path.insert(0, str(TOOLCHAIN))

from fhir_mapper import FHIRConsentMapper  # noqa: E402

# Reproduced verbatim from https://hl7.org.au/fhir/ereq/1.0.1/
# Task-taskgroup-imaging-1.json.html (fetched 2026-09-12). Narrative
# `text.div` omitted — boilerplate HTML the mapper never reads.
TASK_GROUP_IMAGING_1 = {
    "resourceType": "Task",
    "id": "taskgroup-imaging-1",
    "meta": {
        "profile": [
            "http://hl7.org.au/fhir/ereq/StructureDefinition/au-erequesting-task-group"
        ],
        "tag": [
            {"system": "http://terminology.hl7.org.au/CodeSystem/resource-tag",
             "code": "fulfilment-task-group"}
        ],
    },
    "groupIdentifier": {
        "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "PGN"}],
                  "text": "Placer Group Number"},
        "system": "http://ns.electronichealth.net.au/id/hpio-scoped/order/1.0/8003622500032165",
        "value": "EMC4542244-5624",
        "assigner": {"reference": "Organization/elimbah-medical-centre", "display": "Elimbah Medical Centre"},
    },
    "status": "requested",
    "statusReason": {"text": "confirmed booking with Mount Charlton Radiology reception"},
    "businessStatus": {"coding": [{"system": "http://terminology.hl7.org.au/CodeSystem/task-business-status",
                                    "code": "service-booked"}]},
    "intent": "order",
    "priority": "urgent",
    "code": {"coding": [{"system": "http://hl7.org/fhir/CodeSystem/task-code", "code": "fulfill"}]},
    "for": {"reference": "Patient/roberts-fred"},
    "authoredOn": "2024-05-11",
    "lastModified": "2024-05-11",
    "requester": {"reference": "PractitionerRole/generalpractitioner-guthridge-jarred"},
    "owner": {"reference": "Organization/mount-charlton-radiology"},
}

# Reproduced verbatim from https://hl7.org.au/fhir/ereq/1.0.1/
# Task-taskfulfilment-imaging-1.json.html (fetched 2026-09-12).
TASK_FULFILMENT_IMAGING_1 = {
    "resourceType": "Task",
    "id": "taskfulfilment-imaging-1",
    "meta": {
        "profile": [
            "http://hl7.org.au/fhir/ereq/StructureDefinition/au-erequesting-task-diagnosticrequest"
        ],
        "tag": [
            {"system": "http://terminology.hl7.org.au/CodeSystem/resource-tag", "code": "fulfilment-task"}
        ],
    },
    "identifier": [
        {"type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "PLAC",
                               "display": "Placer Identifier"}]},
         "system": "http://ns.electronichealth.net.au/id/hpio-scoped/order/1.0/8003622500032165",
         "value": "EMC4542244-5624-1",
         "assigner": {"reference": "Organization/elimbah-medical-centre", "display": "Elimbah Medical Centre"}}
    ],
    "groupIdentifier": {
        "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "PGN"}],
                  "text": "Placer Group Number"},
        "system": "http://ns.electronichealth.net.au/id/hpio-scoped/order/1.0/8003622500032165",
        "value": "EMC4542244-5624",
        "assigner": {"reference": "Organization/elimbah-medical-centre", "display": "Elimbah Medical Centre"},
    },
    "partOf": [{"reference": "Task/taskgroup-imaging-1"}],
    "status": "requested",
    "businessStatus": {"coding": [{"system": "http://terminology.hl7.org.au/CodeSystem/task-business-status",
                                    "code": "service-booked"}]},
    "intent": "order",
    "priority": "routine",
    "code": {"coding": [{"system": "http://hl7.org/fhir/CodeSystem/task-code", "code": "fulfill"}]},
    "focus": {"reference": "ServiceRequest/order-xray-1"},
    "for": {"reference": "Patient/roberts-fred"},
    "authoredOn": "2024-05-11",
    "requester": {"reference": "PractitionerRole/generalpractitioner-guthridge-jarred"},
    "owner": {"reference": "Organization/mount-charlton-radiology"},
}

# PractitionerRole/generalpractitioner-guthridge-jarred, real .organization
# confirmed live against localhost:8081/fhir this session (not guessed).
PRACTITIONER_ROLE = {
    "resourceType": "PractitionerRole",
    "id": "generalpractitioner-guthridge-jarred",
    "practitioner": {"reference": "Practitioner/guthridge-jarred"},
    "organization": {"reference": "Organization/elimbah-medical-centre"},
}

MOUNT_CHARLTON_RADIOLOGY = {
    "resourceType": "Organization",
    "id": "mount-charlton-radiology",
    "name": "Mount Charlton Radiology",
}

PATIENT_ROBERTS_FRED = {
    "resourceType": "Patient",
    "id": "roberts-fred",
    "name": [{"family": "Roberts", "given": ["Fred"]}],
}


def _bundle() -> dict:
    return {
        "resourceType": "Bundle",
        "id": "task-group-exclusion-probe",
        "entry": [
            {"resource": PRACTITIONER_ROLE},
            {"resource": MOUNT_CHARLTON_RADIOLOGY},
            {"resource": PATIENT_ROBERTS_FRED},
            {"resource": TASK_GROUP_IMAGING_1},
            {"resource": TASK_FULFILMENT_IMAGING_1},
        ],
    }


def test_exactly_one_delegation_produced():
    """Only the fulfilment Task produces a delegation; the Task Group is
    excluded before _map_task ever sees it."""
    el = _map_bundle_text()
    assert el.count("delegation ") == 1


def test_no_delegation_for_task_group_id():
    """No delegation exists whose el_id derives from Task/taskgroup-imaging-1
    (the Task Group's own id) — only from Task/taskfulfilment-imaging-1."""
    el = _map_bundle_text()
    assert "TaskgroupImaging1Delegation" not in el
    assert "delegation TaskfulfilmentImaging1Delegation {" in el


def test_the_one_delegation_resolves_correctly():
    """The surviving delegation (from the fulfilment Task) resolves
    from/to correctly: requester's PractitionerRole -> its real
    .organization (ElimbahMedicalCentre), owner -> MountCharltonRadiology
    directly."""
    el = _map_bundle_text()
    block = el.split("delegation TaskfulfilmentImaging1Delegation {")[1].split("}")[0]
    assert "from: ElimbahMedicalCentre" in block
    assert "to: MountCharltonRadiology" in block


def _map_bundle_text() -> str:
    mapper = FHIRConsentMapper()
    return mapper.map_bundle(_bundle())
