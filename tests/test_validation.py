"""Offline tests for booking validation and the yes/no gate. No network, keys, or sheet needed."""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import BookingRequest, _norm_time, book_appointment, filter_open_slots, is_explicit_yes  # noqa: E402

TOMORROW = (date.today() + timedelta(days=1)).isoformat()


def make(**overrides):
    data = dict(name="Sam Lee", phone="555-010-2222", service="Oil change", date=TOMORROW, time="09:30")
    data.update(overrides)
    return BookingRequest(**data)


def failing_fields(**overrides) -> set[str]:
    with pytest.raises(ValidationError) as exc:
        make(**overrides)
    return {e["loc"][0] for e in exc.value.errors()}


# --- BookingRequest ---------------------------------------------------------------

def test_valid_booking_is_normalized():
    b = make(phone="(555) 010-2222", time="2:30 PM", name="  Sam   Lee ")
    assert b.phone == "5550102222"
    assert b.time == "14:30"
    assert b.name == "Sam Lee"
    assert b.date == date.today() + timedelta(days=1)


def test_today_is_allowed_but_past_is_not():
    assert make(date=date.today().isoformat()).date == date.today()
    assert failing_fields(date=(date.today() - timedelta(days=1)).isoformat()) == {"date"}


@pytest.mark.parametrize("bad_date", ["2026-13-40", "not a date", "2026/11/27x", ""])
def test_bad_dates_rejected(bad_date):
    assert failing_fields(date=bad_date) == {"date"}


@pytest.mark.parametrize("bad_phone", ["12", "abc", "555-CALL-NOW", "1" * 16, ""])
def test_bad_phones_rejected(bad_phone):
    assert failing_fields(phone=bad_phone) == {"phone"}


@pytest.mark.parametrize("phone", ["5550102222", "+1 (555) 010-2222", "555.010.2222", "010-2222"])
def test_good_phones_accepted(phone):
    assert 7 <= len(make(phone=phone).phone) <= 15


@pytest.mark.parametrize("bad_name", ["S", "", "=cmd()", "<script>", "x" * 61])
def test_bad_names_rejected(bad_name):
    assert failing_fields(name=bad_name) == {"name"}


@pytest.mark.parametrize("name", ["Jo Park", "O'Brien", "Anne-Marie Smith", "J. R. Ward"])
def test_reasonable_names_accepted(name):
    assert make(name=name).name == name


@pytest.mark.parametrize("bad_service", ["x", "", "=HYPERLINK(1)", "a" * 61])
def test_bad_services_rejected(bad_service):
    assert failing_fields(service=bad_service) == {"service"}


@pytest.mark.parametrize("bad_time", ["25:99", "9", "noon", "", "24:00", "12:60"])
def test_bad_times_rejected(bad_time):
    with pytest.raises(ValidationError):
        make(time=bad_time)


def test_multiple_problems_all_reported():
    assert failing_fields(name="S", phone="12", time="25:99") == {"name", "phone", "time"}


# --- _norm_time -------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [("8:00", "08:00"), ("08:00", "08:00"), ("08:00:00", "08:00"), ("8:00 AM", "08:00"),
     ("2:30 pm", "14:30"), ("12:00 AM", "00:00"), ("12:00 PM", "12:00"), ("23:59", "23:59")],
)
def test_norm_time(raw, expected):
    assert _norm_time(raw) == expected


# --- explicit yes gate ------------------------------------------------------------

@pytest.mark.parametrize("text", ["yes", "Yes", "YES!", "y", "yep", "yeah", "yes please", "confirm", " ok. ", "book it"])
def test_plain_affirmatives_count(text):
    assert is_explicit_yes(text)


@pytest.mark.parametrize(
    "text",
    ["no", "", "not yet", "yes but make it 3pm", "yes, and also book another", "maybe", "no, yes", "y e s", "cancel it"],
)
def test_everything_else_is_a_no(text):
    assert not is_explicit_yes(text)


# --- filter_open_slots ------------------------------------------------------------

ROWS = [
    {"Date": "2026-11-27", "Day": "Friday", "Time": "11:00", "Status": "open"},
    {"Date": "2026-11-27", "Day": "Friday", "Time": "08:00", "Status": "open"},
    {"Date": "2026-11-27", "Day": "Friday", "Time": "09:30", "Status": "taken"},
    {"Date": "2026-11-20", "Day": "Friday", "Time": "08:00", "Status": "open"},  # in the past
    {"Date": "2026-11-28", "Day": "Saturday", "Time": "09:00", "Status": "OPEN "},
]
TODAY = date(2026, 11, 21)


def times(rows):
    return [(r["Date"], r["Time"]) for r in rows]


def test_weekday_name_skips_taken_and_past_and_sorts():
    assert times(filter_open_slots(ROWS, "Friday", TODAY)) == [("2026-11-27", "08:00"), ("2026-11-27", "11:00")]


def test_weekday_and_status_matching_is_case_insensitive():
    assert times(filter_open_slots(ROWS, "saturday", TODAY)) == [("2026-11-28", "09:00")]


def test_iso_date_lookup():
    assert len(filter_open_slots(ROWS, "2026-11-27", TODAY)) == 2
    assert filter_open_slots(ROWS, "2026-11-29", TODAY) == []


def test_unknown_day_returns_nothing():
    assert filter_open_slots(ROWS, "Funday", TODAY) == []


# --- tool-level guard: bad input never reaches the sheet --------------------------

def test_book_appointment_rejects_invalid_input_before_touching_sheet(monkeypatch):
    import tools

    def boom():
        raise AssertionError("sheet must not be opened for invalid input")

    monkeypatch.setattr(tools, "_spreadsheet", boom)
    out = book_appointment.func(name="S", phone="12", service="Oil change", date=TOMORROW, time="09:30")
    assert out.startswith("Booking details are invalid")
    assert "name" in out and "phone" in out
