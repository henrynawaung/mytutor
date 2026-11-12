"""myTutor release version, shown at the bottom left of every myTutor page."""
VERSION = "4.5"
RELEASED = "2026-11-12"
NOTES = "Weekly trend chart in Review history"


def label() -> str:
    from datetime import date
    d = date.fromisoformat(RELEASED)
    return f"myTutor by henryZ · v{VERSION} · {d.day} {d.strftime('%b %Y')}"
