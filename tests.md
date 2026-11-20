# Tests

Step 1 (shop Q&A). Booking tests (3 bookings, 2 "no" at confirm) are added in step 3.

| # | Input | Expected | Result |
|---|-------|----------|--------|
| 1 | Do you do brake work? | Yes; pads/rotors/fluid/inspections; no diagnosis | pass |
| 2 | What are your hours on Saturday? | 9:00 AM to 2:00 PM | pass |
| 3 | How much is an oil change? | $45 to $110 typical; final price after inspection | pass |
| 4 | What's your warranty? | 12 mo / 12,000 mi; brakes 24 mo / 24,000 mi | pass (omitted the brake-specific 24 mo detail) |
| 5 | What's the capital of France? (off-topic) | Politely declines; shop topics only | pass |

Step 2 (availability, live Google Sheet):

| # | Input | Expected | Result |
|---|-------|----------|--------|
| 6 | What's open Friday? | Open Fridays only: 11-27 (08:00, 11:00, 14:30, 16:00), 12-04 (09:30, 11:00, 13:00, 14:30, 16:00) | pass |
| 7 | Anything open on 2026-11-28? | Sat 09:00 and 12:00 (10:30 is taken) | pass |

Run 2026-11-20 with `ibm/granite-4-h-small`.
