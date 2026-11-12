"use strict";
// ---- display settings (kept in this browser) ----
const SET_DEF = {remind: "off", size: "m", theme: "auto", font: "sans", width: "normal", photo: "soft", goal: "5", accent: "amber", density: "comfy", name: "", today: "clock,wx,rank,quote,crew,mem", ellie: "auto", movebreak: "30", rewards: "on", chime: "kalimba", city: "Christchurch"};
function getSet() { try { return Object.assign({}, SET_DEF, JSON.parse(localStorage.getItem("mytutor-settings") || "{}")); } catch (e) { return {...SET_DEF}; } }
function applySet(s) {
  const r = document.documentElement;
  r.dataset.size = s.size; r.dataset.font = s.font; r.dataset.width = s.width; r.dataset.photo = s.photo; r.dataset.accent = s.accent; r.dataset.density = s.density;
  if (s.theme === "auto") delete r.dataset.theme; else r.dataset.theme = s.theme;
  document.querySelectorAll(".seg[data-set]").forEach(g => g.querySelectorAll("button").forEach(b => b.classList.toggle("on", b.dataset.v === s[g.dataset.set])));
}
applySet(getSet());
function saveSet(k, v) { const s = getSet(); s[k] = v; try { localStorage.setItem("mytutor-settings", JSON.stringify(s)); } catch (e) {} applySet(s); renderProg(); }
function greeting() { const h = new Date().getHours(), n = getSet().name.trim();
  return (h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening") + (n ? ", " + n : ""); }
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
  return S.items.filter(i => (!c || i.course === c) && (!s || i.status === s) && (!ty || i.type === ty) && (!q || i.title.toLowerCase().includes(q)))
    .sort(byCourseDay);
}
// Library order: course A-Z, then Day 1, 2 … 10 (or dates oldest first), Hubs last; notes keep their order inside a day
function dayRank(i) {
  if (i.rel.startsWith("Hubs/")) return [2, 0, ""];
  const d = String(i.day || "");
  if (/^\d{4}-\d{2}-\d{2}$/.test(d)) return [0, 0, d];
  const m = d.match(/day[\s-]*(\d+)/i); if (m) return [0, +m[1], ""];
  return [1, 0, d];
}
function byCourseDay(a, b) {
  const c = String(a.course || "").localeCompare(String(b.course || "")); if (c) return c;
  const x = dayRank(a), y = dayRank(b);
  return x[0] - y[0] || x[1] - y[1] || x[2].localeCompare(y[2]);
}
function renderProg() {
  if ($("today") && todayOn().has("week")) renderWeek();
  const P = $("prog"); if (!P) return; P.innerHTML = "";
  for (const [c, v] of Object.entries(S.courses || {}).sort()) {
    const row = document.createElement("div"); row.className = "prow";
    row.innerHTML = `<span>${esc(c)}</span><span class="bar"><i></i></span><small>${v.reviewed}/${v.total}</small>`;
    row.querySelector("i").style.width = (v.total ? 100 * v.reviewed / v.total : 0) + "%";
    P.appendChild(row);
  }
  const st = S.stats || {}, goal = weeklyGoal(), done = st.approved_week ?? 0, target = weeklyTarget(), stretch = target > goal;
  $("goal-txt").textContent = `${Math.min(done, 999)}/${target}`;
  $("streak-txt").textContent = stretch ? `stretch +${target - goal} · 🔥${st.week_streak || 0} wk` : `this week · 🔥${st.week_streak || 0} wk`;
  const ring = $("goal-ring"), C = 2 * Math.PI * 15, base = stretch ? target - 5 : 0;
  ring.style.strokeDasharray = C; ring.style.strokeDashoffset = C * (1 - Math.min(1, (done - base) / (target - base)));
  $("goal").classList.toggle("met", done >= target); $("goal").classList.toggle("stretch", stretch && done < target);
  $("goal").title = stretch ? `Weekly goal of ${goal} reached ✓. Stretch target: ${target} (you chose +${target - goal})` : `Weekly goal: ${goal} notes approved`;
}
function renderList() {
  const L = $("list");
  if (mode === "journals") {
    L.innerHTML = S.journals.map(j => `<div class="item${cur && cur.rel === j.rel ? " on" : ""}${hasDraft(j.rel) ? " draft" : ""}" data-r="${esc(j.rel)}"><b>${esc(j.title)}</b><small>${j.open} open prompt${j.open > 1 ? "s" : ""}</small></div>`).join("")
      || '<div class="item"><small>No open prompts. Nice.</small></div>';
    return;
  }
  const f = filtered(), q = $("f-q").value.trim();
  // group by course and day; each group folds open/closed, so the list stays short
  const groups = [];
  for (const i of f) {
    const key = i.course + " · " + (i.rel.startsWith("Hubs/") ? "Hubs" : i.day);
    let g = groups.at(-1);
    if (!g || g.key !== key) { g = groups.find(x => x.key === key); if (!g) { g = {key, items: []}; groups.push(g); } }
    g.items.push(i);
  }
  if (cur) { const g = groups.find(g => g.items.some(i => i.rel === cur.rel)); if (g) openGroups.add(g.key); }
  if (!openGroups.size && groups[0]) openGroups.add(groups[0].key);
  const row = i => `<div class="item${cur && cur.rel === i.rel ? " on" : ""}${hasDraft(i.rel) ? " draft" : ""}" data-r="${esc(i.rel)}" title="${esc(i.title)}"><span class="ico t-${esc(i.type)}">${({case: "🏢", core: "💡", hub: "🔗", reference: "📖"})[i.type] || "📄"}</span><div class="itxt"><b>${esc(i.title)}</b></div>${i.status === "reviewed" ? '<span class="sdot ok" title="Approved"></span>' : i.status === "needs-fix" ? '<span class="sdot warn" title="Needs fix"></span>' : ""}</div>`;
  L.innerHTML = `<div class="listmeta">${f.length} note${f.length === 1 ? "" : "s"} · ${groups.length} group${groups.length === 1 ? "" : "s"}
      <span><button class="linkbtn" data-grp="open">expand all</button> · <button class="linkbtn" data-grp="close">collapse all</button></span></div>`
    + groups.map(g => { const open = q || openGroups.has(g.key);
      return `<div class="grp${open ? " open" : ""}"><button class="grphead" data-g="${esc(g.key)}"><span class="chev">▸</span><b>${esc(g.key)}</b><span class="cnt">${g.items.length}</span></button>
        ${open ? `<div class="grpbody">${typeGroups(g, row, q)}</div>` : ""}</div>`; }).join("");
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
function parkActions() { const A = $("actions"); if (A && A.classList.contains("inline")) { A.classList.remove("inline"); document.querySelector("main").after(A); } }
function show() {
  parkActions();
  const n = cur, p = n.props, V = $("view");
  const ST = {"reviewed": ["🏆 Approved", "ok"], "needs-fix": ["⚑ Needs fix", "warn"], "unreviewed": ["🚀 Ready for your review", "todo"]};
  const st = ST[p.status] || (p.status ? [p.status, "todo"] : null);
  const pill = st && mode !== "journals" ? `<div class="statuspill ${st[1]}">${st[0]}${p.status === "reviewed" && p.reviewed_on ? `<small>on ${esc(p.reviewed_on)}</small>` : ""}</div>` : "";
  const chips = pill + [p.course, p.type, n.rel.split("/")[1]].filter(Boolean).map(x => `<span class="chip">${esc(x)}</span>`).join("")
    + (p.fix_note ? `<span class="chip st-needs-fix">fix: ${esc(p.fix_note)}</span>` : "");
  if (mode === "journals") {
    const firstOpen = (n.prompts.find(q => !q.answer) || n.prompts[0] || {}).i;
    V.innerHTML = `<div class="jgrid"><div class="ctx" id="ctx"><p class="muted">Loading the day's material…</p></div><div class="doc qcol"><div class="meta">${chips}</div><h1>${esc(n.title)}</h1>
      <p class="muted small">${n.prompts.filter(q => q.answer).length} of ${n.prompts.length} answered · click a question to open it</p>` + n.prompts.map(q =>
      `<div class="prompt acc${q.i === (openQ ?? firstOpen) ? " active" : ""}" data-q="${q.i}">
         <div class="qhead" data-qh="${q.i}"><span class="qstate${q.answer ? " ok" : ""}" data-st="${q.i}">${q.answer ? "✓" : "○"}</span><p>${esc(q.question)}</p><span class="chev">▸</span></div>
         <div class="qbody">` + (q.answer
        ? `<div class="done md">${md(q.answer)}</div><div class="gap"><button class="b small" data-edit="${q.i}">Edit answer</button></div>
           <div class="editwrap" data-w="${q.i}" hidden><textarea data-i="${q.i}">${esc(q.answer)}</textarea><div class="gap"><button class="b ok" data-ans="${q.i}">Save answer</button></div></div>`
        : `<textarea data-i="${q.i}" placeholder="My answer, in my own words…"></textarea><div class="gap"><button class="b ok" data-ans="${q.i}">Save answer</button></div>`)
      + `</div></div>`).join("") + "</div></div>";
    loadContext(n.rel);
    V.querySelectorAll("textarea").forEach(ta => {
      keepDraft(ta, dkey("ans", n.rel, ta.dataset.i)); enhance(ta);
      const st = V.querySelector(`[data-st="${ta.dataset.i}"]`);
      const mark = () => { if (st && st.textContent !== "✓") st.textContent = ta.value.trim() ? "✎" : "○"; };
      ta.addEventListener("input", mark); mark();
    });
    openQ = null;
    $("actions").hidden = true; return;
  }
  const takes = n.takes || [];
  V.innerHTML = `<div class="doc"><div class="meta">${chips}${p.status === "reviewed" || p.status === "needs-fix" ? '<button class="b small" id="b-unrev" title="Set this note back to not reviewed">Mark not reviewed</button>' : ""}<b class="stitle">${esc(n.title)}</b></div>${md(n.body)}</div>
    ${takes.length ? `<div class="takes"><h3>✎ My takes on this note (${takes.length})</h3>` + takes.map(t => `
      <div class="tk" data-tk="${t.i}"><div class="tkhead"><b>${t.date ? esc(niceDay(t.date)) : "Earlier (undated)"}</b>
        <span><button class="b small" data-tkedit="${t.i}">Edit</button><button class="b small warn" data-tkdel="${t.i}">Delete</button></span></div>
        <div class="md tkview">${md(t.body)}</div>
        <div class="tkedit" hidden><textarea data-tkta="${t.i}">${esc(t.body)}</textarea>
          <div class="gap"><button class="b ok small" data-tksave="${t.i}">Save changes</button> <button class="b small" data-tkcancel="${t.i}">Cancel</button></div></div></div>`).join("") + "</div>" : ""}
    <div class="take"><label for="take">${takes.length ? "Add another take on" : "Your take on"}: <b class="takefor">${esc(n.title)}</b></label><textarea id="take" placeholder="In my own words / where I have seen this / what I would do with it…"></textarea>
    <div class="takebar"><span id="savestate" class="savestate"></span><span class="tiny savehint">Ctrl+Enter</span><button class="b ok savebtn" id="b-take" title="Save my take (Ctrl+Enter)"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 3h11l3 3v13a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2z"/><path d="M8 3v5h7V3M8 21v-6h8v6"/></svg><span>Save</span></button></div></div>`;
  if ($("b-unrev")) $("b-unrev").onclick = async () => { if (await act("/api/undo", {status: "unreviewed"}, "")) { show(); banner("↩ Back to not reviewed: " + cur.title, "info", false); } };
  $("actions").hidden = false;
  { const tk = V.querySelector(".take"); if (tk) { tk.appendChild($("actions")); $("actions").classList.add("inline"); } }   // buttons sit right under your take
  const o = $("b-obs"); if (n.obsidian) { o.href = n.obsidian; o.hidden = false; } else o.hidden = true;
  V.scrollTop = 0; stickyHead(); $("b-take").onclick = saveTake; enhance($("take"), {template: true});
  $("take").addEventListener("keydown", e => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); if ($("take").value.trim()) $("b-take").click(); } });
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
  parkActions();
  $("view").innerHTML = `<div class="doc"><p class="hello">${esc(greeting())} 👋</p><h1>My days</h1>
    <p class="weekline"><b>Last 7 days</b></p><div class="tiles weektiles"><span class="tile t-ok"><b>${wk.approve}</b>approved</span><span class="tile t-take"><b>${wk.take}</b>takes</span><span class="tile t-ref"><b>${wk.ans}</b>reflections</span><span class="tile"><b>${stats.week_streak || 0}🔥</b>week streak</span></div><div id="crewbox" class="crewbox"></div><p class="weekline"><b>Day by day</b></p>` +
    (days.map(d => weekHeader(d, days) + `<div class="daycard" data-day="${d.day}">
      <div class="dayhead"><b>${esc(niceDay(d.day))}</b>
        <span><div class="tiles"><span class="tile t-ok"><b>${d.approve}</b>approved</span><span class="tile t-take"><b>${d["my-take"]}</b>takes</span><span class="tile t-ref"><b>${d.answer}</b>reflections</span>${d["needs-fix"] ? `<span class="tile t-warn"><b>${d["needs-fix"]}</b>needs fix</span>` : ""}</div>${d.no_take && getSet().remind === "on" ? `<em class="notake">${d.no_take} approved without a take</em>` : ""}</span>
        <small>${Object.entries(d.types).map(([t, n]) => { const w = (TYPES[t] || t).toLowerCase(); return `${n} ${n === 1 && w !== "core" ? w.replace(/s$/, "") : w}`; }).join(" · ")}</small>
        <span class="chev">▸</span></div>
      <div class="daybody" hidden></div></div>`).join("") || '<p class="empty">Nothing yet. Approve a note or write a take, and your day shows up here.</p>') + "</div>";
  $("actions").hidden = true; if (window.fillCrew) fillCrew();
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
       <span class="tags">${[...new Set(n.actions.map(a => ACT[a.action] || a.action))].map(x => `<span class="chip">${esc(x)}</span>`).join("")}${noTakeChip(n)}</span><span class="chev">▸</span></div>
     <div class="dayitembody" hidden>${n.actions.map(a => `<div class="upd"><small>${esc(a.at)} · ${esc(ACT[a.action] || a.action)}</small>${a.detail ? `<div class="md">${md(a.detail)}</div>` : ""}</div>`).join("")}
       ${n.has_take || getSet().remind !== "on" ? "" : '<p class="notake">No take on this note yet. Open it to add one.</p>'}
       <button class="b small" data-open="${esc(n.rel)}" data-kind="${n.type === "theme" ? "journals" : "notes"}">${n.has_take || getSet().remind !== "on" ? "Open note" : "Open note to add a take"}</button></div></div>`).join("")).join("");
  body.dataset.loaded = "1";
}
let curIdx = 0, openQ = null;
const openGroups = new Set(), openTypes = new Set();
function next() {
  const f = mode === "journals" ? S.journals : filtered();
  const i = f.findIndex(x => cur && x.rel === cur.rel);
  // if the note just left this list (e.g. approved while viewing "To review"), the next one now sits at its old place
  const n = i >= 0 ? (f[i + 1] || f[0]) : (f[curIdx] || f[0]);
  if (n && (!cur || n.rel !== cur.rel)) return openNote(n.rel); toast("That was the last one");
}
let lastBtn = null, savedAt = {};
document.addEventListener("click", e => { const b = e.target.closest("button.b"); if (b) lastBtn = b; }, true);
function btnState(b, state) {                 // busy -> done / err, so every click shows it worked
  if (!b || !b.isConnected) return;
  const ic = b.classList.contains("iconb");
  if (state === "busy") { b.dataset.label = b.innerHTML; b.classList.add("busy"); b.disabled = true; b.textContent = ic ? "" : "Saving…"; return; }
  b.classList.remove("busy"); b.disabled = false;
  b.classList.add(state); if (ic) b.innerHTML = IC[state === "done" ? "check" : "x"]; else b.textContent = state === "done" ? "✓ Saved" : "✕ Not saved, try again";
  setTimeout(() => { if (!b.isConnected) return; b.classList.remove(state); if (b.dataset.label) b.innerHTML = b.dataset.label; if (cur && (b.id === "b-ok" || b.id === "b-okn")) labels(); }, 1500);
}
async function act(path, extra, msg) {
  const btn = lastBtn; lastBtn = null; btnState(btn, "busy");
  try { const rel = cur.rel; const r = await api(path, Object.assign({rel, mtime: cur.mtime}, extra || {})); cur = r.note; btnState(btn, "done"); if (window.rewardsTick) rewardsTick(path);
    savedAt[rel] = new Date().toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"});
    if (path === "/api/take") dset(dkey("take", rel), "");
    if (path === "/api/answer") dset(dkey("ans", rel, extra.i), ""); if (msg) toast(msg); await load(); return true; }
  catch (e) { btnState(btn, "err"); toast(e.message); return false; }
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
async function approve() {
  if (cur.props.status === "reviewed") return saveTake();     // already approved: just save the take
  await setStatus("/api/approve", null, "✓ Approved and saved: ", "ok");
}
async function approveNext() {
  const title = cur.title, draft = $("take") && $("take").value.trim();
  if (draft && !(await act("/api/take", {take: draft}, ""))) return;
  if (cur.props.status === "reviewed") {                      // already approved: save take (if any) and move on
    await next(); if (draft) banner("✓ Take saved: " + title + "  ·  now on the next note", "ok", false, false); return;
  }
  if (await act("/api/approve", null, "")) { await next(); banner("✓ Approved" + (draft ? " and take saved" : "") + ": " + title + "  ·  now on the next note", "ok", false, false); }
}
const IC = {"check": "<svg viewBox=\"0 0 24 24\" width=\"18\" height=\"18\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M4.5 12.5l5 5 10-11\"/></svg>", "checknext": "<svg viewBox=\"0 0 24 24\" width=\"18\" height=\"18\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M2.5 12.5l4 4 7-8\"/><path d=\"M14.5 12h7M18 8.5l3.5 3.5-3.5 3.5\"/></svg>", "next": "<svg viewBox=\"0 0 24 24\" width=\"18\" height=\"18\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M4 12h15M13 6l6 6-6 6\"/></svg>", "save": "<svg viewBox=\"0 0 24 24\" width=\"18\" height=\"18\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M5 3h11l3 3v13a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2z\"/><path d=\"M8 3v5h7V3M8 21v-6h8v6\"/></svg>", "savenext": "<svg viewBox=\"0 0 24 24\" width=\"18\" height=\"18\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M3 4h8l2 2v9H3z\"/><path d=\"M5.5 4v3h4.5V4\"/><path d=\"M15 12h6.5M18 8.5l3.5 3.5-3.5 3.5\"/></svg>", "flag": "<svg viewBox=\"0 0 24 24\" width=\"18\" height=\"18\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M5 21V4\"/><path d=\"M5 4h11l-2.5 4L16 12H5\"/></svg>", "skip": "<svg viewBox=\"0 0 24 24\" width=\"18\" height=\"18\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M5 5.5l9 6.5-9 6.5z\"/><path d=\"M18.5 5v14\"/></svg>", "open": "<svg viewBox=\"0 0 24 24\" width=\"18\" height=\"18\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M14 4h6v6M20 4l-9 9\"/><path d=\"M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5\"/></svg>", "x": "<svg viewBox=\"0 0 24 24\" width=\"18\" height=\"18\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.2\" stroke-linecap=\"round\" stroke-linejoin=\"round\" aria-hidden=\"true\"><path d=\"M6 6l12 12M18 6L6 18\"/></svg>"};
function setBtn(id, icon, tip) { const b = $(id); if (!b) return; b.innerHTML = IC[icon]; b.title = tip; b.setAttribute("aria-label", tip); b.classList.add("iconb"); }
function labels() {
  const has = $("take") && $("take").value.trim(), done = cur && cur.props.status === "reviewed";
  if ($("b-ok").classList.contains("busy")) return;
  if (done) {                                   // already approved: only saving takes from now on
    setBtn("b-okn", has ? "savenext" : "next", has ? "Save take & go to next note (Shift+A)" : "Next note (Shift+A)");
    setBtn("b-ok", has ? "save" : "check", has ? "Save take (A)" : "Approved ✓"); $("b-ok").disabled = !has;
  } else {
    setBtn("b-okn", "checknext", has ? "Save take, approve & go to next note (Shift+A)" : "Approve & go to next note (Shift+A)");
    setBtn("b-ok", "check", has ? "Save take & approve (A)" : "Approve (A)"); $("b-ok").disabled = false;
  }
  setBtn("b-fix", "flag", "Needs fix (F)"); setBtn("b-skip", "skip", "Skip to next note (→)"); setBtn("b-obs", "open", "Open in Obsidian");
  $("b-ok").classList.toggle("isdone", !!done && !has);
  const ss = $("savestate"); if (ss) {
    ss.className = "savestate " + (has ? "pending" : savedAt[cur.rel] ? "saved" : "");
    ss.textContent = has ? "● Draft (kept safe) · not saved to your note yet" : savedAt[cur.rel] ? `✓ Saved to your note at ${savedAt[cur.rel]}` : "";
  }
  if ($("b-take")) $("b-take").disabled = !has;
}
async function fix() { const why = prompt("What needs fixing?"); if (why === null) return; await setStatus("/api/needs-fix", {why}, "⚑ Marked for fixing: ", "warn"); }
async function undoLast() { if (!undoStatus) return; const s = undoStatus; if (await act("/api/undo", {status: s}, "")) { show(); banner("↩ Undone. Back to " + ({"unreviewed": "not reviewed yet", "reviewed": "approved", "needs-fix": "needs fix"}[s] || s) + ": " + cur.title, "info", false); } }
async function saveTake() { const t = $("take").value.trim(); if (!t) return; if (await act("/api/take", {take: t}, "")) { show(); banner("✓ Take saved: " + cur.title, "ok", false); } }
function setMode(m) {
  mode = m; cur = null;
  for (const t of ["notes", "journals", "activity"]) $("t-" + t).classList.toggle("on", t === m);
  $("leftcol").hidden = m === "activity"; document.querySelector("main").classList.toggle("noside", m === "activity"); $("actions").hidden = true;
  document.querySelector(".filters").hidden = $("f-q").hidden = m !== "notes";
  if (m === "activity") return showActivity();
  parkActions();
  $("view").innerHTML = `<div class="empty"><div class="hello">${esc(greeting())} 👋</div>${m === "journals" ? "Pick a journal on the left to reflect on." : "Pick a note on the left to start reviewing."}</div>`;
  renderList();
}
document.addEventListener("click", async e => {
  const th = e.target.closest("[data-t]");
  if (th) { const k = th.dataset.t; openTypes.has(k) ? openTypes.delete(k) : openTypes.add(k); return renderList(); }
  const gh = e.target.closest("[data-g]");
  if (gh) { const k = gh.dataset.g; openGroups.has(k) ? openGroups.delete(k) : openGroups.add(k); return renderList(); }
  const ga = e.target.closest("[data-grp]");
  if (ga) { if (ga.dataset.grp === "open") document.querySelectorAll("[data-g]").forEach(b => openGroups.add(b.dataset.g)); else { openGroups.clear(); openTypes.clear(); } return renderList(); }
  const op = e.target.closest("[data-open]");
  if (op) { setMode(op.dataset.kind); return openNote(op.dataset.open); }
  const ih = e.target.closest(".dayitemhead");
  if (ih) { const b = ih.nextElementSibling; b.hidden = !b.hidden; ih.parentElement.classList.toggle("open", !b.hidden); return; }
  const dh = e.target.closest(".dayhead"); if (dh) return openDay(dh.parentElement);
  const it = e.target.closest(".item[data-r]"); if (it) return openNote(it.dataset.r);
  const wl = e.target.closest("a.wl");
  if (wl) { e.preventDefault(); const r = await api("/api/find?title=" + encodeURIComponent(wl.dataset.t)); r.rel ? openNote(r.rel) : toast(`No note called “${wl.dataset.t}” yet`); return; }
  const te = e.target.closest("[data-tkedit]");
  if (te) { const box = te.closest(".tk"); box.querySelector(".tkview").hidden = true; box.querySelector(".tkedit").hidden = false;
    const ta = box.querySelector("textarea"); enhance(ta); ta.dispatchEvent(new Event("input")); ta.focus(); te.parentElement.hidden = true; return; }
  const tc = e.target.closest("[data-tkcancel]");
  if (tc) { show(); return; }
  const ts = e.target.closest("[data-tksave]");
  if (ts) { const i = +ts.dataset.tksave, body = document.querySelector(`[data-tkta="${i}"]`).value;
    if (!body.trim()) return toast("Empty: use Delete to remove a take");
    if (await act("/api/take-edit", {i, body}, "")) { show(); banner("✓ Take updated: " + cur.title, "ok", false); } return; }
  const td = e.target.closest("[data-tkdel]");
  if (td) { if (!confirmDelete(td)) return;
    if (await act("/api/take-edit", {i: +td.dataset.tkdel, body: ""}, "")) { show(); banner("🗑 Take deleted from: " + cur.title, "info", false); } return; }
  const qh = e.target.closest("[data-qh]");
  if (qh) { const box = qh.parentElement, was = box.classList.contains("active");
    document.querySelectorAll(".prompt.acc").forEach(p => p.classList.remove("active"));
    if (!was) { box.classList.add("active"); const ta = box.querySelector("textarea:not([hidden])"); if (ta) { ta.dispatchEvent(new Event("input")); ta.focus(); } box.scrollIntoView({block: "start", behavior: "smooth"}); }
    return; }
  const ed = e.target.closest("[data-edit]");
  if (ed) { const w = document.querySelector(`[data-w="${ed.dataset.edit}"]`); w.hidden = false; ed.hidden = true; w.querySelector("textarea").dispatchEvent(new Event("input")); return; }
  const a = e.target.closest("[data-ans]");
  if (a) { const ta = document.querySelector(`textarea[data-i="${a.dataset.ans}"]`); if (!ta.value.trim()) return;
    if (await act("/api/answer", {i: +a.dataset.ans, answer: ta.value}, "Answer saved")) { const nx = cur.prompts.find(q => !q.answer); openQ = nx ? nx.i : +a.dataset.ans; show(); } }
});
function setSide(collapsed) {
  if (!$("main") || !$("b-expand")) return;          // older page layout: nothing to fold
  $("main").classList.toggle("collapsed", collapsed); $("b-expand").hidden = !collapsed;
  try { localStorage.setItem("mytutor-side", collapsed ? "1" : "0"); } catch (e) {}
}
if ($("b-collapse")) $("b-collapse").onclick = () => setSide(true);
if ($("b-expand")) $("b-expand").onclick = () => setSide(false);
try { if (localStorage.getItem("mytutor-side") === "1") setSide(true); } catch (e) {}
document.addEventListener("keydown", e => { if (e.key === "[" && !/TEXTAREA|INPUT|SELECT/.test(e.target.tagName)) setSide(!$("main").classList.contains("collapsed")); });
function isDark() { const t = getSet().theme; return t === "dark" || (t === "auto" && matchMedia("(prefers-color-scheme: dark)").matches); }
const ICON_SUN = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6"/></svg>', ICON_MOON = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5 8.5 8.5 0 1 0 20.5 14.2z"/></svg>';
function themeIcon() { if ($("b-theme")) { $("b-theme").innerHTML = isDark() ? ICON_SUN : ICON_MOON; $("b-theme").title = isDark() ? "Switch to light" : "Switch to dark"; } }
if ($("b-theme")) $("b-theme").onclick = () => { saveSet("theme", isDark() ? "light" : "dark"); themeIcon(); };
themeIcon();
$("b-ok").onclick = approve; $("b-fix").onclick = fix; $("b-skip").onclick = next;
$("b-set").onclick = e => { e.stopPropagation(); $("settings").hidden = !$("settings").hidden; applySet(getSet()); };
document.querySelectorAll(".seg[data-set] button").forEach(b => b.onclick = () => saveSet(b.parentElement.dataset.set, b.dataset.v));
$("s-name").value = getSet().name; $("s-name").oninput = e => saveSet("name", e.target.value);
$("b-user").onclick = e => { e.stopPropagation(); $("umenu").hidden = !$("umenu").hidden; };
document.addEventListener("click", e => { if (!e.target.closest(".usermenu")) $("umenu").hidden = true; });
document.addEventListener("click", e => { if (!e.target.closest("#settings,#b-set")) $("settings").hidden = true; });
async function loadPhoto() {
  try {
    const r = await fetch("/api/background", {method: "HEAD", credentials: "same-origin", cache: "no-store"});
    const el = $("bgphoto");
    if (!r.ok) { el.hidden = true; document.body.classList.remove("hasphoto"); return; }
    el.style.backgroundImage = `url("/api/background?v=${Date.now()}")`; el.hidden = false; document.body.classList.add("hasphoto");
  } catch (e) {}
}
$("bg-file").onchange = async e => {
  const f = e.target.files[0]; if (!f) return;
  const fd = new FormData(); fd.append("photo", f);
  const r = await fetch("/api/background", {method: "POST", credentials: "same-origin", headers: {"X-CSRF": CSRF}, body: fd});
  const j = await r.json().catch(() => ({})); toast(r.ok ? "Photo set" : (j.error || "Could not use that photo")); e.target.value = ""; loadPhoto();
};
$("bg-remove").onclick = async () => { await api("/api/background/remove", {}); loadPhoto(); toast("Photo removed"); };
loadPhoto();
async function loadAvatar() {
  try {
    const r = await fetch("/api/avatar", {method: "HEAD", credentials: "same-origin", cache: "no-store"});
    const b = $("b-user"); if (!b) return;
    if (r.ok) { b.style.backgroundImage = `url("/api/avatar?v=${Date.now()}")`; b.classList.add("hasimg"); }
    else { b.style.backgroundImage = ""; b.classList.remove("hasimg"); }
  } catch (e) {}
}
if ($("av-file")) $("av-file").onchange = async e => {
  const f = e.target.files[0]; if (!f) return;
  const fd = new FormData(); fd.append("photo", f);
  const r = await fetch("/api/avatar", {method: "POST", credentials: "same-origin", headers: {"X-CSRF": CSRF}, body: fd});
  const j = await r.json().catch(() => ({})); toast(r.ok ? "Profile photo set" : (j.error || "Could not use that photo")); e.target.value = ""; loadAvatar();
};
if ($("av-remove")) $("av-remove").onclick = async () => { await api("/api/avatar/remove", {}); loadAvatar(); toast("Profile photo removed"); };
loadAvatar();
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
window.addEventListener("focus", () => { load().then(() => { if (mode === "activity") showActivity(); }).catch(() => {}); });
window.addEventListener("hashchange", () => { if (location.hash === "#days") setMode("activity"); });
load().then(() => { if (location.hash === "#days") return setMode("activity"); const f = filtered(); if (f.length) openNote(f[0].rel); }).catch(e => toast(e.message));

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
    tp.title = "Insert my headings: source, experience, apply, takeaway, memory line"; tp.onclick = () => { insertTemplate(ta); ta.focus(); grow(); }; bar.appendChild(tp);
  }
  const prev = document.createElement("button"); prev.type = "button"; prev.textContent = "Preview"; prev.className = "pvbtn";
  prev.onclick = () => { const on = pv.hidden; pv.hidden = !on; ta.hidden = on; prev.textContent = on ? "Edit" : "Preview";
    if (on) pv.innerHTML = md(ta.value || "*Nothing yet.*"); else ta.focus(); };
  bar.appendChild(prev);
  ta.before(bar); ta.after(pv);
  const grow = () => { ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight + 4, window.innerHeight * 0.7) + "px"; };
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
  const t = `#### 📖 Where I came across this\n${src}\n\n#### 💭 My experience and observation\n\n\n#### 🎯 What I would apply in the future\n- \n\n#### 💡 Key takeaway: what I would tell the C-suite or the board\n\n\n#### 🧠 Memory line: one line to remember\n`;
  const pos = ta.selectionStart, before = ta.value.slice(0, pos);
  const sep = before && !before.endsWith("\n\n") ? (before.endsWith("\n") ? "\n" : "\n\n") : "";
  ta.setRangeText(sep + t, pos, ta.selectionEnd, "end");
  const at = ta.value.indexOf("#### 💭 My experience and observation\n", pos) + "#### 💭 My experience and observation\n".length;
  ta.setSelectionRange(at, at);                                    // cursor ready under "My experience"
  ta.dispatchEvent(new Event("input"));
}

async function loadContext(rel) {
  let c; try { c = await api("/api/context?rel=" + encodeURIComponent(rel)); } catch (e) { $("ctx").innerHTML = `<p class="muted">${esc(e.message)}</p>`; return; }
  if (!cur || cur.rel !== rel) return;
  const card = (n, open) => n.rel
    ? `<details class="cc"${open ? " open" : ""}><summary>${esc(n.title)}</summary><div class="md">${md(n.body.replace(/^#\s.*\n/, ""))}</div>
        <button class="b small" data-open="${esc(n.rel)}" data-kind="notes">Open note</button></details>`
    : `<div class="cc missing">${esc(n.title)} <small>(note not found)</small></div>`;
  const sec = (icon, title, items, open) => items && items.length ? `<h3>${icon} ${title}</h3>` + items.map(i => card(i, open)).join("") : "";
  $("ctx").innerHTML = `<div class="ctxhead">The day's material</div>`
    + sec("📖", "The brief", c.reference, true)
    + sec("💡", `Core concepts (${(c.core || []).length})`, c.core, false)
    + sec("🏢", "Cases", c.cases, false)
    + (c.phrases && c.phrases.length ? `<h3>🔤 Boardroom English</h3><ul class="phr">` + c.phrases.map(p => `<li><b>${esc(p.phrase)}</b> ${esc(p.meaning)}</li>`).join("") + "</ul>" : "")
    || '<p class="muted">No linked material for this day.</p>';
}

function confirmDelete(btn) {                 // two-step delete without a browser dialog: click again to confirm
  if (btn.dataset.armed) return true;
  btn.dataset.armed = "1"; const old = btn.textContent; btn.textContent = "Click again to delete";
  setTimeout(() => { delete btn.dataset.armed; btn.textContent = old; }, 3000);
  return false;
}

function noTakeChip(n) {
  // approved without a take: a deliberate choice unless reminders are switched on
  if (n.has_take || !n.actions.some(a => a.action === "approve")) return "";
  return getSet().remind === "on" ? '<span class="chip notake">no take yet</span>' : '<span class="chip nt-ok">no take needed</span>';
}

function weekMonday(iso) { const d = new Date(iso + "T12:00:00"); d.setDate(d.getDate() - ((d.getDay() + 6) % 7)); return d; }
function weekHeader(d, days) {
  // a heading before the first day of each week, with that week's totals
  const key = weekMonday(d.day).toDateString(), i = days.indexOf(d);
  if (i > 0 && weekMonday(days[i - 1].day).toDateString() === key) return "";
  const wk = days.filter(x => weekMonday(x.day).toDateString() === key);
  const sum = k => wk.reduce((a, x) => a + (x[k] || 0), 0);
  const m = weekMonday(d.day), sun = new Date(m); sun.setDate(m.getDate() + 6);
  const f = o => o.toLocaleDateString(undefined, {day: "numeric", month: "short"});
  const now = weekMonday(new Date().toISOString().slice(0, 10)).toDateString() === key;
  return `<div class="weekhead"><b>${now ? "This week" : "Week"} · ${esc(f(m))} – ${esc(f(sun))}</b>
    <span>${sum("approve")} approved · ${sum("my-take")} takes · ${sum("answer")} reflections · ${wk.length} active day${wk.length === 1 ? "" : "s"}</span></div>`;
}

// inside a day: fold by kind (sources, cases, concepts, hubs), so a 66-note day shows 3–4 short lines
const KINDS = [["reference", "📖", "Sources"], ["case", "🏢", "Cases"], ["core", "💡", "Concepts"], ["hub", "🔗", "Hubs"]];
function typeGroups(g, row, q) {
  return KINDS.map(([k, ico, label]) => {
    const items = g.items.filter(i => i.type === k); if (!items.length) return "";
    const key = g.key + "|" + k, has = cur && items.some(i => i.rel === cur.rel);
    if (has) openTypes.add(key);
    const open = q || openTypes.has(key) || items.length <= 3;
    const done = items.filter(i => i.status === "reviewed").length;
    return `<div class="tgrp${open ? " open" : ""}"><button class="tgrphead" data-t="${esc(key)}"><span class="chev">▸</span>${ico} ${label}<span class="cnt">${done ? done + "/" : ""}${items.length}</span></button>
      ${open ? items.map(row).join("") : ""}</div>`;
  }).join("");
}

/* ---- Today card: time, weather, this week, a memory line (each optional in Personalise) ---- */
const WX = {0: ["☀️", "Clear"], 1: ["🌤️", "Mostly clear"], 2: ["⛅", "Partly cloudy"], 3: ["☁️", "Cloudy"], 45: ["🌫️", "Fog"], 48: ["🌫️", "Fog"],
  51: ["🌦️", "Light drizzle"], 53: ["🌦️", "Drizzle"], 55: ["🌧️", "Heavy drizzle"], 61: ["🌦️", "Light rain"], 63: ["🌧️", "Rain"], 65: ["🌧️", "Heavy rain"],
  71: ["🌨️", "Light snow"], 73: ["🌨️", "Snow"], 75: ["❄️", "Heavy snow"], 80: ["🌦️", "Showers"], 81: ["🌧️", "Showers"], 82: ["⛈️", "Heavy showers"],
  95: ["⛈️", "Thunderstorm"], 96: ["⛈️", "Thunderstorm"], 99: ["⛈️", "Thunderstorm"]};
try { if (!localStorage.getItem("mytutor-today-v3")) { const t1 = new Set((getSet().today || "").split(",").filter(Boolean)); t1.delete("week"); saveSet("today", [...t1].join(",")); localStorage.setItem("mytutor-today-v3", "1"); } } catch (e) {}   // the weekly bar lives in the header ring
try { if (!localStorage.getItem("mytutor-today-v2")) { const t0 = new Set((getSet().today || "").split(",").filter(Boolean)); t0.add("rank"); t0.add("quote"); saveSet("today", [...t0].join(",")); localStorage.setItem("mytutor-today-v2", "1"); } } catch (e) {}
function todayOn() { return new Set((getSet().today || "").split(",").filter(Boolean)); }
function renderToday() {
  const on = todayOn(), card = $("today"); if (!card) return;
  card.hidden = on.size === 0;
  for (const k of ["clock", "wx", "rank", "week", "quote", "crew", "mem"]) $("td-" + k).hidden = !on.has(k);
  if (on.has("rank") && window.fillRank) fillRank();
  if (on.has("quote") && window.showQuote && !$("td-qtext").textContent) showQuote(0);
  if (on.has("crew") && window.fillCrewRow) fillCrewRow();
  document.querySelectorAll("#s-today button").forEach(b => b.classList.toggle("on", on.has(b.dataset.k)));
  if (on.has("clock")) tick();
  if (on.has("week")) renderWeek();
  if (on.has("wx")) loadWeather();
  if (on.has("mem") && !$("td-memline").dataset.done) loadMemLine();
}
function tick() {
  const d = new Date();
  $("td-time").textContent = d.toLocaleTimeString([], {hour: "numeric", minute: "2-digit"});
  $("td-date").textContent = d.toLocaleDateString([], {weekday: "short", day: "numeric", month: "short"});
}
function renderWeek() {
  const st = (S && S.stats) || {}, goal = weeklyGoal(), done = st.approved_week ?? 0;
  $("td-bar").style.width = Math.min(100, Math.round(done / goal * 100)) + "%";
  $("td-weektxt").innerHTML = `<span>${done >= goal ? "🎉 " + done + " / " + goal + " · goal reached" : done + " / " + goal + " approved this week"}</span><span>🔥 ${st.week_streak || 0} wk</span>`;
}
function cacheGet(k) { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (e) { return null; } }
function cacheSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
let wxBusy = false;
async function loadWeather() {
  const city = (getSet().city || "Christchurch").trim(), c = cacheGet("mytutor-wx");
  if (c && c.city === city && Date.now() - c.at < 30 * 60e3) return showWeather(c);
  if (wxBusy) return; wxBusy = true;
  try {
    let g = cacheGet("mytutor-geo");
    if (!g || g.city !== city) {
      const r = await (await fetch("https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + encodeURIComponent(city))).json();
      const p = (r.results || [])[0]; if (!p) throw new Error("City not found");
      g = {city, lat: p.latitude, lon: p.longitude, name: p.name}; cacheSet("mytutor-geo", g);
    }
    const w = await (await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${g.lat}&longitude=${g.lon}&current=temperature_2m,weather_code&daily=temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=1`)).json();
    const v = {city, name: g.name, at: Date.now(), t: Math.round(w.current.temperature_2m), code: w.current.weather_code,
               hi: Math.round(w.daily.temperature_2m_max[0]), lo: Math.round(w.daily.temperature_2m_min[0])};
    cacheSet("mytutor-wx", v); showWeather(v);
  } catch (e) { $("td-wxico").textContent = "🌐"; $("td-temp").textContent = "Weather unavailable"; $("td-wxtxt").textContent = e.message === "City not found" ? `Could not find "${city}"` : "Offline? Will try again later"; }
  finally { wxBusy = false; }
}
function showWeather(v) {
  const [ico, txt] = WX[v.code] || ["🌡️", ""];
  $("td-wxico").textContent = ico; $("td-temp").textContent = `${v.t}°C ${txt}`; $("td-wxtxt").textContent = `${v.name} · H ${v.hi}° L ${v.lo}°`;
}
async function loadMemLine() {
  const el = $("td-memline"), src = $("td-memsrc");
  try {
    const r = await api("/api/memory-line"); el.dataset.done = "1";
    if (!r.line) { el.textContent = "No memory lines yet. Use the Template button in your take and fill in 🧠 Memory line."; el.classList.add("empty"); src.hidden = true; $("td-memnext").hidden = true; return; }
    el.classList.remove("empty"); el.textContent = r.line; src.hidden = false; src.textContent = "from " + r.title; src.dataset.rel = r.rel;
    $("td-memnext").hidden = false; $("td-memnext").title = r.count > 1 ? `Another one (${r.count} memory lines)` : "Refresh";
  } catch (e) {}
}
if ($("today")) {
  $("td-memnext").onclick = () => loadMemLine();
  $("td-memsrc").onclick = e => { e.preventDefault(); if (e.target.dataset.rel) { if (mode !== "notes") setMode("notes"); openNote(e.target.dataset.rel); } };
  document.querySelectorAll("#s-today button").forEach(b => b.onclick = () => {
    const on = todayOn(); on.has(b.dataset.k) ? on.delete(b.dataset.k) : on.add(b.dataset.k); saveSet("today", [...on].join(",")); renderToday(); });
  $("s-city").value = getSet().city;
  $("s-city").onchange = e => { saveSet("city", e.target.value.trim() || "Christchurch"); loadWeather(); };
  setInterval(() => { if (todayOn().has("clock")) tick(); }, 15e3);
  setInterval(() => { if (todayOn().has("wx")) loadWeather(); }, 30 * 60e3);
  setInterval(() => { if (todayOn().has("mem")) loadMemLine(); }, 5 * 60e3);        // a new memory line every 5 minutes
  renderToday();
}

/* keep status + title visible while scrolling a note */
function stickyHead() {
  const V = $("view"), m = V.querySelector(".doc > .meta"); if (!m) return;
  V.onscroll = () => m.classList.toggle("stuck", V.scrollTop > 70); V.onscroll();
}

/* weekly goal: stored on the laptop (jobs/prefs.json) so the Control Centre shows the same number */
function weeklyTarget() { return weeklyGoal() + (+(S && S.weekly_extra) || 0); }   // goal + any stretch you said yes to this week
function weeklyGoal() { return +(S && S.weekly_goal) || 25; }
if ($("s-wgoal")) {
  const g = $("s-wgoal"); g.value = weeklyGoal();
  $("b-set").addEventListener("click", () => { g.value = weeklyGoal(); });
  g.onchange = async () => {
    const n = Math.round(+g.value);
    try { const r = await api("/api/prefs", {weekly_goal: n}); S.weekly_goal = r.weekly_goal; g.value = r.weekly_goal; renderProg(); toast(`✓ Weekly goal set to ${r.weekly_goal}`); }
    catch (e) { toast(e.message); g.value = weeklyGoal(); }
  };
}
