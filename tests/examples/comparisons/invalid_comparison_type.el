// expect: comparison-type
// "60 sec" reads as an amount with currency code 'sec' (sec is not a
// duration unit), and 'sec' is not an ISO 4217 code.
enterprise specification ComparisonTypeInvalid

party Assessor

community Engagement {
    objective: "probe"
    Assessor fills assessorRole
    role assessorRole {
        action assess {
            actor: assessorRole
            precondition: "response time" <= 60 sec
        }
    }
}
