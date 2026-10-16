// expect: ok
// 2.1.0 typed policy values: one policy per value type, each with an
// envelope where the type is ordered. Parses and validates cleanly.
enterprise specification TypedValuesOk

policy MaxRetries : integer {
    initial_value: 3
    envelope { range of [0 to 10] }
}

policy Ratio : decimal {
    initial_value: 0.75
    envelope { range of [0 to 1.00] }
}

policy Score : number {
    initial_value: 4
}

policy InterestRate : percentage {
    initial_value: 4.25%
    envelope { range of [0% to 6%] }
}

policy ReferralFee : amount {
    initial_value: 250.00 AUD
    envelope { range of [10.00 AUD to 500 AUD] }
}

policy ServiceLabel : string {
    initial_value: "standard"
}

policy AuditEnabled : boolean {
    initial_value: true
}

policy RetentionWindow : duration {
    initial_value: 60 days
    envelope { range of [4 weeks to 1 year] }
}

policy Cutoff : date {
    initial_value: 2026-11-30
    envelope { range of [2026-01-01 to 2026-12-31] }
}

policy Opens : instant {
    initial_value: 2026-11-30T17:00+10:00
    envelope { range of [2026-11-30T07:00Z to 2026-11-30T08:00+01:00] }
}

policy ServiceTier : TierOptions {
    initial_value: gold
    envelope { one of [bronze, silver, gold] }
}
