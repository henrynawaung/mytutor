/* myTutor rewards: "My crew" characters, milestone badges, save chimes and celebration pop-ups.
   Everything is derived from /api/rewards counts; only "which unlocks I have already celebrated" lives in localStorage. */
"use strict";

/* ---------- the crew (original characters, drawn here as SVG) ---------- */
const CREW = [
  {id: "sprout", name: "Sprout", role: "The Grower", stat: "approved", unit: "notes approved", lv: [10, 50, 150]},
  {id: "fox", name: "Fox", role: "The Strategist", stat: "takes", unit: "takes written", lv: [5, 25, 75]},
  {id: "turtle", name: "Turtle", role: "Steady", stat: "best_streak", unit: "week streak", lv: [2, 4, 8]},
  {id: "bee", name: "Bee", role: "The Connector", stat: "reflections", unit: "reflections answered", lv: [5, 20, 50]},
  {id: "lion", name: "Lion", role: "Board-ready", stat: "memory_lines", unit: "memory lines", lv: [5, 15, 40]},
  {id: "dragon", name: "Dragon", role: "Course Master", stat: "courses", unit: "courses fully approved", lv: [1, 2, 3], secret: true},
];
const BADGES = [
  {stat: "approved", icon: "📘", unit: "notes reviewed", at: [20, 50, 100, 200, 300, 500, 750, 1000]},
  {stat: "takes", icon: "✍️", unit: "takes written", at: [10, 25, 50, 100, 200]},
  {stat: "reflections", icon: "💬", unit: "reflections", at: [10, 25, 50, 100]},
  {stat: "best_streak", icon: "🔥", unit: "week streak", at: [4, 8, 12, 26, 52]},
  {stat: "memory_lines", icon: "🧠", unit: "memory lines", at: [10, 25, 50]},
];
const TIER = ["bronze", "silver", "gold", "platinum"];

const eye = (x, y) => `<circle cx="${x}" cy="${y}" r="4.2" fill="#1d1d2b"/><circle cx="${x + 1.4}" cy="${y - 1.5}" r="1.4" fill="#fff"/>`;
const blush = (x, y) => `<ellipse cx="${x}" cy="${y}" rx="4.5" ry="2.6" fill="#ff8fa3" opacity=".55"/>`;
const smile = (x, y) => `<path d="M${x - 5} ${y} q5 5 10 0" stroke="#1d1d2b" stroke-width="2.4" fill="none" stroke-linecap="round"/>`;
const ART = {
  sprout: L => `<path d="M30 70h40l-5 22H35z" fill="#c8794a"/><rect x="27" y="64" width="46" height="9" rx="4" fill="#e08e57"/>
    <path d="M50 66V${L >= 3 ? 30 : 40}" stroke="#3aa35b" stroke-width="5" stroke-linecap="round"/>
    <path d="M50 52c-14 2-20-6-22-14 12-2 20 3 22 14z" fill="#5cc97a"/><path d="M50 46c13 1 20-6 22-14-12-2-21 3-22 14z" fill="#48b866"/>
    ${L >= 2 ? `<path d="M50 40c-10-1-15-8-15-15 9 0 15 5 15 15z" fill="#6fd68c"/>` : ""}
    ${L >= 3 ? `<g transform="translate(50 26)">${[0, 72, 144, 216, 288].map(a => `<ellipse rx="5" ry="9" transform="rotate(${a}) translate(0 -8)" fill="#ffb3c7"/>`).join("")}<circle r="5.5" fill="#ffd34d"/></g>` : ""}
    ${eye(43, 80)}${eye(57, 80)}${smile(50, 85)}`,
  fox: L => `<path d="M18 22l18 20-14 8z" fill="#ef7d32"/><path d="M82 22L64 42l14 8z" fill="#ef7d32"/><path d="M23 30l9 11-6 3z" fill="#ffd9bf"/><path d="M77 30l-9 11 6 3z" fill="#ffd9bf"/>
    <path d="M20 46c0-14 14-22 30-22s30 8 30 22c0 20-14 38-30 38S20 66 20 46z" fill="#f38b3c"/>
    <path d="M24 54c8 0 16 6 26 22 10-16 18-22 26-22-2 18-12 30-26 30S26 72 24 54z" fill="#fff4ea"/>
    ${eye(39, 52)}${eye(61, 52)}<ellipse cx="50" cy="66" rx="4" ry="3" fill="#1d1d2b"/>${blush(31, 61)}${blush(69, 61)}
    ${L >= 2 ? `<path d="M30 86h40l-6 8H36z" fill="#3b5bdb"/><path d="M47 86l3 8 3-8z" fill="#ffd34d"/>` : ""}`,
  turtle: L => `<ellipse cx="50" cy="62" rx="32" ry="22" fill="#7cc576"/><path d="M22 60c0-18 12-30 28-30s28 12 28 30z" fill="#3f9d55"/>
    <path d="M50 34l9 9-9 9-9-9zM34 46l8 7-6 7-8-4zM66 46l-8 7 6 7 8-4z" fill="#58b86a" opacity=".9"/>
    <circle cx="84" cy="56" r="11" fill="#8fd486"/>${eye(87, 53)}${smile(85, 60).replace("q5 5 10 0", "q3 4 7 0")}
    <ellipse cx="30" cy="82" rx="8" ry="5" fill="#8fd486"/><ellipse cx="66" cy="82" rx="8" ry="5" fill="#8fd486"/>
    ${L >= 2 ? `<path d="M74 44q10-10 18 0" stroke="#e03131" stroke-width="4" fill="none" stroke-linecap="round"/>` : ""}`,
  bee: L => `<ellipse cx="34" cy="34" rx="14" ry="11" fill="#d7f0ff" opacity=".9"/><ellipse cx="66" cy="34" rx="14" ry="11" fill="#d7f0ff" opacity=".9"/>
    <ellipse cx="50" cy="60" rx="28" ry="24" fill="#ffd23f"/><path d="M28 54h44v8H28zM26 70h48v7H26z" fill="#2b2b3a"/>
    <path d="M42 30q-6-12-12-12M58 30q6-12 12-12" stroke="#2b2b3a" stroke-width="2.5" fill="none"/><circle cx="30" cy="18" r="3.5" fill="#2b2b3a"/><circle cx="70" cy="18" r="3.5" fill="#2b2b3a"/>
    ${eye(41, 46)}${eye(59, 46)}${blush(34, 52)}${blush(66, 52)}
    ${L >= 2 ? `<circle cx="80" cy="76" r="6" fill="#ff6b9a"/><circle cx="80" cy="76" r="2.5" fill="#ffd34d"/>` : ""}`,
  lion: L => `<g fill="#c9772e">${Array.from({length: 12}, (_, i) => `<circle cx="${50 + 30 * Math.cos(i * Math.PI / 6)}" cy="${54 + 30 * Math.sin(i * Math.PI / 6)}" r="12"/>`).join("")}</g>
    <circle cx="50" cy="54" r="27" fill="#f6c453"/><circle cx="30" cy="34" r="7" fill="#f6c453"/><circle cx="70" cy="34" r="7" fill="#f6c453"/>
    ${eye(41, 50)}${eye(59, 50)}<path d="M45 60h10l-5 5z" fill="#7a4b2a"/><path d="M44 68q6 5 12 0" stroke="#1d1d2b" stroke-width="2.4" fill="none" stroke-linecap="round"/>${blush(33, 60)}${blush(67, 60)}
    ${L >= 2 ? `<path d="M40 82l10 6 10-6v8H40z" fill="#1f2a44"/><path d="M48 84l2 9 2-9z" fill="#c92a2a"/>` : ""}`,
  dragon: L => `<path d="M14 48l20-8-4 22zM86 48l-20-8 4 22z" fill="#9b7bea"/><circle cx="50" cy="56" r="28" fill="#7c5ce0"/>
    <path d="M36 32l-4-14 10 10zM64 32l4-14-10 10z" fill="#ffd34d"/><ellipse cx="50" cy="66" rx="17" ry="13" fill="#c8b8ff"/>
    ${eye(40, 50)}${eye(60, 50)}<circle cx="45" cy="64" r="1.8" fill="#4b3a8f"/><circle cx="55" cy="64" r="1.8" fill="#4b3a8f"/>${smile(50, 71)}
    ${L >= 2 ? `<path d="M78 74q10 4 8 14-6-6-12-4z" fill="#ff922b"/>` : ""}`,
};
const crown = `<path d="M34 6l6 10 10-12 10 12 6-10 2 16H32z" fill="#ffd34d" stroke="#e8a400" stroke-width="1.5"/>`;
function charSVG(id, L, size = 64) {
  const extra = L >= 3 ? crown : "", stars = L >= 2 ? `<text x="86" y="16" font-size="14">✨</text>` : "";
  return `<svg class="ch ch-${id}${L ? "" : " locked"}" viewBox="0 0 100 100" width="${size}" height="${size}" aria-hidden="true">${ART[id](Math.max(L, 1))}${extra}${stars}</svg>`;
}

/* ---------- maths ---------- */
let RW = null;
function statOf(r, k) { return k === "courses" ? (r.courses_done || []).length : (r[k] || 0); }
function levelOf(c, r) { const v = statOf(r, c.stat); return c.lv.filter(t => v >= t).length; }
function unlockedKeys(r) {
  const out = [];
  for (const c of CREW) for (let l = 1; l <= levelOf(c, r); l++) out.push(`c:${c.id}:${l}`);
  for (const b of BADGES) for (const t of b.at) if (statOf(r, b.stat) >= t) out.push(`b:${b.stat}:${t}`);
  for (const c of r.courses_done || []) out.push(`course:${c}`);
  return out;
}
function seenGet() { try { return JSON.parse(localStorage.getItem("mytutor-rewards-seen") || "null"); } catch (e) { return null; } }
function seenSet(a) { try { localStorage.setItem("mytutor-rewards-seen", JSON.stringify(a)); } catch (e) {} }

/* ---------- sound: generated in the browser, no files ---------- */
let AC = null;
function tone(f, t0, dur, type = "sine", vol = .14) {
  const o = AC.createOscillator(), g = AC.createGain();
  o.type = type; o.frequency.value = f; o.connect(g); g.connect(AC.destination);
  g.gain.setValueAtTime(0.0001, t0); g.gain.exponentialRampToValueAtTime(vol, t0 + .015); g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  o.start(t0); o.stop(t0 + dur + .05);
}
const CHIMES = {
  bell: t => { tone(1046.5, t, .9); tone(1318.5, t + .12, 1.1); },
  coin: t => { tone(987.8, t, .09, "square", .07); tone(1318.5, t + .08, .45, "square", .07); },
  marimba: t => { [784, 1046.5, 1318.5].forEach((f, i) => tone(f, t + i * .09, .35, "triangle", .16)); },
  sparkle: t => { [1568, 2093, 2637, 3136].forEach((f, i) => tone(f, t + i * .06, .5, "sine", .07)); },
  harp: t => { [523.3, 659.3, 784, 1046.5].forEach((f, i) => tone(f, t + i * .05, .9, "triangle", .1)); },
};
function playChime(name, big) {
  const s = getSet(); name = name || s.chime; if (!name || name === "off") return;
  try {
    AC = AC || new (window.AudioContext || window.webkitAudioContext)(); if (AC.state === "suspended") AC.resume();
    const t = AC.currentTime + .02;
    if (big) { [523.3, 659.3, 784].forEach((f, i) => tone(f, t + i * .11, .3, "triangle", .14)); [523.3, 659.3, 784, 1046.5].forEach(f => tone(f, t + .36, 1.4, "triangle", .08)); }
    else (CHIMES[name] || CHIMES.bell)(t);
  } catch (e) {}
}

/* ---------- celebrations ---------- */
function confetti(box) {
  const C = ["#ffd34d", "#ff6b9a", "#5cc97a", "#4dabf7", "#b197fc", "#ff922b"];
  for (let i = 0; i < 46; i++) {
    const s = document.createElement("i"); s.className = "cf";
    s.style.cssText = `left:${Math.random() * 100}%;background:${C[i % C.length]};animation-delay:${Math.random() * .5}s;animation-duration:${1.6 + Math.random() * 1.2}s;transform:rotate(${Math.random() * 360}deg)`;
    box.appendChild(s);
  }
}
const queue = []; let showing = false;
function celebrate(item) { queue.push(item); if (!showing) nextCelebration(); }
function nextCelebration() {
  const it = queue.shift(); if (!it) { showing = false; return; } showing = true;
  const m = document.createElement("div"); m.className = "reward-modal";
  m.innerHTML = `<div class="rw-card"><div class="rw-confetti"></div><div class="rw-art">${it.art}</div><div class="rw-kicker">${it.kicker}</div>
    <h2>${it.title}</h2><p>${it.text}</p><button class="b ok" type="button">Nice! Keep going</button></div>`;
  document.body.appendChild(m); confetti(m.querySelector(".rw-confetti")); playChime(null, true);
  const close = () => { m.classList.add("out"); setTimeout(() => { m.remove(); nextCelebration(); }, 220); };
  m.querySelector("button").onclick = close; m.onclick = e => { if (e.target === m) close(); };
  setTimeout(() => { if (m.isConnected) close(); }, 6500);
}
function describe(key, r) {
  const [k, a, b] = key.split(":");
  if (k === "c") { const c = CREW.find(x => x.id === a), L = +b;
    return {art: charSVG(a, L, 150), kicker: L === 1 ? "New crew member!" : `Level ${L}!`,
      title: L === 1 ? `${c.name} joined your crew` : `${c.name} grew to level ${L}`,
      text: `${c.role} · ${c.lv[L - 1]} ${c.unit}${L < 3 ? ` · next level at ${c.lv[L]}` : " · fully grown 👑"}`}; }
  if (k === "b") { const bd = BADGES.find(x => x.stat === a), t = +b, i = bd.at.indexOf(t);
    return {art: badgeHTML(bd, t, i, true, true), kicker: "Badge earned!", title: `${t} ${bd.unit}`, text: i + 1 < bd.at.length ? `Next badge at ${bd.at[i + 1]}.` : "That is the top badge. Legendary."}; }
  return {art: charSVG("dragon", 1, 150), kicker: "Course complete!", title: `${a} fully approved`, text: "Every note in this course is reviewed. Boardroom ready."};
}
function nudge(kinds, r) {               // the small "+1" after every save
  const s = getSet(); if (s.rewards === "off") return;
  const map = {approve: "approved", take: "takes", answer: "reflections"}, k = kinds.find(x => map[x]); if (!k) return;
  const c = CREW.find(x => x.stat === map[k]), v = statOf(r, c.stat), nextT = c.lv.find(t => v < t);
  const bd = BADGES.find(x => x.stat === c.stat), nb = bd && bd.at.find(t => v < t);
  let el = document.getElementById("rw-nudge"); if (!el) { el = document.createElement("div"); el.id = "rw-nudge"; document.body.appendChild(el); }
  el.innerHTML = `${charSVG(c.id, Math.max(1, levelOf(c, r)), 38)}<div><b>+1 ${({approve: "approved", take: "take", answer: "reflection"})[k]}</b><small>${nextT ? `${nextT - v} more to ${c.name} level ${c.lv.indexOf(nextT) + 1}` : nb ? `${nb - v} more to the ${nb} badge` : `${v} ${c.unit} 🎉`}</small></div>`;
  el.classList.remove("show"); void el.offsetWidth; el.classList.add("show");
  clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("show"), 2600);
}

/* ---------- rendering ---------- */
function badgeHTML(bd, t, i, earned, big) {
  return `<div class="badge ${earned ? TIER[Math.min(i, 3)] : "locked"}${big ? " big" : ""}" title="${t} ${bd.unit}"><div class="medal"><span>${bd.icon}</span><b>${t}</b></div>${big ? "" : `<small>${t} ${bd.unit}</small>`}</div>`;
}
function crewCard(c, r) {
  const L = levelOf(c, r), v = statOf(r, c.stat), nextT = c.lv[L], hide = c.secret && !L;
  const pct = nextT ? Math.round((v - (c.lv[L - 1] || 0)) / (nextT - (c.lv[L - 1] || 0)) * 100) : 100;
  return `<div class="crew-card${L ? "" : " is-locked"}">${charSVG(c.id, L, 84)}<b>${hide ? "???" : c.name}</b><small>${hide ? "Secret crew member" : c.role}</small>
    <div class="lvl">${L ? "★".repeat(L) + "☆".repeat(3 - L) : "Locked"}</div>
    <div class="cbar"><i data-w="${Math.max(0, Math.min(100, pct))}"></i></div>
    <small class="cnext">${hide ? "Approve every note in one course to meet them" : nextT ? `${nextT - v} more ${nextT - v === 1 ? c.unit.replace(/s\b/, "") : c.unit} to ${L ? "level " + (L + 1) : "unlock"}` : "Fully grown 👑"}</small></div>`;
}
function fillCrew() {
  const box = document.getElementById("crewbox"); if (!box || !RW) return;
  const r = RW, earned = [], next = [];
  for (const bd of BADGES) { const v = statOf(r, bd.stat);
    bd.at.forEach((t, i) => { if (v >= t) earned.push(badgeHTML(bd, t, i, true)); });
    const n = bd.at.findIndex(t => v < t); if (n >= 0) next.push(badgeHTML(bd, bd.at[n], n, false).replace("</small>", ` · ${bd.at[n] - v} to go</small>`)); }
  for (const c of r.courses_done || []) earned.push(`<div class="badge gold"><div class="medal"><span>🎓</span><b>✓</b></div><small>${esc(c)} complete</small></div>`);
  box.innerHTML = `<h2 id="crew">🌟 My crew</h2><p class="muted">Your study companions grow as you approve notes, write takes, reflect and keep your week streak.</p>
    <div class="crew-grid">${CREW.map(c => crewCard(c, r)).join("")}</div>
    <h2>🏅 Badges <small class="muted">${earned.length} earned</small></h2><div class="badges">${earned.join("") || '<p class="muted">Your first badge is close. See below.</p>'}</div>
    <p class="weekline"><b>Up next</b></p><div class="badges next">${next.join("")}</div>`;
  box.querySelectorAll("[data-w]").forEach(i => i.style.width = i.dataset.w + "%");   // CSP: no inline style attributes
}
function fillCrewRow() {
  const row = document.getElementById("td-crew"); if (!row || !RW) return;
  row.innerHTML = `<small class="td-lbl">🌟 My crew <a href="#" id="td-crewall">see all</a></small><div class="crew-row">${CREW.map(c => { const L = levelOf(c, RW);
    return `<span class="crew-mini" title="${c.secret && !L ? "Secret" : c.name}${L ? " · level " + L : " · locked"}">${charSVG(c.id, L, 38)}${L ? `<i>${L}</i>` : ""}</span>`; }).join("")}</div>`;
  document.getElementById("td-crewall").onclick = e => { e.preventDefault(); openCrew(); };
  row.querySelector(".crew-row").onclick = () => openCrew();
}
async function openCrew() {
  if (mode !== "activity") setMode("activity"); else await showActivity();
  setTimeout(() => { const h = document.getElementById("crew"); if (h) h.scrollIntoView({behavior: "smooth", block: "start"}); }, 350);
}

/* ---------- the loop ---------- */
async function refreshRewards(kinds) {
  let r; try { r = await api("/api/rewards"); } catch (e) { return; }
  RW = r; fillCrewRow(); fillCrew();
  const keys = unlockedKeys(r), seen = seenGet();
  if (seen === null) {                              // first time: welcome, don't replay every past unlock
    seenSet(keys);
    if (keys.length && getSet().rewards !== "off") celebrate({art: `<div class="rw-trio">${CREW.filter(c => levelOf(c, r)).slice(0, 3).map(c => charSVG(c.id, levelOf(c, r), 96)).join("") || charSVG("sprout", 1, 120)}</div>`,
      kicker: "Meet your crew!", title: "Your study rewards are here", text: `You have already earned ${keys.filter(k => k.startsWith("b:") || k.startsWith("course:")).length} badges and ${CREW.filter(c => levelOf(c, r)).length} crew members. They grow as you keep going.`});
    return;
  }
  const fresh = keys.filter(k => !seen.includes(k)); seenSet([...new Set([...seen, ...keys])]);
  if (getSet().rewards === "off") return;
  if (fresh.length) fresh.slice(0, 4).forEach(k => celebrate(describe(k, r)));
  else if (kinds && kinds.length) nudge(kinds, r);
}
let pend = [], pendT = null;
function rewardsTick(path) {                         // called after every successful save
  const kind = ({"/api/approve": "approve", "/api/take": "take", "/api/answer": "answer", "/api/take-edit": "edit", "/api/needs-fix": "fix"})[path];
  if (!kind) return;
  pend.push(kind); if (pendT) return;
  playChime();
  pendT = setTimeout(() => { const k = pend; pend = []; pendT = null; refreshRewards(k); }, 300);
}
window.rewardsTick = rewardsTick; window.fillCrew = fillCrew; window.fillCrewRow = fillCrewRow;
document.querySelectorAll('[data-set="chime"] button').forEach(b => b.addEventListener("click", () => playChime(b.dataset.v)));
const tr = document.getElementById("s-rwtest"); if (tr) tr.onclick = () => celebrate({art: charSVG("fox", 2, 150), kicker: "Preview", title: "This is a level-up", text: "Pop-ups like this appear when a crew member joins or grows, or you earn a badge."});
refreshRewards();
