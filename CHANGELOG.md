# myTutor by henryZ: version history

Version numbers read **major.feature.fix**:
- **Major release** (1 → 2 → 3 → 4) is a big change in what myTutor is, with major new features.
- **Feature update** (4.1, 4.2, 4.3 …) adds new features.
- **Bug fix** (4.3.1, 4.3.2 …) is a correction or polish, listed under its feature update.

The running version appears at the bottom left of every myTutor page.

# Major release 4 (current): myTutor as a second brain
Version 4 began with the assessment release (4.0 and 4.1) and grew into a daily learning app: Review app, Control Centre and rewards. Feature updates, newest first:

## 4.6 · 12 Nov 2026 · Completion forecast
- **Completion forecast** in the Control Centre: a pace slider (5 to 100 notes a week) shows how many weeks are left and the finish date. Quick buttons for My goal, My recent pace and 50/week. The chart shows notes reviewed so far plus a dashed projection; hover for any week.
- Bug fix 4.6.1: Restart and Stop also close **stray Review app copies** (for example one started from a console window). The Services row shows the running version and turns red if an old copy is still answering. "Error 404" became a clear "Stop, then Start" message.
- Bug fix 4.6.2: this **version history**. Click the version label at the bottom left of any page to open it.

## 4.5 · 12 Nov 2026 · Weekly trend chart
- Review history in the Control Centre gains a **weekly trend chart**: approved notes and takes per week, a goal line, "▲/▼ vs last week", and hover details. Colours were checked for colour-blind safety in both themes.

## 4.4 · 12 Nov 2026 · Stretch goal
- When you reach your weekly goal, Ellie **asks** whether to stretch by +5 (never automatic). Saying no stops the questions for that week, and every week starts again at your normal goal (25).
- Weekly goal is configurable (default 25) and shared by the Review app and Control Centre.
- Bug fix 4.4.2: the save message fades out by itself (5 s, or 8 s when it offers Undo).

## 4.3 · 12 Nov 2026 · Gamification
- **XP and career ladder**: approve +10, take +25, reflection +15, memory line +20. Ranks run Analyst, Senior Analyst, Manager, Senior Manager, Director, VP, C-suite, Board Chair, with a promotion pop-up for each.
- **Combo streak** for saves less than 3 minutes apart; **Ellie's wardrobe** with costumes that unlock by rank; **quote of the day** with leadership quotes.
- 4.3.1 (small feature): **Move-break reminder**: after 30/45/60 minutes, Ellie asks you to stand and walk for 2 minutes, with a countdown.
- Bug fixes 4.3.2 to 4.3.15, layout polish:
  - Review actions became **icon buttons inside the take card, under Save**; Save is a compact button with an icon, and Ctrl+Enter saves.
  - The achievement card is a steady top-right notification; the status line is a single line.
  - The Control Centre has calmer buttons and lights, **dark/light mode**, a light brain panel with darker neurons, and the same sun/moon icon as the Review app.
  - The **Library is sorted** by course, then Day 1, 2 … (or by date), with hubs last.
  - The duplicate weekly bar was removed from the Today card (the header ring is enough), and the memory line refreshes.

## 4.2 · 12 Nov 2026 · Rewards, Ellie, Review app and Control Centre
Everything built since the assessment release (4 to 12 Nov):
- **Ellie the elephant** celebration character with motions and costumes, a **kalimba** save tune (3 s, plus a short version), party poppers every 5th save and fireworks for goals and level-ups. **My crew** characters and milestone **badges**.
- **Today card**: time, weather, rank, quote, crew and memory line, with each part optional.
- Bug fixes 4.2.1: text size scales only the reading area; the Today card never overlaps. 4.2.2: Ellie appears together with the sound.
- **Review app** (Flask + SQLite, email login, Markdown stays the master copy):
  - Markdown editor with a Template button (C-suite takeaway and memory line), drafts, Approve & Next, approve-once counting, and editing or deleting takes.
  - My days by week, reflections with the day's material, a weekly goal ring and streak (no daily pressure).
  - Personalisation (theme, font, size, accent, photo, profile photo), a grouped and collapsible Library, a sticky note header, and a version label "myTutor by henryZ".
- **Control Centre**: starts, stops and restarts n8n and the Review app; runs myTutor, dry runs, vault checks and practice quizzes; console; living "second brain" hero; KPIs; inventory; review history.
- **Vault tools**: read-only health check (vault doctor), hash-guarded apply/undo of vault changes, duplicate clean-up, and each day filed before the next is generated.
- **Reading mode** for daily leadership readings (BusinessMentor).

## 4.1 · 1 Nov 2026 · Assessment release (MBAM601 Digital Experiment)
- Final deck v4.1. Two classmates independently checked 10 audit claims and agreed on 9 of 10.
- 4.0: final deck files and evidence workbook.

# Major releases 1 to 3: assessment build (Oct 2026)
The pipeline and evidence for the MBAM601 Digital Experiment, built up to the final deck (v3.2, v3.3).
- myTutor pipeline (extract, generate, file into Obsidian) with an n8n workflow and setup guide.
- Quiz generation with shuffled answers and a mixed-difficulty target; practice page.
- Accuracy audits (Day 9, Day 10 30/30), timing replication, a recall pilot, the architecture diagram, the developer guide and pinned dependency versions.
