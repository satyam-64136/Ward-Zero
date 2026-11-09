# Roadmap

Planned work, written as tickets that a tester without code knowledge can verify. These are **drafts**: nothing here has been filed in an issue tracker. To file one, copy it into a GitHub issue using the feature request template.

| # | Ticket | Priority |
|---|---|---|
| 1 | Caregiver login | High |
| 2 | Text message or WhatsApp escalation | High |
| 3 | Several patients on one dashboard | Medium |
| 4 | Real history, charts over hours and days | Medium |
| 5 | Review of risk thresholds with a clinician | High |
| 6 | Instant updates instead of once-a-second refresh | Low |
| 7 | Keyboard and screen reader check | Medium |

---

## 1. Caregiver login
**Why.** Today anyone who can open the page can acknowledge alerts or change the demo.
**How to check.**
1. Open the dashboard without signing in.
2. You should be asked to sign in and see no patient data.
3. Sign in as a caregiver. You should see the dashboard and be able to acknowledge an alert.
4. Sign in as a family member. You should see the dashboard but not the demo controls, and the Acknowledge button should be missing.

## 2. Text message or WhatsApp escalation
**Why.** A caregiver who is away from the screen never sees an in-app alert.
**How to check.**
1. Set the family contact to your own phone number.
2. Start the Deteriorating scenario and do not acknowledge.
3. After the first escalation step, your phone should receive a message that names the risk level and the reasons.
4. Acknowledge on the dashboard. No further messages should arrive.

## 3. Several patients on one dashboard
**Why.** A caregiver may look after more than one person.
**How to check.**
1. Add two patients, Bed 1 and Bed 2.
2. Make Bed 2 deteriorate.
3. Bed 2 should show High risk and an alert; Bed 1 should stay Low and show no alert.

## 4. Real history
**Why.** The 24 to 48 hour prediction currently looks at a short window of readings.
**How to check.**
1. Load 48 hours of sample data in which oxygen slowly falls.
2. An early warning should appear before the oxygen reaches a critical value.
3. Load 48 hours of steady data. No early warning should appear.

## 5. Review of risk thresholds with a clinician
**Why.** The thresholds are illustrative and not validated.
**How to check.** A named clinician signs off a written list of thresholds and the wording shown on screen. Every change is recorded in the changelog.

## 6. Instant updates
**Why.** The page asks for new data once a second.
**How to check.** With the network inspector open, the page should not send repeated requests, and a new reading should appear within half a second.

## 7. Keyboard and screen reader check
**Why.** Caregivers may rely on a keyboard or screen reader.
**How to check.**
1. Use only the Tab key to reach and press every button.
2. A screen reader should announce a change in risk level and each new alert.
3. Text should stay readable at 200 percent zoom in both light and dark themes.
