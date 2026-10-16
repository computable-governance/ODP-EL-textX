// expect: comparison-in-step
// Step preconditions are not enforced, so this comparison checks nothing.
enterprise specification ComparisonInStepInvalid

party Assessor

community Engagement {
    objective: "probe"
    Assessor fills assessorRole
    role assessorRole {
        action assess { actor: assessorRole }
    }
    process Onboarding {
        initiates: "request received"
        terminates: "assessment recorded"
        step assess {
            actor: assessorRole
            precondition: "insurance cover" >= 20000000 AUD
        }
    }
}
