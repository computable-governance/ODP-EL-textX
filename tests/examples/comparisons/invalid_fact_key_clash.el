// expect: fact-key-clash
// 'insurance cover' is read as a plain fact in one action and as an
// amount in another; one reported value cannot satisfy both.
enterprise specification FactKeyClashInvalid

party Assessor

community Engagement {
    objective: "probe"
    Assessor fills assessorRole
    role assessorRole {
        action assess {
            actor: assessorRole
            precondition: "insurance cover" >= 20000000 AUD
        }
        action renew {
            actor: assessorRole
            precondition: "insurance cover"
        }
    }
}
