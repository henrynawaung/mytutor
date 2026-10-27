"""myTutor practice page: build a self-contained quiz page from the generated quiz data.

Usage
    py practice.py                 # every job that has quiz data -> jobs\\practice.html
    py practice.py --open          # build it and open it in your browser

Reads   <job>/quiz/*.json                 questions from generate.py
        <job>/notes/core/*.md, vault core/*.md   definitions shown when you get a question wrong
Writes  <jobs_root>/practice.html         one file, works offline, no server needed

On the page: pick a day and answer its fixed practice set (or, before the set exists, random questions) from that day's sources. A wrong answer shows the right
one, the explanation and the key concept's definition. The summary lists the concepts to review.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import webbrowser
from pathlib import Path

PRACTICE_SET = "practice-set.json"


def read_concepts(*folders: Path) -> dict:
    """title -> {definition, why} from core notes ('**Definition:** ...' lines)."""
    concepts = {}
    for folder in folders:
        if not folder or not folder.exists():
            continue
        for p in folder.rglob("*.md"):
            text = p.read_text(encoding="utf-8", errors="replace")
            d = re.search(r"\*\*Definition:\*\*\s*(.+)", text)
            w = re.search(r"\*\*Why it matters:\*\*\s*(.+)", text)
            if d:
                concepts[p.stem] = {"definition": d.group(1).strip(), "why": w.group(1).strip() if w else ""}
    return concepts


def collect(jobs_root: Path, vault: Path | None, vault_name: str = "") -> dict:
    """Each day: its fixed practice set if one was built, else all its questions as a pool."""
    days: dict = {}
    fixed: dict = {}
    core_dirs = [d for d in vault.rglob("*") if d.is_dir() and d.name.lower() == "core"] if vault and vault.exists() else []
    for job in sorted(jobs_root.glob("*")):
        qdir = job / "quiz"
        if not qdir.is_dir():
            continue
        core_dirs.append(job / "notes" / "core")
        for f in sorted(qdir.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            key = f"{data.get('course', '')} {data.get('day', '')}".strip()
            if f.name == PRACTICE_SET:
                if key not in fixed or data.get("built", "") >= fixed[key].get("built", ""):
                    fixed[key] = data
                continue
            day = days.setdefault(key, {"label": key, "questions": []})
            for q in data.get("questions", []):
                qid = f"{f.stem}#{q['question']}"
                if any(x["id"] == qid for x in day["questions"]):
                    continue                     # same question from a re-run
                day["questions"].append({**q, "id": qid, "source": data.get("source_title", ""),
                                         "reference": data.get("reference", "")})
    for key, data in fixed.items():
        days[key] = {"label": key, "fixed": True, "built": data.get("built", ""),
                     "questions": [{**q, "id": f"set#{i}"} for i, q in enumerate(data.get("questions", []))]}
    vault_name = vault_name or (vault.name if vault else "")
    concepts = read_concepts(*core_dirs)
    return {"days": sorted(days.values(), key=lambda d: natural_key(d["label"])), "concepts": concepts,
            "vault": vault_name}


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def build_html(payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return PAGE.replace("/*DATA*/null", data)


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>myTutor Practice</title>
<style>
:root{--paper:#F3EFE6;--card:#FBF9F4;--ink:#141A2E;--soft:#4A5568;--line:#D8CFBD;--rule:#E7E0D1;
--teal:#1F6F62;--teal-bg:#DDEDE8;--red:#B23A0B;--red-bg:#F8E3D9;--accent:#C2410C;--focus:#2563EB}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#141A2E;--card:#1C2440;--ink:#F3EFE6;
--soft:#BFC8D6;--line:#34405F;--rule:#1F2742;--teal:#7FCDBB;--teal-bg:#18352F;--red:#F2A07B;--red-bg:#3A221A;--accent:#E9A47F}}
:root[data-theme="dark"]{--paper:#141A2E;--card:#1C2440;--ink:#F3EFE6;--soft:#BFC8D6;--line:#34405F;--rule:#1F2742;
--teal:#7FCDBB;--teal-bg:#18352F;--red:#F2A07B;--red-bg:#3A221A;--accent:#E9A47F}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:17px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;
background-image:repeating-linear-gradient(180deg,transparent 0 31px,var(--rule) 31px 32px)}
main{max-width:760px;margin:0 auto;padding:32px 16px 64px}
.mono{font-family:ui-monospace,"Cascadia Mono",Consolas,monospace;font-size:14px;color:var(--accent)}
h1{font-family:Georgia,"Times New Roman",serif;font-size:40px;margin:4px 0 8px;line-height:1.1}
h2{font-family:Georgia,serif;font-size:24px;line-height:1.3;margin:6px 0 18px}
p.lead{color:var(--soft);margin:0 0 24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:24px;box-shadow:0 6px 18px rgba(20,26,46,.07)}
label.small{display:block;font-size:14px;color:var(--soft);margin-bottom:6px}
select,button{font:inherit}
select{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:6px;background:var(--paper);color:var(--ink)}
.row{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap;margin-top:18px}
.btn{background:var(--ink);color:var(--paper);border:0;border-radius:6px;padding:11px 20px;cursor:pointer;font-weight:600}
.btn.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}
.btn:disabled{opacity:.4;cursor:default}
button:focus-visible,select:focus-visible{outline:3px solid var(--focus);outline-offset:2px}
.progress{height:6px;background:var(--rule);border-radius:3px;overflow:hidden;margin:10px 0 20px}
.progress>i{display:block;height:100%;background:var(--teal);width:0;transition:width .3s}
.opts{display:grid;gap:10px}
.opt{display:flex;gap:12px;text-align:left;width:100%;padding:12px 14px;border:1px solid var(--line);border-radius:6px;
background:var(--paper);color:var(--ink);cursor:pointer;line-height:1.4}
.opt b{font-family:ui-monospace,Consolas,monospace;min-width:1.2em}
.opt:hover:not(:disabled){border-color:var(--ink)}
.opt.right{border:2px solid var(--teal);background:var(--teal-bg)}
.opt.wrong{border:2px solid var(--red);background:var(--red-bg)}
.opt:disabled{cursor:default}
.feedback{margin-top:18px;padding:16px;border-radius:6px;border-left:5px solid var(--teal);background:var(--teal-bg)}
.feedback.bad{border-left-color:var(--red);background:var(--red-bg)}
.feedback p{margin:6px 0}
.concept{margin-top:12px;padding:12px 14px;background:var(--card);border:1px dashed var(--line);border-radius:6px}
.concept .mono{color:var(--teal)}
.source{font-size:14px;color:var(--soft);margin-top:8px}
a{color:var(--teal)}
.score{font-family:Georgia,serif;font-size:56px;line-height:1;margin:8px 0}
ul.review{padding-left:20px}
ul.review li{margin:8px 0}
.history{font-size:14px;color:var(--soft);margin-top:16px}
.empty{color:var(--soft)}
</style>
</head>
<body>
<main>
  <p class="mono">mytutor / practice</p>
  <h1>Practice quiz</h1>
  <p class="lead">Practise one day’s sources. Get a question wrong and you’ll see the right answer and the concept behind it.</p>
  <div id="app" class="card" aria-live="polite"></div>
</main>
<script>
const DATA = /*DATA*/null;
const app = document.getElementById('app');
const L = 'ABCD';
let state = null;

function esc(s){return String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function md(s){return esc(s).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/\*([^*\s][^*]*?)\*/g,'<i>$1</i>').replace(/\[\[([^\]|]+)(\|([^\]]+))?\]\]/g,(m,a,b,c)=>c||a);}
function store(k,v){try{ if(v===undefined) return JSON.parse(localStorage.getItem(k)||'null'); localStorage.setItem(k,JSON.stringify(v)); }catch(e){ return null; }}
function shuffle(a){a=a.slice();for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;}
function obsidian(title,folder){ if(!DATA.vault||!title) return ''; return 'obsidian://open?vault='+encodeURIComponent(DATA.vault)+'&file='+encodeURIComponent(title); }

function home(){
  if(!DATA.days.length){ app.innerHTML='<p class="empty">No quiz data yet. Run generate.py, then practice.py again.</p>'; return; }
  const last = store('mytutor.lastDay');
  const opts = DATA.days.map((d,i)=>`<option value="${i}" ${d.label===last?'selected':''}>${esc(d.label)} · ${d.fixed?'practice set, ':''}${d.questions.length} questions</option>`).join('');
  const hist = (store('mytutor.history')||[]).slice(-5).reverse()
    .map(h=>`<li>${esc(h.date)} · ${esc(h.day)} · ${h.score}/${h.total}</li>`).join('');
  app.innerHTML = `<label class="small" for="day">Day</label><select id="day">${opts}</select>
    <div id="countbox"><label class="small" for="count" style="margin-top:16px">Questions</label>
    <select id="count">${[10,20,0].map(n=>`<option value="${n}" ${n===(store('mytutor.count')??DATA.count)?'selected':''}>${n?n:'All'}</option>`).join('')}</select></div>
    <div class="row"><span class="source" id="hint"></span><button class="btn" id="start">Start</button></div>
    ${hist?`<div class="history"><p class="mono">recent scores on this device</p><ul class="review">${hist}</ul></div>`:''}`;
  const sel=document.getElementById('day');
  const sync=()=>{ const d=DATA.days[+sel.value];
    document.getElementById('countbox').hidden=!!d.fixed;
    document.getElementById('hint').textContent = d.fixed
      ? `The same ${d.questions.length} questions every time, built once on ${d.built}.`
      : 'No practice set yet for this day: questions are drawn at random from its sources.'; };
  sel.onchange=sync; sync();
  document.getElementById('start').onclick=()=>{
    const d = DATA.days[+sel.value];
    store('mytutor.lastDay', d.label);
    let qs;
    if(d.fixed){ qs=d.questions.slice(); }
    else { const n=+document.getElementById('count').value; store('mytutor.count', n); qs=n?shuffle(d.questions).slice(0,n):shuffle(d.questions); }
    state={day:d.label, qs, i:0, score:0, missed:[]};
    question();
  };
}

function question(){
  const q=state.qs[state.i], n=state.qs.length;
  app.innerHTML=`<div class="row" style="margin:0"><span class="mono">${esc(state.day)} · question ${state.i+1} of ${n}</span><span class="mono">score ${state.score}</span></div>
    <div class="progress"><i style="width:${state.i/n*100}%"></i></div>
    <h2>${md(q.question)}</h2>
    <div class="opts">${q.options.map((o,j)=>`<button class="opt" data-j="${j}"><b>${L[j]}</b><span>${md(o)}</span></button>`).join('')}</div>
    <div id="fb"></div>`;
  app.querySelectorAll('.opt').forEach(b=>b.onclick=()=>answer(+b.dataset.j));
  app.querySelector('.opt').focus();
}

function answer(j){
  const q=state.qs[state.i], ok=j===q.answer;
  app.querySelectorAll('.opt').forEach(b=>{const k=+b.dataset.j; b.disabled=true;
    if(k===q.answer) b.classList.add('right'); else if(k===j) b.classList.add('wrong');});
  if(ok) state.score++; else state.missed.push(q);
  const c = DATA.concepts[q.concept];
  const link = obsidian(c?q.concept:q.reference, c?'core':'reference');
  const concept = !ok ? `<div class="concept"><p class="mono">key concept · ${esc(q.concept||q.reference)}</p>
      ${c?`<p>${md(c.definition)}</p>${c.why?`<p><i>Why it matters:</i> ${md(c.why)}</p>`:''}`:'<p>See the reference note for this source.</p>'}
      ${link?`<p><a href="${link}">Open in Obsidian</a></p>`:''}</div>`:'';
  document.getElementById('fb').innerHTML=`<div class="feedback ${ok?'':'bad'}">
      <p><b>${ok?'Correct.':'Not quite. The answer is '+L[q.answer]+'.'}</b> ${md(q.explanation)}</p>
      ${concept}<p class="source">From: ${esc(q.source)}</p></div>
    <div class="row"><span></span><button class="btn" id="next">${state.i+1<state.qs.length?'Next question':'See results'}</button></div>`;
  const nx=document.getElementById('next'); nx.focus();
  nx.onclick=()=>{ state.i++; state.i<state.qs.length?question():results(); };
}

function results(){
  const n=state.qs.length, h=store('mytutor.history')||[];
  h.push({date:new Date().toISOString().slice(0,10), day:state.day, score:state.score, total:n}); store('mytutor.history',h);
  const seen=new Set(), review=state.missed.filter(q=>{const k=q.concept||q.reference; if(seen.has(k)) return false; seen.add(k); return true;});
  const items=review.map(q=>{const c=DATA.concepts[q.concept]; const link=obsidian(c?q.concept:q.reference,c?'core':'reference');
    return `<li><b>${esc(q.concept||q.reference)}</b>${c?` · ${md(c.definition)}`:''}${link?` · <a href="${link}">open</a>`:''}</li>`;}).join('');
  app.innerHTML=`<p class="mono">${esc(state.day)} · results</p><p class="score">${state.score}/${n}</p>
    ${review.length?`<h2>Concepts to review</h2><ul class="review">${items}</ul>`:'<h2>All correct. Nothing to review.</h2>'}
    <div class="row"><button class="btn ghost" id="copy">Copy score for my log</button><button class="btn" id="again">Practise again</button></div>`;
  document.getElementById('again').onclick=home;
  document.getElementById('copy').onclick=async e=>{
    const line=`${new Date().toISOString().slice(0,10)}\t${state.day}\t${state.score}/${n}\t${review.map(q=>q.concept||q.reference).join('; ')}`;
    try{await navigator.clipboard.writeText(line); e.target.textContent='Copied';}catch(_){e.target.textContent=line;}
  };
}
home();
</script>
</body>
</html>
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the myTutor practice page.")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--open", action="store_true", help="open the page when built")
    args = parser.parse_args(argv)
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8")) if Path(args.config).exists() else {}
    jobs_root = Path(os.path.expandvars(os.path.expanduser(cfg.get("jobs_root", "~/mytutor/jobs"))))
    vault = Path(os.path.expanduser(cfg["vault_path"])) if cfg.get("vault_path") else None
    payload = collect(jobs_root, vault, cfg.get("obsidian_vault_name", ""))
    payload["count"] = int(cfg.get("practice_questions", 20))
    out = jobs_root / "practice.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_html(payload), encoding="utf-8")
    total = sum(len(d["questions"]) for d in payload["days"])
    print(f"{len(payload['days'])} day(s), {total} questions, {len(payload['concepts'])} concept definitions")
    print(f"Practice page: {out}")
    if args.open:
        webbrowser.open(out.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
