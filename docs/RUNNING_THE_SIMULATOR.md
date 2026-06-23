The scenario switcher button at the top of each widget switches the API
runtime between gp_referral and ereferral. For demos, open each widget
in its own browser tab.

## Demo guide — clinical governance audience (eReferral widget)

### 1. The compelled/detectable distinction
Point to the blue COMPELLED badge on Referral Submission vs the amber
DETECTABLE badges on Specialist Examination and AI Diagnostic Examination.

Key message: the architecture makes the referral submission impossible to
skip (discharge_mode: strict — AF in CTL). The specialist and AI obligations
are monitored after the fact (discharge_mode: eventual — EF in CTL). If
either is violated, the violation response is shown directly on the card:
escalation to GP Practice for the specialist, remediation by Specialist
Clinician for the AI agent.

### 2. The happy path
Walk through all five actions in sequence:
1. GP Clinician — Submit Referral
2. Specialist Clinician — Acknowledge Referral
3. Specialist Clinician — Schedule Assessment
4. AI Diagnostic Agent — Conduct AI Examination

The progress bar advances and Worlds checked shrinks (72 → 64 → 24 → 22 → 1),
showing the Kripke model converging to a single terminal world as actions
are executed and futures close off.

### 3. The AI agent as a governed participant
SpecialistAIAgent has obligations just like the human clinicians. Its
examination burden is detectable — the system monitors it and escalation
falls back to SpecialistClinician if the AI fails. Concrete answer to:
"how do you govern AI in a clinical pathway?"

### 4. What if the specialist doesn't act?
Reset the episode, submit the referral, then do nothing for the specialist.
Explain that in a real deployment a timer would fire and the violation
response would trigger — escalation to GP Practice. The widget shows this
path is always detectable even if not compelled.

## Demo guide — architect/researcher audience (GP-referral widget)

### 1. Recommended action and Q-values
The Bellman planner shows the optimal next action and its Q-value. Watch
how the recommendation and value change after each action is executed.

### 2. Objective reachability
The EF(objective_satisfied) check shows whether the governance objective
is still achievable from the current state. Executing a wrong action can
make the objective unreachable.

### 3. Switch between scenarios
Use the scenario switcher to flip between gp_referral and ereferral against
the same API, showing the same ODP-EL toolchain supports both clinical
governance patterns.

## Stopping the servers

```bash
pkill -f "uvicorn toolchain.el_api"
pkill -f "http.server 8080"
```
