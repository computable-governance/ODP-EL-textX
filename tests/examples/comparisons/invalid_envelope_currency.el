// expect: envelope-currency
// The initial value is in AUD, the envelope in NZD; amounts are never
// converted.
enterprise specification EnvelopeCurrencyInvalid

policy MinimumCover : amount {
    initial_value: 20000000 AUD
    envelope { range of [10000000 NZD to 50000000 NZD] }
}
