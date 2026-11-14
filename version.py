"""myTutor release version, shown at the bottom left of every myTutor page."""
VERSION = "4.11.4"
RELEASED = "2026-11-14"
NOTES = "Long post titles filed safely; unfiled days are filed next run"


def label() -> str:
    from datetime import date
    d = date.fromisoformat(RELEASED)
    return f"myTutor by henryZ · v{VERSION} · {d.day} {d.strftime('%b %Y')}"
