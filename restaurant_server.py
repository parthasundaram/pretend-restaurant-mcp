import os
import sqlite3
from datetime import date as calendar_date
from typing import Annotated
from uuid import uuid4

from mcp.server.fastmcp import FastMCP
from pydantic import Field

NAME = "Pasta Palace"
TIMES = ("17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00", "20:30")
DB_PATH = os.getenv("RESERVATIONS_DB", "reservations.sqlite3")
mcp = FastMCP(NAME, host="0.0.0.0", port=int(os.getenv("PORT", "8000")),
              stateless_http=True, json_response=True)


def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS reservations (
        reservation_id TEXT PRIMARY KEY, guest_name TEXT NOT NULL,
        date TEXT NOT NULL, time TEXT NOT NULL, party_size INTEGER NOT NULL,
        status TEXT NOT NULL)""")
    db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_confirmed_per_slot
        ON reservations(date, time) WHERE status = 'confirmed'""")
    return db


def valid(date: str, party_size: int) -> str | None:
    try:
        parsed = calendar_date.fromisoformat(date)
        if parsed.isoformat() != date:
            raise ValueError()
    except ValueError:
        return "Date must be in YYYY-MM-DD format."
    if parsed < calendar_date.today():
        return "Date cannot be in the past."
    if not 1 <= party_size <= 10:
        return "Party size must be between 1 and 10."
    return None


@mcp.tool()
def search_slots(
    date: Annotated[str, Field(description="Reservation date in YYYY-MM-DD format, for example 2026-10-10. Past dates are rejected.")],
    party_size: Annotated[int, Field(description="Number of guests, from 1 through 10.")],
) -> dict:
    """Search available tables at Pasta Palace without making a booking.

    Use this when a guest wants to see options for a date and party size.
    Returns available_slots as 24-hour HH:MM strings, between 17:00 and
    20:30 in 30-minute steps. Availability can change before booking, so
    book_reservation may still reject a slot. This demo has one table per
    date and time; party size is validated but does not change capacity.
    Returns success=false with error for invalid inputs.
    """
    if error := valid(date, party_size):
        return {"success": False, "error": error}
    with connect() as db:
        booked = {row[0] for row in db.execute(
            "SELECT time FROM reservations WHERE date = ? AND status = 'confirmed'", (date,))}
    return {"success": True, "restaurant": NAME, "date": date,
            "party_size": party_size, "available_slots": [t for t in TIMES if t not in booked]}


@mcp.tool()
def book_reservation(
    date: Annotated[str, Field(description="Reservation date in YYYY-MM-DD format; use the same date shown to the guest.")],
    time: Annotated[str, Field(description="One offered time in 24-hour HH:MM format, such as 19:00. Offered every 30 minutes from 17:00 through 20:30.")],
    party_size: Annotated[int, Field(description="Number of guests, from 1 through 10.")],
    guest_name: Annotated[str, Field(description="Name to place on the reservation, 1 to 100 characters after trimming; blank names are rejected.")],
) -> dict:
    """Create a confirmed reservation at Pasta Palace.

    This changes state. Call only when the guest has chosen a specific date,
    time, party size, and name and asked to book. A prior search is useful
    but not required. Only one confirmed reservation can occupy a date/time;
    if another booking wins, returns success=false and an error. On success,
    return the reservation details and reservation_id to the guest. Keep that
    ID for lookup or cancellation. Times have no timezone conversion.
    """
    if error := valid(date, party_size):
        return {"success": False, "error": error}
    if time not in TIMES:
        return {"success": False, "error": "That time is not offered."}
    guest_name = guest_name.strip()
    if not guest_name or len(guest_name) > 100:
        return {"success": False, "error": "Guest name must be 1–100 characters."}
    reservation = {"reservation_id": str(uuid4()), "restaurant": NAME,
                   "guest_name": guest_name, "date": date, "time": time,
                   "party_size": party_size, "status": "confirmed"}
    try:
        with connect() as db:
            db.execute("""INSERT INTO reservations
                (reservation_id, guest_name, date, time, party_size, status)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (reservation["reservation_id"], guest_name, date, time, party_size, "confirmed"))
    except sqlite3.IntegrityError:
        return {"success": False, "error": "That slot is no longer available."}
    return {"success": True, "reservation": reservation}


@mcp.tool()
def get_reservation(
    reservation_id: Annotated[str, Field(description="The reservation_id UUID returned by book_reservation.")],
) -> dict:
    """Retrieve one reservation without changing it.

    Use the exact reservation_id from a prior booking. Returns its guest
    name, date, time, party size, and status (confirmed or cancelled).
    Returns success=false with error if the ID does not exist.
    """
    with connect() as db:
        row = db.execute("SELECT * FROM reservations WHERE reservation_id = ?",
                         (reservation_id,)).fetchone()
    if row is None:
        return {"success": False, "error": "Reservation not found."}
    return {"success": True, "reservation": {"restaurant": NAME, **dict(row)}}


@mcp.tool()
def cancel_reservation(
    reservation_id: Annotated[str, Field(description="The reservation_id UUID returned by book_reservation; not a date or guest name.")],
) -> dict:
    """Cancel a confirmed reservation and free its date/time slot.

    This changes state. Call only when the guest asks to cancel the booking
    identified by reservation_id. On success, returns the reservation with
    status=cancelled. An unknown ID or an already cancelled reservation
    returns success=false with an error. Cancellation cannot be undone; a
    new booking is required to reserve the slot again.
    """
    with connect() as db:
        changed = db.execute("""UPDATE reservations SET status = 'cancelled'
            WHERE reservation_id = ? AND status = 'confirmed'""", (reservation_id,)).rowcount
        row = db.execute("SELECT * FROM reservations WHERE reservation_id = ?",
                         (reservation_id,)).fetchone()
    if row is None:
        return {"success": False, "error": "Reservation not found."}
    if not changed:
        return {"success": False, "error": "Reservation has already been cancelled."}
    return {"success": True, "reservation": {"restaurant": NAME, **dict(row)}}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
