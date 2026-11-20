"""Reset the demo sheet: reload Schedule from data/schedule_seed.csv, clear Appointments rows.

Fake data only. Run before demos/tests:  python seed_sheet.py
"""
import csv
from pathlib import Path

from tools import _spreadsheet

SEED = Path(__file__).parent / "data" / "schedule_seed.csv"


def main():
    ss = _spreadsheet()
    sched = ss.worksheet("Schedule")
    rows = list(csv.reader(SEED.open()))
    sched.clear()
    sched.update(rows, "A1")
    appts = ss.worksheet("Appointments")
    appts.batch_clear(["A2:G1000"])
    print(f"Schedule reset ({len(rows) - 1} slots); Appointments cleared.")


if __name__ == "__main__":
    main()
