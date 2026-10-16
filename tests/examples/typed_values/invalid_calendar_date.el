// expect: calendar-date
// 30 February is not a calendar date.
enterprise specification TypedValuesNoSuchDate

policy Cutoff : date {
    initial_value: 2026-02-30
}
