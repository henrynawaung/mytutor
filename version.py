"""myTutor release version, shown at the bottom left of every myTutor page."""
VERSION = "4.8.3"
RELEASED = "2026-11-14"
NOTES = "Resume your last note; Recent list; Done panel no longer freezes"


def label() -> str:
    from datetime import date
    d = date.fromisoformat(RELEASED)
    return f"myTutor by henryZ · v{VERSION} · {d.day} {d.strftime('%b %Y')}"
