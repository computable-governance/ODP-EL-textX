// expect: standing-in-group
// A standing duty is never discharged by an action, so it cannot be a
// member of a token group.
enterprise specification StandingInGroupInvalid

policy ContractEnd : instant { initial_value: 2027-06-30T17:00+10:00 }

party Supplier { holds keepCover holds fileReport }

burden keepCover {
    standing
    keeps: "insurance cover" >= 20000000 AUD
    ends_at: ContractEnd
    state: active
}

burden fileReport { for_action: "file" state: active deadline: "30 days" }

token_group obligations {
    member: keepCover
    member: fileReport
}
