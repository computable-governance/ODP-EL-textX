// expect: ok
// 2.1.0 standing duties: insurance cover and a subcontract share kept for
// the life of the contract, from its signing until its end date or its
// termination. Parses and validates cleanly.
enterprise specification CoverForTheTermOk

policy MinimumCover : amount { initial_value: 20000000 AUD }
policy MaximumShare : percentage { initial_value: 10% }
policy ContractEnd : instant { initial_value: 2027-06-30T17:00+10:00 }

party Supplier {
    holds keepCover
    holds keepShare
}

burden keepCover {
    standing
    keeps: "insurance cover" >= MinimumCover
    ends_at: ContractEnd
    ended_by: contractTerminated
    state: pending
    triggered_by: contractSigned
}

burden keepShare {
    standing
    keeps: "subcontract share" <= MaximumShare
    ends_at: ContractEnd
    ended_by: contractTerminated
    state: pending
    triggered_by: contractSigned
}

community Contract {
    objective: "the supplier keeps cover and limits subcontracting for the term"
    event contractSigned
    event contractTerminated
    Supplier fills supplierRole
    role supplierRole {
        action sign { actor: supplierRole emits: contractSigned }
        action terminate { actor: supplierRole emits: contractTerminated }
    }
}
