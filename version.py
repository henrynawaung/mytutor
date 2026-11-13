"""myTutor release version, shown at the bottom left of every myTutor page."""
VERSION = "4.9"
RELEASED = "2026-11-14"
NOTES = "Case Lab (unlocks at 50% reviewed); Ellie walks and checks her watch"


def label() -> str:
    from datetime import date
    d = date.fromisoformat(RELEASED)
    return f"myTutor by henryZ · v{VERSION} · {d.day} {d.strftime('%b %Y')}"
