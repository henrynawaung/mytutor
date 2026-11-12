"""myTutor release version, shown at the bottom left of every myTutor page."""
VERSION = "4.2"
RELEASED = "2026-11-12"
NOTES = "Review app: Today card, rewards (Ellie, crew, badges, kalimba), weekly goal setting"


def label() -> str:
    from datetime import date
    d = date.fromisoformat(RELEASED)
    return f"myTutor by henryZ · v{VERSION} · {d.day} {d.strftime('%b %Y')}"
