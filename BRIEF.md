# Session brief

Build "Shop Front Desk" per CLAUDE.md. Abilities:
1. Answer shop questions (hours, services, price ranges, warranty) via RAG over 4-5 short made-up docs in docs/.
2. Check open slots from a "Schedule" tab in a Google Sheet.
3. Book an appointment (confirm first, re-check slot, Pydantic validation); write a row to an "Appointments" tab and mark the slot taken.

Tests (tests.md): 4 shop questions, 3 bookings, 2 "no" at confirm, 1 off-topic.

Steps (stop after each):
1. Terminal Q&A via RAG. Done when "Do you do brake work?" gets a correct answer.
2. Read open times from the sheet. Done when "What's open Friday?" lists the right slots.
3. Booking with confirm and slot re-check. Done when a confirmed booking appears as a new row.
4. Gradio UI with 3 example questions, HF Spaces deploy, README, demo GIF.

Start with step 1 only. Use plan mode first.
