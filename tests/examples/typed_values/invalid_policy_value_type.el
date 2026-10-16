// expect: policy-value-type
// An integer policy whose value is a decimal.
enterprise specification TypedValuesWrongType

policy MaxRetries : integer {
    initial_value: 4.5
}
