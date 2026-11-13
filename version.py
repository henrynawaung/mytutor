"""myTutor release version, shown at the bottom left of every myTutor page."""
VERSION = "4.8.4"
RELEASED = "2026-11-14"
NOTES = "Calmer Ellie when several awards arrive"


def label() -> str:
    from datetime import date
    d = date.fromisoformat(RELEASED)
    return f"myTutor by henryZ · v{VERSION} · {d.day} {d.strftime('%b %Y')}"
