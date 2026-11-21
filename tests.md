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

Step 3 (booking; run `python seed_sheet.py` first to reset the sheet):

| # | Scenario | Expected | Result |
|---|----------|----------|--------|
| 8 | Sam Lee, oil change, Fri 11-27 08:00, then "yes" | Readback, then booked; row in Appointments; slot -> taken | pass |
| 9 | Priya Nair, brake inspection, Mon 11-23 09:30, then "Yes" | Same | pass |
| 10 | Alex Kim, tire rotation, Sat 11-28 9:00 AM, then "yes please" | Same | pass |
| 11 | Jo Park, battery test, Tue 11-24 13:00, then "no" | Nothing booked; slot stays open | pass |
| 12 | Lee Wong, oil change, Wed 11-25 08:00, then "actually no, cancel it" | Nothing booked; slot stays open | pass |
| 13 | Request an already-taken slot (11-27 08:00) | Says unavailable, lists open times, asks customer to pick; books only after pick + "yes" | pass |

Not exercised live: the final re-check when a slot is taken between the readback and the "yes"
(implemented in `book_appointment`; needs two simultaneous visitors). Offline checks passed for
validation (bad name/phone/date/time rejected) and strict yes/no ("yes but make it 3pm" = no).

Grounding (no invented services; `python eval_grounding.py 3`, 9 prompts x 3 runs):

| # | Scenario | Expected | Result |
|---|----------|----------|--------|
| 14 | "What services do you offer?", "What do you do?", summaries | Only services named in `docs/services.md`; no "and more" | pass (was failing: listed engine diagnostics, transmission service) |
| 15 | "Do you do transmission repair?" / "wheel alignments?" / "fix my exhaust?" | Says it isn't listed; suggests calling; never "yes" | pass (was failing: said yes to transmission and alignments) |
| 16 | Bare "yes" / "hi" with nothing pending | Short "how can I help?"; no shop summary | pass |

Before the fix 21 of 27 answers had a problem (checker over-counted one case); after: 0 of 27.

Rate limit (per IP; offline tests plus a live run with `RATE_LIMIT_PER_MINUTE=3`):

| # | Scenario | Expected | Result |
|---|----------|----------|--------|
| 17 | 5 rapid requests, limit 3/min | 1-3 answered; 4-5 get "wait ~N seconds"; model not called; text kept in box | pass |
| 18 | Retry while blocked | Wait time keeps shrinking (52s then 50s); block not extended | pass |
| 19 | Forged `X-Forwarded-For` with the same `CF-Connecting-IP` | Still limited | pass (offline test) |

Run 2026-11-20 with `ibm/granite-4-h-small`.
