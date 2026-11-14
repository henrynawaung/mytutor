# myTutor by henryZ: version history and tech stack

Version numbers read **major.feature.fix**:
- **Major release** (1 → 2 → 3 → 4) is a big change in what myTutor is, with major new features.
- **Feature update** (4.1, 4.2, 4.3 …) adds new features.
- **Bug fix** (4.3.1, 4.3.2 …) is a correction or polish, listed under its feature update.

The running version appears at the bottom left of every myTutor page.

# Tech stack (as of 4.11)
Installed versions were read from the laptop's Python environment on 12 Nov 2026.

## Languages
- **Python 3.12**: pipeline, Review app, Control Centre, vault tools. Tested on 3.12.2; 3.11+ is supported.
- **JavaScript** (plain, no framework), **HTML** and **CSS**: the browser pages.
- **SQL** (SQLite) for the review database; **Markdown** for the Obsidian notes, which stay the master copy.
- **Windows batch** for the start-up scripts (myTutor Control Centre.bat, start-n8n.bat).

## Python libraries
- **anthropic 1.15.0**: Claude API client for note and quiz generation.
- **pymupdf 1.28.2**, **python-pptx 1.0.2**, **python-docx 1.2.0**: read PDF, PowerPoint and Word lecture files.
- **flask 3.1.3** with **werkzeug 3.1.9** and **jinja2 3.1.6**: the Review app web server, scrypt password hashing and page templates.
- **xlsxwriter 3.2.9**: evidence workbooks. **pillow 13.0.0**, **lxml 6.1.3**: used by the document readers.
- Standard library only for the **Control Centre** (http.server, sqlite3, subprocess, threading) and for the vault tools.
- Optional, not installed: **msal**, **requests**, needed only for OneDrive "graph" mode.

## AI
- Claude API, model **claude-sonnet-5-5** (set in config.json). Case Lab also uses Claude's server-side **web search tool** (web_search_20250305, up to 4 searches per case). The API key lives in the ANTHROPIC_API_KEY environment variable, never in files.

## Browser side
- **marked 12.0.2**: Markdown preview in the take editor.
- Everything else is hand-written, with no extra libraries: SVG charts (trend, forecast), LinkedIn images drawn with the browser's canvas, the canvas brain, Ellie and the crew as SVG, and sounds (kalimba, chimes) made with Web Audio.
- **Open-Meteo**: weather on the Today card (free, no key). It is the only outside call from the pages.

## Automation and notes
- **n8n 2.x** on **Node.js 24+**: runs myTutor every 15 minutes (Execute Command node, enabled by start-n8n.bat).
- **Obsidian** vault (henry_mba) with the **Dataview** plugin for the Review Dashboard.

## Local services
- Control Centre on **127.0.0.1:5056**; Review app on **127.0.0.1:5057**; n8n on **localhost:5678**. All stay on the laptop.

## Security
- Email login with scrypt-hashed passwords and lockout after 5 tries; CSRF tokens; Content-Security-Policy (scripts only from the app itself).
- The Control Centre uses a per-session token and Host check, and only runs whitelisted actions.

## Testing
- **pytest**: 130 automated tests (pipeline, Review app, Control Centre, vault tools).
- **Playwright** browser checks were used while building each UI change (on the development machine, not the laptop).

# Major release 4 (current): myTutor as a second brain
Version 4 began with the assessment release (4.0 and 4.1) and grew into a daily learning app: Review app, Control Centre and rewards. Feature updates, newest first:

## 4.11 · 14 Nov 2026 · LinkedIn images
- The **📣 Post** pop-up now also gives you **two images** for every draft: a **title image** (1200×627: headline, a topic illustration and "Henry N. Aung") and an **ending image** (1080×1350: the key points as numbered steps, your takeaway and the closing question). Clean light style in your accent colour, drawn on your laptop (no extra cost). **Download PNG** saves each one.
- **Copy image prompt** for each image: a ready-made prompt for ChatGPT, Gemini, Copilot or Midjourney when you want a photo-style version (an executive presenting the headline to a boardroom, or an icon infographic). No logos or brand names.
- Bug fix 4.11.1: notes made from **your own LinkedIn posts are filed as reviewed**, so they never join your review queue.

## 4.10 · 14 Nov 2026 · LinkedIn in and out
- **Your posts in:** a new inbox folder **LinkedIn_MyPosts** (next to BusinessMentor). Save each post as a text or .md file, with the article link or text underneath if it was based on one. myTutor files it by date (from the file name, or the day you saved it) and writes a **"My post - ..."** note: your public position in one line, the post text, what it was based on (with links), and links to the concepts it uses. The article gets its own source note. No quiz questions on your own opinions.
- **Posts out:** a **📣 Post** button on every take drafts a LinkedIn post from that take, in the voice of your earlier posts (about US$0.02). Edit, copy and post it yourself; myTutor never posts for you.
- Bug fix 4.10.1: the stretch question now comes **as soon as you pass your target** (at 121 of 120, not 125). "Not now", or clicking outside the box, pauses it for 5 more notes.

## 4.9 · 14 Nov 2026 · Case Lab
- New **🧭 Case Lab** tab. Describe a situation, paste an article or name a board topic, and myTutor writes a board-ready case with a **model answer to guide you** when a similar situation comes up: the case, recommendation, options considered, rationale, risks and how to reduce them, first 90 days, and the questions a board will ask with strong answers.
- Built on **your own notes first**: it finds the most relevant concepts, cases, sources and your takes (quoted as "Your take"), links each one, then adds **key points from web search** of reputable sources, each with its source, plus the gaps your notes don't cover yet.
- Each case is saved in Obsidian under **Case Lab / date** and appears in the Library like any other note (search, copy, add takes). About US$0.10 to 0.20 per case.
- **Unlocks when 50% of your notes are reviewed**; until then the tab shows your progress and how many more to go.
- Move break: **Ellie now walks** back and forth with you, swinging her arms, and **checks her watch** every few seconds.
- Fixed: My days and Case Lab keep the Done panel in its column.

## 4.8 · 14 Nov 2026 · Done panel
- A new **Done** panel on the right lists your completed work, newest first, grouped Today / Yesterday / by date.
- Filters: **Both / Takes / Approved**, This week / Today / All time, kind (concepts, cases, sources, hubs), course, and a quick text filter.
- Each row shows the note, course and day, ✓ approved, the number of takes and the start of your latest take.
- Click a row to open the note at your takes; click ✎ to jump straight into editing your latest take, for continuous fine-tuning. The list refreshes after every save.
- **Hide »** folds the panel (or press **]**); **Done «** on the right edge brings it back. It starts folded on small screens.
- Search now labels every result **✓ done**, **to review** or **needs fix**, with All / To review / Done buttons. It always searches every note, whatever the Library filters say.
- Bug fix 4.8.1 (small feature): **one-click Copy** at the top of every note copies it as clean text with its title, ready to paste into Word, email or Teams. Each of your takes has its own Copy button. Shift+click copies the Markdown instead. The button shows "Copied" in green.
- Bug fix 4.8.2: after a move break, **one click** ("I'm back, continue learning") closes Ellie and returns you to your note, with a short welcome-back message. If the 2-minute timer runs out, the cheer closes by itself after 5 seconds.
- Bug fix 4.8.3: **back where you left off**: after a refresh, restart or reboot, the Review app reopens the note you were last working on (within 7 days), with your unsaved draft. The Done panel gains a **🕘 Recent** filter listing the notes you opened, newest first, with unsaved drafts marked. Fixed the Done panel's Hide button and top rows not responding: the hidden achievement card was still catching clicks there.
- Bug fix 4.8.4: **calmer Ellie** when several awards arrive together. Once her card is on screen it stays still and only the words and bar update; her motion plays twice, then she rests; and when a big award pop-up opens, the small card steps aside so there is only one Ellie at a time. Your **award points (+XP)** now show in a badge under Ellie and update in place.
- Bug fix 4.8.5: **failed days are retried automatically**. If note writing failed (for example the API key was rejected), every later run, including n8n's 15-minute run, redoes only the failed sources and then files the notes. Days that already worked are never redone or charged twice. If Claude rejects the API key, the run stops after the first failure with one clear message ("API KEY REJECTED … Stop all, close and reopen the Control Centre, Start all") instead of failing every day.
- Bug fix 4.8.6: Ellie's achievement card now sits **beside the Done panel** instead of on top of it (it returns to the right edge when the panel is hidden). Personalise is tidier: every option is visible (rows wrap instead of being cut off, and the selected option is highlighted again), and scrollbars are thin and quiet, with the settings scrollbar showing only while your mouse is over the panel.
- Bug fix 4.8.7: Ellie now **moves for the whole tune** (about 3.3 s for the kalimba, longer for big moments, shorter for the short chime) and then rests in her normal pose, instead of stopping before the music ends.
- Bug fix 4.8.8: Ellie's card is **one clean layer**: the glowing combo ring and the tinted background layer are gone, Ellie and her +XP badge are centred in the card, and a combo is shown by the red edge and label only.

## 4.7 · 12 Nov 2026 · Full-text search
- The Library search box now looks **inside every note**: concepts, cases, sources, hubs, reflections and your own takes, not just titles.
- All the words you type must appear, in any order. Title matches rank first.
- Each result shows its kind, course, day and a snippet with the words highlighted.
- Opening a result highlights the words in the note and scrolls to the first one.
- **Enter** opens the top result; **Esc** clears the search.
- The stretch question reads correctly when you are exactly on target.
- Bug fix 4.7.1: Library groups **fold again**. The group of the open note, and small groups such as Sources, used to spring back open; now they open once and stay folded when you close them.
- Bug fix 4.7.2: a **tidier Today card** (time, weather, move breaks, quote of the day). Rank and XP moved to a compact pill in the header (click it for the ladder and crew); **My crew** moved to the profile menu; the memory line is off by default (switch it on in Personalise). The profile menu now opens above the note header.
- Bug fix 4.7.3 (14 Nov): when you are **past your target**, Ellie suggests the next three targets above your count (at 48: 50, 55 or 60), asking again at every 5th approval. "Not now" pauses the question until you are 10 notes further. Once the target is met, **click the weekly ring** to stretch any time.

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
