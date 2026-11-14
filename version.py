"""myTutor release version, shown at the bottom left of every myTutor page."""
VERSION = "4.11.1"
RELEASED = "2026-11-14"
NOTES = "LinkedIn post notes are filed as reviewed"


def label() -> str:
    from datetime import date
    d = date.fromisoformat(RELEASED)
    return f"myTutor by henryZ · v{VERSION} · {d.day} {d.strftime('%b %Y')}"
