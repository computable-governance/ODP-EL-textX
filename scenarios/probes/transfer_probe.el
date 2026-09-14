/*
 * transfer_probe.el — AM-82 probe.
 *
 * Exercises the `effect transfer` DeonticEffect (§6.4.7/§7.8.7) at the
 * Kripke layer (Rule T9). There is zero live usage of this DeonticEffect
 * anywhere in referral_scenario.el (confirmed: grep -n "effect.*transfer"
 * returns nothing there), so this probe exists purely to give T9 a real
 * spec to BFS over.
 *
 * Covers the happy path plus every T9 skip case in one file, each via
 * its own Burden/Action pair so they can be exercised independently:
 *   - performTransfer            : happy path — roleA (ActorA) -> roleB
 *                                   (ActorB), both resolve to exactly
 *                                   one actor.
 *   - transferNoFromRole         : no `from` clause at all — skipped,
 *                                   no live acting-actor to fall back on.
 *   - transferAmbiguousFrom      : `from: roleC`, filled by BOTH ActorC
 *                                   and ActorD — skipped, not exactly
 *                                   one actor.
 *   - transferUnfilledTo         : `to: roleUnfilled`, filled by nobody
 *                                   — skipped, zero actors.
 *   - transferPermitKind         : token is a Permit, not a Burden —
 *                                   skipped, out of scope for T9.
 *
 * Role membership (which actor fills which role) is NOT expressible in
 * this grammar — there is no "fills"/"member" binding construct, only
 * descriptive `actor: roleX` on an Action (see grammar comment, DOC-03:
 * "these classify how objects participate in one action execution; they
 * do NOT define structural positions in a community"). Role membership
 * is assigned in Python by the test that builds this probe's runtime,
 * via el_engine.enroll(state, actor_name, role_name=...) — the same
 * pattern el_api.py's own scenario builders use.
 *
 * Probe tier (scenarios/README.md): disposable by design. Success means
 * T9's lesson is absorbed as a settled Kripke rule; this file is not
 * expected to be touched again afterward.
 */

enterprise specification TransferProbe

party ActorA {
    holds probeBurden
    holds noFromRoleBurden
    holds ambiguousFromBurden
    holds unfilledToBurden
    holds probePermit
    holds strictBurden
}

party ActorB {}
party ActorC {}
party ActorD {}

burden probeBurden {
    state: active
    discharge_mode: eventual
    description: "Probe obligation, initially held by whoever fills roleA"
}

burden noFromRoleBurden {
    state: active
    discharge_mode: eventual
    description: "Probe obligation for the no-from_role T9 skip case"
}

burden ambiguousFromBurden {
    state: active
    discharge_mode: eventual
    description: "Probe obligation for the multiple-actors-fill-from_role T9 skip case"
}

burden unfilledToBurden {
    state: active
    discharge_mode: eventual
    description: "Probe obligation for the zero-actors-fill-to_role T9 skip case"
}

permit probePermit {
    state: active
    description: "Probe permit for the Permit-kind-token T9 skip case"
}

burden strictBurden {
    state: active
    discharge_mode: strict
    priority: critical
    description: "Outstanding strict burden — must be discharged before T9 (or any other instantaneous rule sharing strict_burden_blocks()) can fire, same guard as T4/T7/T8"
}

commitment probeCommitment {
    by: ActorA
    obligation: "Hold probeBurden until transferred to roleB's filler"
    creates_burden: probeBurden
}

commitment noFromRoleCommitment {
    by: ActorA
    obligation: "Probe: no-from_role skip case"
    creates_burden: noFromRoleBurden
}

commitment ambiguousFromCommitment {
    by: ActorA
    obligation: "Probe: ambiguous from_role skip case"
    creates_burden: ambiguousFromBurden
}

commitment unfilledToCommitment {
    by: ActorA
    obligation: "Probe: unfilled to_role skip case"
    creates_burden: unfilledToBurden
}

commitment strictCommitment {
    by: ActorA
    obligation: "Probe: strict-burden-blocking guard case"
    creates_burden: strictBurden
}

community TransferProbeCommunity {
    objective: "Demonstrate a Burden transfer via a Community Action's DeonticEffect(transfer), plus every T9 skip case — AM-82/T9"

    role roleA
        description: "Initial holder of every probe Burden above"
        {
            action performTransfer {
                description: "Happy path: transfers probeBurden from roleA's filler to roleB's filler"
                actor: roleA
                effect transfer probeBurden from roleA to roleB
            }

            action transferNoFromRole {
                description: "Skip case: no from_role at all"
                actor: roleA
                effect transfer noFromRoleBurden to roleB
            }

            action transferAmbiguousFrom {
                description: "Skip case: from_role (roleC) resolves to more than one actor"
                actor: roleA
                effect transfer ambiguousFromBurden from roleC to roleB
            }

            action transferUnfilledTo {
                description: "Skip case: to_role (roleUnfilled) resolves to zero actors"
                actor: roleA
                effect transfer unfilledToBurden from roleA to roleUnfilled
            }

            action transferPermitKind {
                description: "Skip case: token is a Permit, not a Burden"
                actor: roleA
                effect transfer probePermit from roleA to roleB
            }
        }

    role roleB
        description: "Target holder role"
        {}

    role roleC
        description: "Filled by two actors (ActorC, ActorD) — ambiguous from_role"
        {}

    role roleUnfilled
        description: "Filled by nobody — unresolvable to_role"
        {}
}
