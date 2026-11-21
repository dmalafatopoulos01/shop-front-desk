"""Agent tools. Step 1: shop-docs search only."""
import os
import re
from datetime import date, datetime

import chromadb
from dotenv import load_dotenv
from langchain_core.tools import tool
from langgraph.types import interrupt
from pydantic import BaseModel, Field, ValidationError, field_validator

from ingest import CHROMA_DIR, COLLECTION

load_dotenv()
_collection = None


def _get_collection():
    global _collection
    if _collection is None:
        _collection = chromadb.PersistentClient(path=str(CHROMA_DIR)).get_collection(COLLECTION)
    return _collection


@tool
def search_shop_docs(query: str) -> str:
    """Search Maple Street Auto's info docs (hours, services, price ranges, warranty, location).
    Use for any question about the shop."""
    res = _get_collection().query(query_texts=[query], n_results=4)
    chunks = [
        f"[{meta['source']}]\n{doc}"
        for doc, meta in zip(res["documents"][0], res["metadatas"][0])
    ]
    return "\n\n---\n\n".join(chunks) or "No matching information found."


def _spreadsheet():
    import json

    import gspread

    # Hosted (HF Spaces): the key is a secret holding the JSON text. Local: a gitignored file.
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        gc = gspread.service_account_from_dict(json.loads(raw))
    else:
        gc = gspread.service_account(filename=os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])
    return gc.open_by_key(os.environ["SHEET_ID"])


def _schedule_rows() -> list[dict]:
    """Read the 'Schedule' tab (columns: Date, Day, Time, Status) from the Google Sheet."""
    return _spreadsheet().worksheet("Schedule").get_all_records()


def filter_open_slots(rows: list[dict], day: str, today: date) -> list[dict]:
    """Open, not-in-the-past slots for a weekday name ('Friday') or ISO date ('2026-11-27')."""
    day = day.strip()
    out = []
    for r in rows:
        if str(r["Status"]).strip().lower() != "open" or str(r["Date"]) < today.isoformat():
            continue
        if day == str(r["Date"]) or day.lower() == str(r["Day"]).strip().lower():
            out.append(r)
    return sorted(out, key=lambda r: (str(r["Date"]), str(r["Time"])))


@tool
def get_open_slots(day: str) -> str:
    """List open appointment slots for a weekday name (e.g. 'Friday') or an ISO date (YYYY-MM-DD).
    For a weekday name, returns every upcoming date with that weekday."""
    slots = filter_open_slots(_schedule_rows(), day, date.today())
    if not slots:
        return f"No open slots found for {day}."
    lines, current = [], None
    for r in slots:
        if r["Date"] != current:
            current = r["Date"]
            lines.append(f"{r['Day']} {current}:")
        lines.append(f"  - {r['Time']}")
    return "\n".join(lines)


class BookingRequest(BaseModel):
    """Validated booking details. Raises ValidationError on bad input."""

    name: str = Field(min_length=2, max_length=60)
    phone: str
    service: str = Field(min_length=3, max_length=60)
    date: date
    time: str

    @field_validator("name", "service")
    @classmethod
    def _clean_text(cls, v: str) -> str:
        v = " ".join(v.split())
        if not re.fullmatch(r"[A-Za-z0-9 .,'&/()\-]+", v):
            raise ValueError("contains unsupported characters")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if not 7 <= len(digits) <= 15 or not re.fullmatch(r"[\d\s()+.\-]+", v):
            raise ValueError("must be a valid phone number (7-15 digits)")
        return digits

    @field_validator("date")
    @classmethod
    def _future(cls, v: date) -> date:
        if v < date.today():
            raise ValueError("date is in the past")
        return v

    @field_validator("time", mode="before")
    @classmethod
    def _time(cls, v) -> str:
        return _norm_time(str(v))


def _norm_time(t: str) -> str:
    """'8:00', '08:00:00', '8:00 AM', '2:30 pm' -> 'HH:MM' (24h)."""
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})(?::\d{2})?\s*([AaPp][Mm])?\s*", t)
    if not m:
        raise ValueError("time must look like 09:30 or 2:30 PM")
    h, mi, ap = int(m[1]), int(m[2]), (m[3] or "").lower()
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        raise ValueError("time out of range")
    return f"{h:02d}:{mi:02d}"


def _find_slot(ws, iso_date: str, hhmm: str):
    """Return (row_number, status) for the slot, or (None, None). Reads fresh from the sheet."""
    for i, r in enumerate(ws.get_all_records(), start=2):
        if str(r["Date"]) == iso_date and _norm_time(str(r["Time"])) == hhmm:
            return i, str(r["Status"]).strip().lower()
    return None, None


_YES = re.compile(r"\s*(yes|y|yep|yeah|yup|confirm|confirmed|ok|okay|sure|book it|yes please)[\s.!]*", re.I)


def is_explicit_yes(text: str) -> bool:
    """Only a short, plain affirmative counts. Anything else (incl. 'yes but...') is a no."""
    return bool(_YES.fullmatch(str(text)))


@tool
def book_appointment(name: str, phone: str, service: str, date: str, time: str) -> str:
    """Book an appointment. Call ONLY after the customer has given their name, phone, service,
    and chosen an open date and time (from get_open_slots). The customer is asked to confirm
    before anything is booked. date is YYYY-MM-DD, time is HH:MM (24h)."""
    try:
        req = BookingRequest(name=name, phone=phone, service=service, date=date, time=time)
    except ValidationError as e:
        problems = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())
        return f"Booking details are invalid ({problems}). Ask the customer to correct them."

    ss = _spreadsheet()
    sched = ss.worksheet("Schedule")
    row, status = _find_slot(sched, req.date.isoformat(), req.time)
    if status != "open":
        # Don't let the model pick another time for the customer: pause and ask them.
        others = [r["Time"] for r in filter_open_slots(sched.get_all_records(), req.date.isoformat(), datetime.now().date())]
        options = ", ".join(_norm_time(str(t)) for t in others) or "none"
        choice = interrupt(
            f"Sorry, {req.date.strftime('%A %Y-%m-%d')} at {req.time} is not available. "
            f"Open times that day: {options}. Which time would you like (or another day)?"
        )
        return (f"That slot was unavailable. The customer replied: {choice!r}. "
                "If they chose a new time, call book_appointment again with exactly that time.")

    readback = (
        f"Please confirm this booking:\n"
        f"  Name: {req.name}\n  Phone: {req.phone}\n  Service: {req.service}\n"
        f"  When: {req.date.strftime('%A %Y-%m-%d')} at {req.time}\n"
        f"Reply 'yes' to book it, or anything else to cancel."
    )
    answer = interrupt(readback)  # pauses the graph until the visitor replies
    if not is_explicit_yes(answer):
        return "The customer did not confirm. Nothing was booked. Tell them it is cancelled."

    # Re-check right before writing: the slot may have been taken while we waited.
    row, status = _find_slot(sched, req.date.isoformat(), req.time)
    if status != "open":
        return "Sorry, that slot was just taken. Nothing was booked. Offer other open slots."
    status_col = sched.row_values(1).index("Status") + 1
    sched.update_cell(row, status_col, "taken")
    ss.worksheet("Appointments").append_row(
        [datetime.now().isoformat(timespec="seconds"), req.name, req.phone, req.service,
         req.date.isoformat(), req.time, "booked via chat"],
        value_input_option="RAW",
    )
    return (f"Booked: {req.service} for {req.name} on {req.date.strftime('%A %Y-%m-%d')} "
            f"at {req.time}. Final price follows an inspection.")


TOOLS = [search_shop_docs, get_open_slots, book_appointment]
