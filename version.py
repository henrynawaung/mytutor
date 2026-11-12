"""myTutor release version, shown at the bottom left of every myTutor page."""
VERSION = "4.3.9"
RELEASED = "2026-11-12"
NOTES = "Gamification: XP & career ladder, combo streak, Ellie wardrobe, quote of the day"


def label() -> str:
    from datetime import date
    d = date.fromisoformat(RELEASED)
    return f"myTutor by henryZ · v{VERSION} · {d.day} {d.strftime('%b %Y')}"
