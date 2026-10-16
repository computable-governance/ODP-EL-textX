// expect: standing-fields
// A strict standing duty would block the clock and be reported compelled
// by a discharge the engine never makes.
enterprise specification StandingFieldsInvalid

policy ContractEnd : instant { initial_value: 2027-06-30T17:00+10:00 }

party Supplier { holds keepCover }

burden keepCover {
    standing
    keeps: "insurance cover" >= 20000000 AUD
    ends_at: ContractEnd
    state: active
    discharge_mode: strict
}
