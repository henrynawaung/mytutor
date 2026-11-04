"use strict";
const CSRF = document.querySelector('meta[name="csrf"]').content;
let S = {items: [], journals: [], courses: {}, stats: {}}, cur = null, mode = "notes", hist = [];
const $ = id => document.getElementById(id);

async function api(path, body) {
  const r = await fetch(path, {method: body ? "POST" : "GET", credentials: "same-origin",
    headers: {"X-CSRF": CSRF, "Content-Type": "application/json"}, body: body ? JSON.stringify(body) : undefined});
  if (r.status === 401) { location.href = "/login"; throw new Error("Please log in again."); }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || ("Error " + r.status));
  return j;
}
function toast(t) { const e = $("toast"); e.textContent = t; e.classList.add("show"); setTimeout(() => e.classList.remove("show"), 1800); }
function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c])); }
function md(t) {
  const links = [];
  t = t.replace(/\[\[([^\]|#]+)(#[^\]|]*)?(?:\|([^\]]+))?\]\]/g, (m, a, h, al) => {
    links.push(`<a class="wl" data-t="${esc(a.trim())}">${esc(al || a)}</a>`); return `@@WL${links.length - 1}@@`; });
  // notes are my own files, but render them without raw HTML anyway
  t = t.replace(/</g, "&lt;");
  let html = window.marked ? marked.parse(t, {breaks: true, gfm: true}) : "<pre>" + t + "</pre>";
  return html.replace(/@@WL(\d+)@@/g, (m, i) => links[+i]).replace(/href="(?!https?:|obsidian:|file:)[^"]*"/g, 'href="#"');
}
function filtered() {
  const c = $("f-course").value, s = $("f-status").value, ty = $("f-type").value, q = $("f-q").value.trim().toLowerCase();
  return S.items.filter(i => (!c || i.course === c) && (!s || i.status === s) && (!ty || i.type === ty) && (!q || i.title.toLowerCase().includes(q)));
}
function renderProg() {
  const P = $("prog"); P.innerHTML = "";
  for (const [c, v] of Object.entries(S.courses).sort()) {
    const span = document.createElement("span");
    span.innerHTML = `${esc(c)} ${v.reviewed}/${v.total}<span class="bar"><i></i></span>`;
    span.querySelector("i").style.width = (v.total ? 100 * v.reviewed / v.total : 0) + "%";
    P.appendChild(span);
  }
  const st = S.stats || {};
  $("stats").textContent = `Today ${st.today || 0} · Streak ${st.streak || 0} day${st.streak === 1 ? "" : "s"}`;
}
function renderList() {
  const L = $("list");
  if (mode === "journals") {
    L.innerHTML = S.journals.map(j => `<div class="item${cur && cur.rel === j.rel ? " on" : ""}${hasDraft(j.rel) ? " draft" : ""}" data-r="${esc(j.rel)}"><b>${esc(j.title)}</b><small>${j.open} open prompt${j.open > 1 ? "s" : ""}</small></div>`).join("")
      || '<div class="item"><small>No open prompts. Nice.</small></div>';
    return;
  }
  const f = filtered();
  L.innerHTML = `<div class="item"><small>${f.length} note${f.length === 1 ? "" : "s"}</small></div>` + f.slice(0, 500).map(i =>
    `<div class="item${cur && cur.rel === i.rel ? " on" : ""}${hasDraft(i.rel) ? " draft" : ""}" data-r="${esc(i.rel)}"><b>${esc(i.title)}</b><small>${esc(i.course)} · ${esc(i.day)} · ${esc(i.type)}</small></div>`).join("");
}
async function load() {
  S = await api("/api/summary");
  const sel = $("f-course"), v = sel.value;
  sel.innerHTML = '<option value="">All courses</option>' + Object.keys(S.courses).sort().map(c => `<option>${esc(c)}</option>`).join("");
  sel.value = v; renderProg(); renderList();
}
async function openNote(rel, push = true) {
  try {
    if (cur && push) hist.push(cur.rel);
    cur = await api("/api/note?rel=" + encodeURIComponent(rel)); hideBanner(); renderList(); show();
    curIdx = Math.max(0, (mode === "journals" ? S.journals : filtered()).findIndex(x => x.rel === rel));
  } catch (e) { toast(e.message); }
}
function show() {
  const n = cur, p = n.props, V = $("view");
  const chips = [p.course, p.type, n.rel.split("/")[1], p.status].filter(Boolean).map(x => `<span class="chip st-${esc(x)}">${esc(x)}</span>`).join("")
    + (p.reviewed_on ? `<span class="chip">reviewed ${esc(p.reviewed_on)}</span>` : "")
    + (p.fix_note ? `<span class="chip st-needs-fix">fix: ${esc(p.fix_note)}</span>` : "");
  if (mode === "journals") {
    V.innerHTML = `<div class="doc"><div class="meta">${chips}</div><h1>${esc(n.title)}</h1>` + n.prompts.map(q =>
      `<div class="prompt"><p>${esc(q.question)}</p>` + (q.answer
        ? `<div class="done md">${md(q.answer)}</div><div class="gap"><button class="b small" data-edit="${q.i}">Edit answer</button></div>
           <div class="editwrap" data-w="${q.i}" hidden><textarea data-i="${q.i}">${esc(q.answer)}</textarea><div class="gap"><button class="b ok" data-ans="${q.i}">Save answer</button></div></div>`
        : `<textarea data-i="${q.i}" placeholder="My answer, in my own words…"></textarea><div class="gap"><button class="b ok" data-ans="${q.i}">Save answer</button></div>`)
      + `</div>`).join("") + "</div>";
    V.querySelectorAll("textarea").forEach(ta => { keepDraft(ta, dkey("ans", n.rel, ta.dataset.i)); enhance(ta); });
    $("actions").hidden = true; return;
  }
  V.innerHTML = `<div class="doc"><div class="meta">${chips}</div>${md(n.body)}</div>
    <div class="take"><label for="take">My take (saved into the note, dated)</label><textarea id="take" placeholder="In my own words / where I have seen this / what I would do with it…"></textarea>
    <div class="gap"><button class="b" id="b-take">Save my take</button></div></div>`;
  $("actions").hidden = false;
  const o = $("b-obs"); if (n.obsidian) { o.href = n.obsidian; o.hidden = false; } else o.hidden = true;
  V.scrollTop = 0; $("b-take").onclick = saveTake; enhance($("take"), {template: true});
  keepDraft($("take"), dkey("take", n.rel)); $("take").addEventListener("input", labels); labels();
}
const ACT = {"approve": "✓ approved", "needs-fix": "⚑ needs fix", "my-take": "✎ take", "answer": "💬 reflection", "undo": "↩ undo"};
const TYPES = {"case": "Cases", "core": "Core", "hub": "Hubs", "reference": "Sources", "reflection": "Reflections", "other": "Other"};
function niceDay(d) { return new Date(d + "T12:00:00").toLocaleDateString(undefined, {weekday: "short", day: "numeric", month: "short", year: "numeric"}); }
function plural(n, w) { return `${n} ${w}${n === 1 ? "" : "s"}`; }
async function showActivity() {
  const {days, stats} = await api("/api/days");
  const wk = days.filter(d => (Date.now() - new Date(d.day + "T12:00:00")) / 864e5 < 7)
    .reduce((a, d) => ({approve: a.approve + d.approve, take: a.take + d["my-take"], ans: a.ans + d.answer}), {approve: 0, take: 0, ans: 0});
  $("view").innerHTML = `<div class="doc"><h1>My days</h1>
    <p class="weekline"><b>Last 7 days:</b> ${plural(wk.approve, "approval")} · ${plural(wk.take, "take")} · ${plural(wk.ans, "reflection")} · streak ${plural(stats.streak || 0, "day")}</p>` +
    (days.map(d => `<div class="daycard" data-day="${d.day}">
      <div class="dayhead"><b>${esc(niceDay(d.day))}</b>
        <span>${d.approve} approved · ${d["my-take"]} takes · ${d.answer} reflections${d["needs-fix"] ? " · " + d["needs-fix"] + " needs fix" : ""}</span>
        <small>${Object.entries(d.types).map(([t, n]) => { const w = (TYPES[t] || t).toLowerCase(); return `${n} ${n === 1 && w !== "core" ? w.replace(/s$/, "") : w}`; }).join(" · ")}</small>
        <span class="chev">▸</span></div>
      <div class="daybody" hidden></div></div>`).join("") || '<p class="empty">Nothing yet. Approve a note or write a take, and your day shows up here.</p>') + "</div>";
  $("actions").hidden = true;
}
async function openDay(card) {
  const body = card.querySelector(".daybody"), open = body.hidden;
  card.classList.toggle("open", open); body.hidden = !open;
  if (!open || body.dataset.loaded) return;
  const notes = await api("/api/day?d=" + card.dataset.day);
  const groups = {};
  for (const n of notes) (groups[n.type === "theme" ? "reflection" : (n.type || "other")] ||= []).push(n);
  body.innerHTML = Object.keys(TYPES).filter(t => groups[t]).map(t => `<h3>${TYPES[t]} (${groups[t].length})</h3>` + groups[t].map(n =>
    `<div class="dayitem"><div class="dayitemhead" data-x="1"><b>${esc(n.title)}</b><small>${esc(n.course)}</small>
       <span class="tags">${[...new Set(n.actions.map(a => ACT[a.action] || a.action))].map(x => `<span class="chip">${esc(x)}</span>`).join("")}</span><span class="chev">▸</span></div>
     <div class="dayitembody" hidden>${n.actions.map(a => `<div class="upd"><small>${esc(a.at)} · ${esc(ACT[a.action] || a.action)}</small>${a.detail ? `<div class="md">${md(a.detail)}</div>` : ""}</div>`).join("")}
       <button class="b small" data-open="${esc(n.rel)}" data-kind="${n.type === "theme" ? "journals" : "notes"}">Open note</button></div></div>`).join("")).join("");
  body.dataset.loaded = "1";
}
let curIdx = 0;
function next() {
  const f = mode === "journals" ? S.journals : filtered();
  const i = f.findIndex(x => cur && x.rel === cur.rel);
  // if the note just left this list (e.g. approved while viewing "To review"), the next one now sits at its old place
  const n = i >= 0 ? (f[i + 1] || f[0]) : (f[curIdx] || f[0]);
  if (n && (!cur || n.rel !== cur.rel)) return openNote(n.rel); toast("That was the last one");
}
async function act(path, extra, msg) {
  try { const rel = cur.rel; const r = await api(path, Object.assign({rel, mtime: cur.mtime}, extra || {})); cur = r.note;
    if (path === "/api/take") dset(dkey("take", rel), "");
    if (path === "/api/answer") dset(dkey("ans", rel, extra.i), ""); if (msg) toast(msg); await load(); return true; }
  catch (e) { toast(e.message); return false; }
}
let undoStatus = null;
function banner(msg, kind, canUndo, showNext = true) {
  const b = $("banner"); $("banner-msg").textContent = msg; b.className = "banner " + kind; b.hidden = false;
  $("b-undo").hidden = !canUndo; $("b-next").hidden = !showNext; if (showNext) $("b-next").focus({preventScroll: true});
}
function hideBanner() { $("banner").hidden = true; undoStatus = null; }
async function setStatus(path, extra, msg, kind) {
  const before = cur.props.status || "unreviewed", title = cur.title;
  const draft = $("take") && $("take").value.trim();
  if (draft && !(await act("/api/take", {take: draft}, ""))) return;     // never lose an unsaved take
  if (await act(path, extra, "")) { show(); undoStatus = before; banner(msg + title + (draft ? " (your take was saved too)" : ""), kind, true); }
}
async function approve() { await setStatus("/api/approve", null, "✓ Approved and saved: ", "ok"); }
async function approveNext() {
  const title = cur.title, draft = $("take") && $("take").value.trim();
  if (draft && !(await act("/api/take", {take: draft}, ""))) return;
  if (await act("/api/approve", null, "")) { await next(); banner("✓ Approved" + (draft ? " and take saved" : "") + ": " + title + "  ·  now on the next note", "ok", false, false); }
}
function labels() {
  const has = $("take") && $("take").value.trim();
  $("b-okn").textContent = has ? "Save take, Approve & Next →" : "Approve & Next →";
  $("b-ok").textContent = has ? "Save take & Approve" : "Approve";
}
async function fix() { const why = prompt("What needs fixing?"); if (why === null) return; await setStatus("/api/needs-fix", {why}, "⚑ Marked for fixing: ", "warn"); }
async function undoLast() { if (!undoStatus) return; const s = undoStatus; if (await act("/api/undo", {status: s}, "")) { show(); banner("↩ Undone. Status is back to " + s + ": " + cur.title, "info", false); } }
async function saveTake() { const t = $("take").value.trim(); if (!t) return; if (await act("/api/take", {take: t}, "")) { show(); banner("✓ Take saved: " + cur.title, "ok", false); } }
function setMode(m) {
  mode = m; cur = null;
  for (const t of ["notes", "journals", "activity"]) $("t-" + t).classList.toggle("on", t === m);
  $("side").hidden = m === "activity"; document.querySelector("main").classList.toggle("noside", m === "activity"); $("actions").hidden = true;
  document.querySelector(".filters").hidden = $("f-q").hidden = m !== "notes";
  if (m === "activity") return showActivity();
  $("view").innerHTML = `<div class="empty">${m === "journals" ? "Pick a journal with open prompts." : "Pick a note on the left."}</div>`;
  renderList();
}
document.addEventListener("click", async e => {
  const op = e.target.closest("[data-open]");
  if (op) { setMode(op.dataset.kind); return openNote(op.dataset.open); }
  const ih = e.target.closest(".dayitemhead");
  if (ih) { const b = ih.nextElementSibling; b.hidden = !b.hidden; ih.parentElement.classList.toggle("open", !b.hidden); return; }
  const dh = e.target.closest(".dayhead"); if (dh) return openDay(dh.parentElement);
  const it = e.target.closest(".item[data-r]"); if (it) return openNote(it.dataset.r);
  const wl = e.target.closest("a.wl");
  if (wl) { e.preventDefault(); const r = await api("/api/find?title=" + encodeURIComponent(wl.dataset.t)); r.rel ? openNote(r.rel) : toast(`No note called “${wl.dataset.t}” yet`); return; }
  const ed = e.target.closest("[data-edit]");
  if (ed) { const w = document.querySelector(`[data-w="${ed.dataset.edit}"]`); w.hidden = false; ed.hidden = true; w.querySelector("textarea").dispatchEvent(new Event("input")); return; }
  const a = e.target.closest("[data-ans]");
  if (a) { const ta = document.querySelector(`textarea[data-i="${a.dataset.ans}"]`); if (!ta.value.trim()) return;
    if (await act("/api/answer", {i: +a.dataset.ans, answer: ta.value}, "Answer saved")) show(); }
});
$("b-ok").onclick = approve; $("b-fix").onclick = fix; $("b-skip").onclick = next;
$("b-next").onclick = next; $("b-undo").onclick = undoLast; $("b-okn").onclick = approveNext;
$("b-sync").onclick = async () => { try { const r = await api("/api/sync", {}); await load(); toast(`Refreshed: ${r.changed} change${r.changed === 1 ? "" : "s"}`); } catch (e) { toast(e.message); } };
["f-course", "f-status", "f-type"].forEach(id => $(id).onchange = renderList);
$("f-q").oninput = renderList;
$("t-notes").onclick = () => setMode("notes"); $("t-journals").onclick = () => setMode("journals"); $("t-activity").onclick = () => setMode("activity");
document.addEventListener("keydown", e => {
  if (/TEXTAREA|INPUT|SELECT/.test(e.target.tagName) || !cur || mode !== "notes") return;
  const k = e.key.toLowerCase();
  if (k === "a" && e.shiftKey) approveNext(); else if (k === "a") approve(); else if (k === "f") fix(); else if (k === "s" || k === "n" || k === "arrowright") next();
  else if (k === "arrowleft" && hist.length) openNote(hist.pop(), false);
  else if (k === "t") { e.preventDefault(); $("take").focus(); }
});
load().then(() => { const f = filtered(); if (f.length) openNote(f[0].rel); }).catch(e => toast(e.message));

// ---------------------------------------------------------------- drafts (kept in this browser until saved)
function dkey(kind, rel, i) { return `mytutor-draft:${kind}:${rel}${i === undefined ? "" : ":" + i}`; }
function dget(k) { try { return localStorage.getItem(k) || ""; } catch (e) { return ""; } }
function dset(k, v) { try { v.trim() ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch (e) {} }
function hasDraft(rel) { try { for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (k.startsWith("mytutor-draft:") && k.includes(":" + rel)) return true; } } catch (e) {} return false; }
function keepDraft(ta, key) {
  const saved = dget(key);
  if (saved && !ta.value) { ta.value = saved; const t = document.createElement("small"); t.className = "restored"; t.textContent = "✎ Draft restored (not saved to the note yet)"; ta.after(t); }
  ta.addEventListener("input", () => { dset(key, ta.value); markDraft(); });
}
function markDraft() { if (!cur) return; const el = document.querySelector(`.item[data-r="${CSS.escape(cur.rel)}"]`); if (el) el.classList.toggle("draft", hasDraft(cur.rel)); }

// ---------------------------------------------------------------- Markdown editor (toolbar, preview, auto-grow)
function enhance(ta, opts = {}) {
  if (!ta || ta.dataset.enh) return;
  ta.dataset.enh = "1";
  const bar = document.createElement("div"); bar.className = "tb";
  const pv = document.createElement("div"); pv.className = "pv md"; pv.hidden = true;
  const tools = [["B", "Bold (Ctrl+B)", () => wrap(ta, "**")], ["I", "Italic (Ctrl+I)", () => wrap(ta, "*")],
    ["H", "Heading", () => prefix(ta, "#### ")], ["•", "Bullet list", () => prefix(ta, "- ")],
    ["1.", "Numbered list", () => prefix(ta, "1. ", true)], ["❝", "Quote", () => prefix(ta, "> ")],
    ["🔗", "Link", () => wrap(ta, "[", "](https://)")], ["[[ ]]", "Link to a note", () => wrap(ta, "[[", "]]")]];
  for (const [label, title, fn] of tools) {
    const b = document.createElement("button"); b.type = "button"; b.textContent = label; b.title = title;
    b.onclick = () => { fn(); ta.focus(); grow(); }; bar.appendChild(b);
  }
  if (opts.template) {
    const tp = document.createElement("button"); tp.type = "button"; tp.textContent = "Template"; tp.className = "tpbtn";
    tp.title = "Insert my four headings"; tp.onclick = () => { insertTemplate(ta); ta.focus(); grow(); }; bar.appendChild(tp);
  }
  const prev = document.createElement("button"); prev.type = "button"; prev.textContent = "Preview"; prev.className = "pvbtn";
  prev.onclick = () => { const on = pv.hidden; pv.hidden = !on; ta.hidden = on; prev.textContent = on ? "Edit" : "Preview";
    if (on) pv.innerHTML = md(ta.value || "*Nothing yet.*"); else ta.focus(); };
  bar.appendChild(prev);
  ta.before(bar); ta.after(pv);
  const grow = () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight + 4, window.innerHeight * 0.6) + "px"; };
  ta.addEventListener("input", grow); setTimeout(grow, 0);
  ta.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") { e.preventDefault(); wrap(ta, "**"); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "i") { e.preventDefault(); wrap(ta, "*"); }
    else if (e.key === "Enter" && !e.shiftKey) continueList(ta, e);
  });
}
function wrap(ta, a, b = a) {
  const {selectionStart: s, selectionEnd: e, value: v} = ta, sel = v.slice(s, e);
  ta.setRangeText(a + sel + b, s, e, "end");
  if (!sel) ta.setSelectionRange(s + a.length, s + a.length);
  ta.dispatchEvent(new Event("input"));
}
function prefix(ta, p, numbered = false) {
  const v = ta.value, s = v.lastIndexOf("\n", ta.selectionStart - 1) + 1;
  let e = v.indexOf("\n", ta.selectionEnd); if (e < 0) e = v.length;
  const lines = v.slice(s, e).split("\n");
  const has = lines.every(l => numbered ? /^\d+\. /.test(l) : l.startsWith(p));
  const out = lines.map((l, i) => has ? l.replace(numbered ? /^\d+\. / : p, "") : (numbered ? `${i + 1}. ` : p) + l.replace(/^(- |\d+\. |> |#### )/, ""));
  ta.setRangeText(out.join("\n"), s, e, "end"); ta.dispatchEvent(new Event("input"));
}
function continueList(ta, e) {
  const v = ta.value, pos = ta.selectionStart, s = v.lastIndexOf("\n", pos - 1) + 1, line = v.slice(s, pos);
  const m = line.match(/^(\s*)(- |\* |> |(\d+)\. )(.*)$/);
  if (!m) return;
  e.preventDefault();
  if (!m[4].trim()) { ta.setRangeText("\n", s, pos, "end"); ta.dispatchEvent(new Event("input")); return; }  // empty item ends the list
  const next = m[3] ? `${+m[3] + 1}. ` : m[2];
  ta.setRangeText("\n" + m[1] + next, pos, ta.selectionEnd, "end"); ta.dispatchEvent(new Event("input"));
}

function insertTemplate(ta) {
  // the note's own source: "**Source:** [[X]]" in the body, else the source property, else blank
  const m = cur && cur.body.match(/\*\*Source:\*\*\s*(\[\[[^\]]+\]\])/);
  const src = m ? m[1] : (cur && cur.props.source ? cur.props.source : "");
  const t = `#### 📖 Where I came across this\n${src}\n\n#### 💭 My experience and observation\n\n\n#### 🎯 What I would apply in the future\n- \n\n#### 💡 My key takeaway\n`;
  const pos = ta.selectionStart, before = ta.value.slice(0, pos);
  const sep = before && !before.endsWith("\n\n") ? (before.endsWith("\n") ? "\n" : "\n\n") : "";
  ta.setRangeText(sep + t, pos, ta.selectionEnd, "end");
  const at = ta.value.indexOf("#### 💭 My experience and observation\n", pos) + "#### 💭 My experience and observation\n".length;
  ta.setSelectionRange(at, at);                                    // cursor ready under "My experience"
  ta.dispatchEvent(new Event("input"));
}
