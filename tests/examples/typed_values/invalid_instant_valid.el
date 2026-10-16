// expect: instant-valid
// A UTC offset of 24 hours is out of range.
enterprise specification TypedValuesBadOffset

policy Opens : instant {
    initial_value: 2026-11-30T17:00+24:00
}
