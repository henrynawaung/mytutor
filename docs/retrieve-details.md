# myTutor pipeline

Copies one course folder (for example `Day 1`) from your OneDrive Inbox into a local
job folder, so the later stages (extract text, generate notes, file into Obsidian) work on a
fixed snapshot rather than on files that may still be syncing.

```
OneDrive  myTutor/Inbox/Day 1/  ──retrieve.py──▶  ~/mytutor/jobs/2026-10-17_103000_day-1/
                                                      source/         the copied files
                                                      manifest.json   what was copied, and from where
                                                  ~/mytutor/jobs/index.json   files already retrieved
                                                  ~/mytutor/jobs/runs.csv     one row per run
```

## Set up on Windows (once)

1. **Put the files in a folder**, for example `C:\Users\<you>\mytutor\`
   (`retrieve.py`, `extract.py`, `config.example.json`, `requirements.txt`, `tests\`).
2. **Make the config:** copy `config.example.json` to `config.json`.
3. **Choose a mode** (below) and set its paths in `config.json`.
4. **Check it works:** open *Command Prompt*, then (use `py` if `python` is not found)
   ```
   cd %USERPROFILE%\mytutor
   python -m unittest discover tests
   ```
   You should see `OK`.

### Mode 1: `synced` (start here)

Uses the folder the OneDrive app keeps on your PC. Nothing to install, no sign-in in the script.

1. Open the **OneDrive** app (built into Windows), sign in with your **UC account**.
2. In OneDrive on the web, create `myTutor\Inbox\Day 1` and upload the Day 1 files.
3. On your PC, find the synced folder. It is usually
   `C:\Users\<you>\OneDrive - University of Canterbury\myTutor\Inbox`.
4. Put that path in `config.json` as `synced_inbox` (forward slashes or `~` are fine):
   ```json
   "synced_inbox": "~/OneDrive - University of Canterbury/myTutor/Inbox"
   ```

Files marked "available online only" are downloaded automatically when the script reads them.
A file still syncing is skipped with a note; run again a minute later.

### Mode 2: `graph` (fall-back, downloads straight from OneDrive)

Needs an app registration in Microsoft Entra ID (Azure). **UC may not let students create one**;
if the portal refuses, stay with synced mode.

1. portal.azure.com → *App registrations* → *New registration*,
   supported account types: *Accounts in any organizational directory*.
2. *Authentication* → *Allow public client flows* → **Yes**.
3. *API permissions* → Microsoft Graph → Delegated → **Files.Read**.
4. Copy the *Application (client) ID* into `config.json` → `graph.client_id`, and set
   `"mode": "graph"`.
5. `pip install -r requirements.txt`

The first run prints a code and a link: sign in with your UC account once.
The token is cached in `jobs\.token_cache.json`; **keep that file private.**

## Run it

```
python retrieve.py --folder "Day 1"             # retrieve
python retrieve.py --folder "Day 1" --dry-run   # show what would be copied
python retrieve.py --folder "Day 1" --force     # copy again, even if already retrieved
python retrieve.py --config other.json --folder "Week 2"
```

Example output:

```
retrieved          Lecture 1 - Digital Transformation.pdf
retrieved          Readings/Case - Kodak.docx
skipped_type       whiteboard.jpg  (.jpg is not in the extension list)

2 retrieved, 0 duplicate, 1 skipped, 0 failed in 0.4s
Job folder: C:\Users\<you>\mytutor\jobs\2026-10-17_103245_day-1
```

## What it does with each file

| Situation | Result |
|---|---|
| `.pdf .pptx .docx .txt .md` | copied, keeping sub-folders |
| other types (images, `.exe`) | `skipped_type`, listed in the manifest |
| over `max_file_mb` | `skipped_size` |
| same content already retrieved in an earlier job | `skipped_duplicate` (the copy is removed) |
| Office lock files `~$…`, `desktop.ini`, `Thumbs.db` | ignored |
| could not be read or downloaded | `failed`, with the reason; the rest still run |

Exit code: `0` all good · `1` at least one file failed · `2` folder not found.

## Links back to the original

Each manifest entry has an `origin`: the local OneDrive path (synced) or the OneDrive web
link (graph). The note-writing stage will put this into each reference note, so every note
links back to its original document.

## For the KPI log

`runs.csv` records every run: start, finish, seconds, and counts. That is the machine-timed part
of "time per source"; your own review time is still logged by hand.

## Stage 2: extract

Turns every retrieved file in a job into one Markdown text file, ready for the AI step.

Install the readers once (Command Prompt, in the mytutor folder):

```
py -m pip install pymupdf python-pptx python-docx
```

Then, after each retrieve:

```
py extract.py                 # the newest job
py extract.py --job <name>    # a particular job
py extract.py --force         # redo files already extracted
```

It writes `<job>\text\<file>.md` (with `## Page n` or `## Slide n` headings, slide speaker notes
included) and `<job>\extract.json` (pages, words and a guessed kind for each file).

| It does | Why |
|---|---|
| removes lines repeated on most pages (HBR "for the exclusive use of" footers, journal headers, page numbers) | they waste the AI step's tokens |
| joins words broken across lines | cleaner text |
| guesses each file's kind: `slides`, `reading` or `case` | from the folder (`Lecture`, `Readings`, `Cases`) if you use one, else the file name, else page shape |
| flags pages with almost no text | a scanned PDF needs OCR first |
| counts words per file | the KPI is minutes per 1,000 words |

The guessed kind is only a hint; the AI step confirms it from the content.

## Stage 3: generate

Sends each extracted text to Claude and stages the notes it writes, in your vault's folder structure.

Once: create an API key at platform.claude.com, then

```
setx ANTHROPIC_API_KEY "your-key"      (then open a NEW Command Prompt)
py -m pip install anthropic
```

Add to `config.json`:

```json
"vault_path": "C:/Users/henry/<your vault folder>",
"term": "T3",
"model": "claude-sonnet-5-5",
"price_per_mtok": {"input": 2.0, "output": 10.0}
```

`price_per_mtok` is only used to estimate cost in the log; set it to the prices shown in the Console.

Run:

```
py generate.py --estimate              # tokens and cost per source, no API call
py generate.py --only "Short Case"     # one source first, to check the notes (a few cents)
py generate.py                         # everything else in the newest job
py generate.py --only "Short" --force  # redo one source
```

Per source, Claude returns (through a forced tool call, so the output is always valid JSON):

| Folder | Notes |
|---|---|
| `reference` | one note: overview, key points, frameworks, questions, link to the original file |
| `core` | 3 to 6 concept notes, skipped when the concept already exists in your vault (it links instead) |
| `cases` | one per real organisation discussed as a case, only if there is one |
| `quizzes` | 5 questions built from structured quiz data; each answer explains itself and links to the note it comes from. The same questions are saved as `<job>\quiz\*.json` for the practice page |

After all sources, a journal stub `theme/<Course> <Day> - Journal.md` links that day's notes and leaves the
reflection headings empty for you.

Order matters: slides run first, so readings and cases link to the concepts the lecture defined.

Notes are **staged** in `<job>\notes\`, not written into the vault yet. Check them in a text editor or
open the `notes` folder as a vault in Obsidian, then stage 4 copies them across.

Logged per source in `<job>\generate.json` and `jobs\generate_runs.csv`: tokens, estimated cost,
seconds, notes written, links to existing notes. That is the machine side of the KPIs.

## Practice page

```
py practice.py --open
```

Builds `jobs\practice.html` from every job's `quiz\*.json` and opens it in your browser. One file,
works offline, no server.

- Pick a day and how many questions: **20** by default (set `"practice_questions"` in `config.json`),
  10, or all. They are drawn at random from that day's sources (Day 1: 10 sources × 5 = 50 questions).
- A wrong answer shows the right one, the explanation, and the key concept's definition and
  "why it matters" from its core note, with an **Open in Obsidian** link once the notes are in your vault.
- The results list the concepts to review. **Copy score for my log** copies
  `date, day, score, concepts missed` for the recall KPI.
- Recent scores are remembered in that browser only.

Run it again after each `generate.py` run to add the new day.

## Stage 4: file into the vault, and spot-check a sample

```
py file.py --day "Day 1" --dry-run          # where each note would go; nothing written
py file.py --day "Day 1" --sample 10        # file the notes, then pick 10 to spot-check
```

- Notes go into the course folder in your vault: an existing folder starting with the course code
  (e.g. `MBAM601-...`), or `course_folders` in config.json, or a new
  `<code>-<term_label> - <course name>` folder, with sub-folders from `vault_folders`
  (default `Ref`, `Core`, `Cases`, `Quizzes`, `Theme`).
- **Your edits are never overwritten.** A vault note is replaced only if it is still exactly what
  myTutor filed last time; otherwise it is reported as "KEPT YOURS".
- `--sample 10` picks 10 random notes (not the journal), lists Obsidian links to open them, and adds
  them to `jobs\quality_audit.csv` with the automatic checks already filled in (frontmatter complete,
  links to its source, links to an existing note). You fill in `accurate` (yes/no) in Excel. That sheet
  is the note-quality KPI.
- Notes keep `status: unreviewed` until you change it in Obsidian when you have actually studied them.

## Automation: run.py, n8n and Task Scheduler

`py run.py` does everything except filing: for each `<course>/<day>` folder in OneDrive with files not
seen before, it runs retrieve, extract and generate, then rebuilds the practice page. It is safe to run
often: finished work is skipped (no second Claude charge), folders still syncing wait for the next run,
and a lock stops two runs overlapping. `py run.py --dry-run` only lists what it would do.

### n8n (initial plan)

1. Node.js: `node -v`. If missing, install the LTS version from nodejs.org.
2. Install n8n once: `npm install -g n8n`
3. Start it with **start-n8n.bat** (enables the Execute Command node, which n8n 2.0 turns off by default),
   then open http://localhost:5678 and create the local owner account.
4. New workflow:
   - **Schedule Trigger**: every 15 minutes
   - **Execute Command**: `cd /d C:\Users\henry\mytutor && py run.py`
   - (optional) a notification node when the output contains `"days_processed": 1` or more
5. Turn the workflow **on** (Active / Publish).
6. To start n8n with Windows: Win+R, `shell:startup`, put a shortcut to start-n8n.bat there.

### Task Scheduler (fall-back)

Create Basic Task, daily 21:00, Start a program: `C:\Users\henry\mytutor\run_mytutor.bat`,
Start in: `C:\Users\henry\mytutor`, Run only when user is logged on. Output goes to `jobs\run_output.log`.

After either runs, spot-check and file as usual: `py file.py --day "Day 2" --sample 10`.
