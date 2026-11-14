"""myTutor release version, shown at the bottom left of every myTutor page."""
VERSION = "4.11.2"
RELEASED = "2026-11-14"
NOTES = "Longer career ladder: Senior VP and Chief Executive added"


def label() -> str:
    from datetime import date
    d = date.fromisoformat(RELEASED)
    return f"myTutor by henryZ · v{VERSION} · {d.day} {d.strftime('%b %Y')}"
