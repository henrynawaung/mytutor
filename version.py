"""myTutor release version, shown at the bottom left of every myTutor page."""
VERSION = "4.7.3"
RELEASED = "2026-11-14"
NOTES = "Stretch suggests higher targets when you are past it"


def label() -> str:
    from datetime import date
    d = date.fromisoformat(RELEASED)
    return f"myTutor by henryZ · v{VERSION} · {d.day} {d.strftime('%b %Y')}"
