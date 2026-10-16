// expect: comparison-type
// "60 day" reads as an amount with currency code 'day'; a duration
// cannot be compared, and 'day' is not an ISO 4217 code.
enterprise specification ComparisonTypeInvalid

party Assessor

community Engagement {
    objective: "probe"
    Assessor fills assessorRole
    role assessorRole {
        action assess {
            actor: assessorRole
            precondition: "response time" <= 60 day
        }
    }
}
