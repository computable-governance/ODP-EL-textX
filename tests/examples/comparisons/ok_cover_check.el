// expect: ok
// 2.1.0 comparisons: a cover check at assessment time against a policy,
// and a share limit against a literal. Parses and validates cleanly.
enterprise specification CoverCheckOk

policy MinimumCover : amount {
    initial_value: 20000000 AUD
    envelope { range of [10000000 AUD to 50000000 AUD] }
}

policy MaximumShare : percentage {
    initial_value: 10%
    envelope { one of [5%, 10%, 15%] }
}

party Assessor

community Engagement {
    objective: "engage only suppliers with enough cover"
    Assessor fills assessorRole
    role assessorRole {
        action assess {
            actor: assessorRole
            precondition: "insurance cover" >= MinimumCover
        }
        action approveSubcontract {
            actor: assessorRole
            precondition: "subcontract share" <= 10%
        }
    }
}
