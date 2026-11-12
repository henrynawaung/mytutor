"""myTutor release version, shown at the bottom left of every myTutor page."""
VERSION = "4.4.1"
RELEASED = "2026-11-12"
NOTES = "Stretch goal +5 after weekly goal; Today card without duplicate weekly bar"


def label() -> str:
    from datetime import date
    d = date.fromisoformat(RELEASED)
    return f"myTutor by henryZ · v{VERSION} · {d.day} {d.strftime('%b %Y')}"
