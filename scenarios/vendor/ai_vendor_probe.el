/*
 * ================================================================
 * ai_vendor_probe.el
 * ODP Enterprise Language DSL — AIVendor two-construct probe
 * (peer contract federation + subordination domain, N-peer provenance)
 *
 * Purpose: closes the AM-40 loop. AM-40 (2026-07-19/21) added Domain's
 * role-based controlling_role/controlled_role/DomainRoleFiller syntax
 * (with via=[Federation] provenance) to fix a grammar/standard mismatch
 * — §7.5.1 describes controlling/controlled object as ROLES, not fixed
 * object slots. AM-40's grammar, parser, and validator (V-NEW-21) all
 * landed with 5 passing unit tests, but nothing had ever used it in a
 * real named scenario — this file is that missing piece, and the first
 * live exercise of the AIVendor gap identified 2026-07-09
 * (docs/CONCEPTS_INDEX.md).
 *
 * The gap: a GP practice's deployed AI agents are supplied by
 * independent AI vendors. Privacy/AI regulation treats "the vendor who
 * built/supplies the system" and "the system as deployed/operated" as
 * legally distinct roles — EU AI Act's provider/deployer split, GDPR's
 * controller/processor split, HIPAA's covered-entity/business-associate
 * split all draw the same line. Two ODP constructs, not one:
 *
 *   - PEER layer: each vendor's supply relationship with the practice
 *     is a standing, negotiated contract federation (pre-deployment
 *     provider duty) — same pattern as ReferralNetworkFederation.
 *   - SUBORDINATION layer: each vendor's deployed agent, once running,
 *     is a controlled object under the practice's domain authority
 *     (in-use processor duty) — but WHICH federation authorized WHICH
 *     deployed agent must be traceable once there is more than one
 *     vendor. That's what via=[Federation] is for.
 *
 * Deliberately N=2 vendors, not 1:1 — proving the multi-peer case is
 * the whole point (per Pieter van Schalkwyk's industrial N-peer
 * motivating case, docs/CONCEPTS_INDEX.md, 2026-07-14 update), not an
 * afterthought bolted onto a single-vendor example.
 *
 * Deliberately uses ONLY the new role-based syntax — proving it alone
 * is sufficient to pass V-NEW-21, not exercising the coexisting old
 * flat controlling_object/controlled_object syntax that
 * PatientDataAuthorshipDomain/PatientDataConsentDomain still use (that
 * migration remains separately deferred, per AM-40's own entry).
 * ================================================================
 */

enterprise specification AIVendorProbe
    description: "Two independent AI vendors supply a GP practice with deployed diagnostic agents; peer contract federations carry the pre-deployment provider duty, a shared subordination domain carries the in-use processor duty, and via=[Federation] traces each deployed agent back to whichever vendor federation authorized it"

party GPPractice
    description: "GP practice; controlling authority for both deployed AI agents' in-use governance"

agent DiagnosticImagingAIAgent
    description: "Deployed diagnostic-imaging AI agent, supplied by AIVendorAlpha"

agent TriageAIAgent
    description: "Deployed triage-support AI agent, supplied by AIVendorBeta"

// ================================================================
// §6.2.2, §7.4 — COMMUNITIES (peer-federation participants)
// ================================================================

community GPPracticeCommunity
    description: "GP practice as a peer-federation participant"
    {
        objective: "Maintain governed AI vendor supply relationships"
    }

community AIVendorAlphaCommunity
    description: "First AI vendor, supplying the diagnostic-imaging agent"
    {
        objective: "Supply and support a conformant diagnostic-imaging AI system"
    }

community AIVendorBetaCommunity
    description: "Second AI vendor, supplying the triage-support agent"
    {
        objective: "Supply and support a conformant triage-support AI system"
    }

community_object GPPracticeObj
    description: "Community object representing GPPracticeCommunity in vendor supply federations"
    {
        abstracts: GPPracticeCommunity
    }

community_object AIVendorAlphaObj
    description: "Community object representing AIVendorAlphaCommunity in its supply federation"
    {
        abstracts: AIVendorAlphaCommunity
    }

community_object AIVendorBetaObj
    description: "Community object representing AIVendorBetaCommunity in its supply federation"
    {
        abstracts: AIVendorBetaCommunity
    }

// ================================================================
// §7.9 — NORMATIVE POLICY (shared regulatory grounding)
// ================================================================

normative_policy AIVendorProviderDeployerSplit {
    description: "EU AI Act's provider/deployer split (mirrored by GDPR controller/processor, HIPAA covered-entity/business-associate) underlying the peer/subordination two-construct shape"
    source: "EU AI Act (Regulation (EU) 2024/1689), Articles 3(3) 'provider' and 3(4) 'deployer'"
    kind: regulation
    type: string
    initial_value: "Provider (vendor, pre-deployment conformance duty) and deployer (practice, in-use operational duty) are distinct legal roles"
    policy_setting_behaviour: "EU legislative amendment / implementing act"
}

// ================================================================
// §7.5.2, §7.9.2 — PEER LAYER: two independent supply federations
// (pre-deployment provider duty; EU AI Act "provider" role)
// ================================================================

contract federation AIVendorAlphaSupplyFederation
    description: "Standing supply contract between GP practice and AIVendorAlpha"
    {
        objective: "Ensure conformant supply of the diagnostic-imaging AI system"

        normative_policy: AIVendorProviderDeployerSplit

        member: GPPracticeCommunity represented_by GPPracticeObj
        member: AIVendorAlphaCommunity represented_by AIVendorAlphaObj
    }

contract federation AIVendorBetaSupplyFederation
    description: "Standing supply contract between GP practice and AIVendorBeta"
    {
        objective: "Ensure conformant supply of the triage-support AI system"

        normative_policy: AIVendorProviderDeployerSplit

        member: GPPracticeCommunity represented_by GPPracticeObj
        member: AIVendorBetaCommunity represented_by AIVendorBetaObj
    }

// ================================================================
// §7.5.1 (AM-40) — SUBORDINATION LAYER: one shared domain,
// N vendors' deployed agents, each traced via=[Federation]
// (in-use processor duty; EU AI Act "deployer" role)
// ================================================================

domain AIVendorGovernanceDomain
    characterized_by: "Data controller-processor relationship over deployed AI agents from multiple vendors"
    description: "GP practice as controlling authority over both deployed AI agents, regardless of which vendor supplied them"
    {
        controlling_role role practiceAuthority
            description: "GP practice's controlling authority over deployed AI agents"
            {}

        controlled_role role deployedAIAgent
            description: "A deployed AI agent operating under the practice's authority"
            {}

        GPPractice fills practiceAuthority
        DiagnosticImagingAIAgent fills deployedAIAgent via AIVendorAlphaSupplyFederation
        TriageAIAgent fills deployedAIAgent via AIVendorBetaSupplyFederation

        normative_policy: AIVendorProviderDeployerSplit
    }
