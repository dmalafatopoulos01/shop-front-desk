# Shop Front Desk

Tool-using AI agent for a made-up auto shop (Maple Street Auto). Spec: https://claude.ai/artifact/TzpMZoorPMhyv6L2DTmjX7

Stack: Python, LangGraph, Chroma, gspread (Google Sheets), Gradio, watsonx or another tool-calling model.

## Rules
- Fake data only (made-up shop, made-up time slots).
- No keys in git. Use a local `.env` (not committed), `.env.example`, and Hugging Face Secrets.
- No diagnoses or firm prices; give typical ranges and say the final price follows an inspection.
- Booking: read details back, book only after an explicit "yes", re-check the slot is still open, validate inputs with a Pydantic model.
- Cap messages per visitor.
- Ask before creating the Google service account or any credentials.

## Repo layout
app.py (Gradio), agent.py (LangGraph + confirm step), tools.py, ingest.py, docs/, tests.md, requirements.txt, .env.example, README.md

## Working style
Build in four steps and stop after each for review. See BRIEF.md.
