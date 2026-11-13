"""myTutor release version, shown at the bottom left of every myTutor page."""
VERSION = "4.8"
RELEASED = "2026-11-14"
NOTES = "Done panel: your takes and approvals on the right"


def label() -> str:
    from datetime import date
    d = date.fromisoformat(RELEASED)
    return f"myTutor by henryZ · v{VERSION} · {d.day} {d.strftime('%b %Y')}"
