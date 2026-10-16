// expect: envelope-membership
// 12% is not one of the envelope's values.
enterprise specification EnvelopeMembershipInvalid

policy MaximumShare : percentage {
    initial_value: 12%
    envelope { one of [5%, 10%, 15%] }
}
