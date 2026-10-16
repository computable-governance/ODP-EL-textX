// expect: range-ends
// Amounts in different currencies are never converted, so a range
// whose ends are in AUD and NZD cannot be ordered.
enterprise specification TypedValuesMixedCurrencies

policy ReferralFee : amount {
    initial_value: 250.00 AUD
    envelope { range of [10.00 AUD to 500.00 NZD] }
}
