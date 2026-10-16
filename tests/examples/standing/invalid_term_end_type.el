// expect: term-end-type
// The term must end at a date or an instant, not a duration policy.
enterprise specification TermEndTypeInvalid

policy ContractLength : duration { initial_value: 365 days }

party Supplier { holds keepCover }

burden keepCover {
    standing
    keeps: "insurance cover" >= 20000000 AUD
    ends_at: ContractLength
    state: active
}
