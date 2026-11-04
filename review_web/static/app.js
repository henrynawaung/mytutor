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
    L.innerHTML = S.journals.map(j => `<div class="item${cur && cur.rel === j.rel ? " on" : ""}" data-r="${esc(j.rel)}"><b>${esc(j.title)}</b><small>${j.open} open prompt${j.open > 1 ? "s" : ""}</small></div>`).join("")
      || '<div class="item"><small>No open prompts. Nice.</small></div>';
    return;
  }
  const f = filtered();
  L.innerHTML = `<div class="item"><small>${f.length} note${f.length === 1 ? "" : "s"}</small></div>` + f.slice(0, 500).map(i =>
    `<div class="item${cur && cur.rel === i.rel ? " on" : ""}" data-r="${esc(i.rel)}"><b>${esc(i.title)}</b><small>${esc(i.course)} · ${esc(i.day)} · ${esc(i.type)}</small></div>`).join("");
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
    cur = await api("/api/note?rel=" + encodeURIComponent(rel)); renderList(); show();
  } catch (e) { toast(e.message); }
}
function show() {
  const n = cur, p = n.props, V = $("view");
  const chips = [p.course, p.type, n.rel.split("/")[1], p.status].filter(Boolean).map(x => `<span class="chip st-${esc(x)}">${esc(x)}</span>`).join("")
    + (p.reviewed_on ? `<span class="chip">reviewed ${esc(p.reviewed_on)}</span>` : "")
    + (p.fix_note ? `<span class="chip st-needs-fix">fix: ${esc(p.fix_note)}</span>` : "");
  if (mode === "journals") {
    V.innerHTML = `<div class="doc"><div class="meta">${chips}</div><h1>${esc(n.title)}</h1>` + n.prompts.map(q =>
      `<div class="prompt"><p>${esc(q.question)}</p>${q.answer ? `<div class="done">✓ ${esc(q.answer)}</div>` :
      `<textarea data-i="${q.i}" placeholder="My answer, in my own words…"></textarea><div class="gap"><button class="b ok" data-ans="${q.i}">Save answer</button></div>`}</div>`).join("") + "</div>";
    $("actions").hidden = true; return;
  }
  V.innerHTML = `<div class="doc"><div class="meta">${chips}</div>${md(n.body)}</div>
    <div class="take"><label for="take">My take (saved into the note, dated)</label><textarea id="take" placeholder="In my own words / where I have seen this / what I would do with it…"></textarea>
    <div class="gap"><button class="b" id="b-take">Save my take</button></div></div>`;
  $("actions").hidden = false;
  const o = $("b-obs"); if (n.obsidian) { o.href = n.obsidian; o.hidden = false; } else o.hidden = true;
  V.scrollTop = 0; $("b-take").onclick = saveTake;
}
async function showActivity() {
  const rows = await api("/api/recent");
  $("view").innerHTML = `<div class="doc"><h1>Activity</h1><table class="act">` + (rows.map(r =>
    `<tr><td>${esc(r.at.replace("T", " "))}</td><td>${esc(r.action)}</td><td>${esc((r.rel || "").split("/").pop().replace(/\.md$/, ""))}${r.detail ? "<br><small>" + esc(r.detail) + "</small>" : ""}</td></tr>`).join("")
    || "<tr><td>No activity yet.</td></tr>") + "</table></div>";
  $("actions").hidden = true;
}
function next() {
  const f = mode === "journals" ? S.journals : filtered();
  const i = f.findIndex(x => cur && x.rel === cur.rel);
  const n = f[i + 1] || f[0];
  if (n && (!cur || n.rel !== cur.rel)) openNote(n.rel); else toast("That was the last one");
}
async function act(path, extra, msg) {
  try { const r = await api(path, Object.assign({rel: cur.rel, mtime: cur.mtime}, extra || {})); cur = r.note; toast(msg); await load(); return true; }
  catch (e) { toast(e.message); return false; }
}
async function approve() { if (await act("/api/approve", null, "Approved ✓")) next(); }
async function fix() { const why = prompt("What needs fixing?"); if (why === null) return; if (await act("/api/needs-fix", {why}, "Marked: needs fix")) next(); }
async function saveTake() { const t = $("take").value.trim(); if (!t) return; if (await act("/api/take", {take: t}, "Saved to the note")) show(); }
function setMode(m) {
  mode = m; cur = null;
  for (const t of ["notes", "journals", "activity"]) $("t-" + t).classList.toggle("on", t === m);
  $("side").hidden = m === "activity"; $("actions").hidden = true;
  document.querySelector(".filters").hidden = $("f-q").hidden = m !== "notes";
  if (m === "activity") return showActivity();
  $("view").innerHTML = `<div class="empty">${m === "journals" ? "Pick a journal with open prompts." : "Pick a note on the left."}</div>`;
  renderList();
}
document.addEventListener("click", async e => {
  const it = e.target.closest(".item[data-r]"); if (it) return openNote(it.dataset.r);
  const wl = e.target.closest("a.wl");
  if (wl) { e.preventDefault(); const r = await api("/api/find?title=" + encodeURIComponent(wl.dataset.t)); r.rel ? openNote(r.rel) : toast(`No note called “${wl.dataset.t}” yet`); return; }
  const a = e.target.closest("[data-ans]");
  if (a) { const ta = document.querySelector(`textarea[data-i="${a.dataset.ans}"]`); if (!ta.value.trim()) return;
    if (await act("/api/answer", {i: +a.dataset.ans, answer: ta.value}, "Answer saved")) show(); }
});
$("b-ok").onclick = approve; $("b-fix").onclick = fix; $("b-skip").onclick = next;
$("b-sync").onclick = async () => { try { const r = await api("/api/sync", {}); await load(); toast(`Refreshed: ${r.changed} change${r.changed === 1 ? "" : "s"}`); } catch (e) { toast(e.message); } };
["f-course", "f-status", "f-type"].forEach(id => $(id).onchange = renderList);
$("f-q").oninput = renderList;
$("t-notes").onclick = () => setMode("notes"); $("t-journals").onclick = () => setMode("journals"); $("t-activity").onclick = () => setMode("activity");
document.addEventListener("keydown", e => {
  if (/TEXTAREA|INPUT|SELECT/.test(e.target.tagName) || !cur || mode !== "notes") return;
  const k = e.key.toLowerCase();
  if (k === "a") approve(); else if (k === "f") fix(); else if (k === "s" || k === "arrowright") next();
  else if (k === "arrowleft" && hist.length) openNote(hist.pop(), false);
  else if (k === "t") { e.preventDefault(); $("take").focus(); }
});
load().then(() => { const f = filtered(); if (f.length) openNote(f[0].rel); }).catch(e => toast(e.message));
