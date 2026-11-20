"""Agent tools. Step 1: shop-docs search only."""
import os
from datetime import date

import chromadb
from dotenv import load_dotenv
from langchain_core.tools import tool

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


def _schedule_rows() -> list[dict]:
    """Read the 'Schedule' tab (columns: Date, Day, Time, Status) from the Google Sheet."""
    import gspread

    gc = gspread.service_account(filename=os.environ["GOOGLE_SERVICE_ACCOUNT_FILE"])
    return gc.open_by_key(os.environ["SHEET_ID"]).worksheet("Schedule").get_all_records()


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


TOOLS = [search_shop_docs, get_open_slots]
