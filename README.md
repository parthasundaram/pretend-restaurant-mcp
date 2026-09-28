# Pretend restaurant MCP server

Four tools: `search_slots`, `book_reservation`, `get_reservation`, and
`cancel_reservation`. One reservation is allowed per date and time. Booking
requires a guest name. Data is kept in SQLite across process restarts.

## Tool contract

| Tool | When to call | Inputs | Result |
| --- | --- | --- | --- |
| `search_slots` | Guest asks what is available; read-only | `date` (YYYY-MM-DD), `party_size` (1–10) | `available_slots` as 24-hour HH:MM strings |
| `book_reservation` | Guest selects a particular slot and asks to book; changes state | `date`, `time`, `party_size`, `guest_name` | Confirmed `reservation` with `reservation_id` |
| `get_reservation` | Guest asks for booking details; read-only | `reservation_id` | Reservation and current status |
| `cancel_reservation` | Guest asks to cancel an identified booking; changes state | `reservation_id` | Reservation with `status=cancelled` |

All responses have `success`. An invalid input or unavailable slot returns
`success=false` and an `error` string. Search does not hold a table. A
booking can fail if another request takes the slot first. Offered times are
17:00 through 20:30, every 30 minutes. This intentionally models one table
per date/time; party size is validated but does not affect capacity. The demo
does not convert timezones, and the past-date check uses the server's clock.

Example flow: search `{"date":"2026-10-10","party_size":4}`, book with
`{"date":"2026-10-10","time":"19:00","party_size":4,"guest_name":"Alex Lee"}`,
then retain the returned `reservation_id` for lookup or cancellation.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python restaurant_server.py
```

Connect an MCP client to `http://localhost:8000/mcp` using Streamable HTTP.
The server listens on `0.0.0.0` and honors the `PORT` environment variable.

## Deploy

Deploy the Dockerfile on any container host that supports an HTTPS web service.
Expose `PORT=8000` (or let the host set PORT), then use
`https://YOUR-HOST/mcp` as the agent's MCP URL. Mount persistent storage at
`/data` for the SQLite database; without it, reservations disappear on
container replacement. Run one instance unless you configure shared storage.

This is a demo: it has no authentication. Anyone who knows a reservation ID can
retrieve or cancel that reservation. Add authentication and ownership checks
before accepting real guest information on a public endpoint.

## Railway

Create an empty Railway project and deploy this directory with `railway up`,
or connect a GitHub repository containing these files at its root. Railway
uses the Dockerfile and `railway.toml`. In the service settings, generate a
public domain. The MCP URL is `https://YOUR-DOMAIN/mcp`.

For durable reservations, attach a Railway volume at `/data` before creating
bookings. The container's `RESERVATIONS_DB` points to
`/data/reservations.sqlite3`. Keep the service at one replica with SQLite.
