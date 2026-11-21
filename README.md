---
title: Maple Street Auto Front Desk
emoji: 🔧
colorFrom: gray
colorTo: red
sdk: gradio
sdk_version: 6.32.0
python_version: "3.12"
app_file: app.py
pinned: false
---

# Shop Front Desk

A tool-using AI agent for a **made-up** auto shop, Maple Street Auto. Everything (shop, prices, time slots, customers) is fake demo data.

It can:

1. **Answer shop questions** (hours, services, typical price ranges, warranty) with RAG over five short docs in `docs/`.
2. **Check open times** from a `Schedule` tab in a Google Sheet.
3. **Book an appointment**: it reads the details back, books only after an explicit "yes", re-checks the slot is still open, validates inputs with a Pydantic model, writes a row to an `Appointments` tab and marks the slot taken.

It never diagnoses a car or quotes a firm price: it gives typical ranges and says the final price follows an inspection. Chats are capped at 20 messages.

## How it works

```
Gradio (app.py)
  └─ LangGraph ReAct agent (agent.py, watsonx chat model)
       ├─ search_shop_docs   → Chroma (local embeddings) over docs/*.md   (ingest.py)
       ├─ get_open_slots     → Google Sheet "Schedule" tab                (tools.py)
       └─ book_appointment   → Pydantic validation → slot check → interrupt (readback)
                               → explicit yes? → re-check slot → write "Appointments" row
```

The confirmation is enforced in code, not left to the model: `book_appointment` pauses the graph with `interrupt()` and only a plain affirmative ("yes", "yes please") resumes it. Anything else, including "yes but make it 3pm", cancels. If a slot is taken, the tool asks the customer to pick another time instead of letting the model choose one.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env      # then fill in your values
.\.venv\Scripts\python ingest.py     # builds the local Chroma index
.\.venv\Scripts\python app.py        # Gradio UI on http://localhost:7860
```

Or chat in the terminal with `python agent.py`.

### Configuration (`.env`, never committed)

| Variable | What |
|---|---|
| `WATSONX_APIKEY`, `WATSONX_URL`, `WATSONX_PROJECT_ID` | watsonx.ai credentials |
| `WATSONX_MODEL_ID` | tool-calling chat model (default `ibm/granite-4-h-small`) |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | path to a service account JSON key (local) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | the key's JSON text (hosted, as a secret; wins over the file) |
| `SHEET_ID` | ID of the Google Sheet |

### Google Sheet setup

1. Create a Google Cloud project, enable the **Sheets** and **Drive** APIs, create a service account and a JSON key.
2. Create a sheet in your own Drive (service accounts can't own files) and share it with the service account's email as **Editor**.
3. Put the ID in `SHEET_ID`, then run `python seed_sheet.py`. It loads `data/schedule_seed.csv` into a `Schedule` tab (`Date, Day, Time, Status`) and creates an `Appointments` tab. Run it again any time to reset the demo.

## Tests

Manual test cases and results are in [tests.md](tests.md): shop questions, bookings, "no" at confirm, an off-topic question, and a taken slot.

## Deploy to Hugging Face Spaces

This README's header is the Space config. Add these as Space **Secrets** (not files): the five variables above, using `GOOGLE_SERVICE_ACCOUNT_JSON` for the key. The Chroma index is built automatically on first start.

Because the demo writes to a shared sheet, anyone can book fake slots. Run `python seed_sheet.py` to reset it.
