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
let RW = null, RW_PREV = null;
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
  o.type = type; o.frequency.value = f; o.connect(g); g.connect(AC._master || AC.destination);
  g.gain.setValueAtTime(0.0001, t0); g.gain.exponentialRampToValueAtTime(vol, t0 + .015); g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  o.start(t0); o.stop(t0 + dur + .05);
}
// [frequency Hz, start s, length s, wave, volume]: short melody + soft fading chord, about 5-7 seconds
const CHIME_NOTES = {"bell":[[1046.5,0.0,3.8,"sine",0.12],[1318.5,0.28,3.8,"sine",0.12],[1568.0,0.56,3.8,"sine",0.12],[2093.0,0.95,4.2,"sine",0.08],[523.3,0.95,4.3,"sine",0.045],[784.0,0.95,4.3,"sine",0.045]],"coin":[[987.8,0,0.1,"square",0.06],[1318.5,0.09,0.6,"square",0.06],[1318.5,0.6,1.0,"triangle",0.07],[1661.2,0.75,1.0,"triangle",0.07],[1975.5,0.9,1.0,"triangle",0.07],[659.3,0.95,4.4,"sine",0.045],[987.8,0.95,4.4,"sine",0.045],[1318.5,0.95,4.4,"sine",0.045]],"marimba":[[784.0,0.0,0.7,"triangle",0.15],[1046.5,0.18,0.7,"triangle",0.15],[1318.5,0.36,0.7,"triangle",0.15],[1568.0,0.54,0.7,"triangle",0.15],[1318.5,0.72,0.7,"triangle",0.15],[1046.5,0.9,0.7,"triangle",0.15],[523.3,1.05,4.3,"sine",0.05],[659.3,1.05,4.3,"sine",0.05],[784.0,1.05,4.3,"sine",0.05]],"sparkle":[[1568.0,0.0,1.6,"sine",0.06],[2093.0,0.13,1.6,"sine",0.06],[2637.0,0.26,1.6,"sine",0.06],[3136.0,0.39,1.6,"sine",0.06],[2637.0,0.52,1.6,"sine",0.06],[2093.0,0.65,1.6,"sine",0.06],[1568.0,0.78,1.6,"sine",0.06],[1318.5,0.91,1.6,"sine",0.06],[1046.5,0.9,4.4,"sine",0.035],[1568.0,0.9,4.4,"sine",0.035]],"harp":[[261.6,0.0,3.0,"triangle",0.09],[329.6,0.11,3.0,"triangle",0.09],[392.0,0.22,3.0,"triangle",0.09],[523.3,0.33,3.0,"triangle",0.09],[659.3,0.44,3.0,"triangle",0.09],[784.0,0.55,3.0,"triangle",0.09],[1046.5,0.66,3.0,"triangle",0.09],[1318.5,0.77,3.0,"triangle",0.09],[1046.5,1.1,3.2,"triangle",0.07],[784.0,1.26,3.2,"triangle",0.07],[659.3,1.42,3.2,"triangle",0.07],[523.3,1.6,3.8,"sine",0.035],[659.3,1.6,3.8,"sine",0.035],[784.0,1.6,3.8,"sine",0.035]],"fanfare":[[523.3,0.0,0.45,"triangle",0.14],[659.3,0.16,0.45,"triangle",0.14],[784.0,0.32,0.45,"triangle",0.14],[1046.5,0.5,1.2,"triangle",0.14],[784.0,1.25,0.5,"triangle",0.12],[1046.5,1.45,0.5,"triangle",0.12],[1318.5,1.7,1.6,"triangle",0.13],[261.6,2.2,4.6,"triangle",0.05],[523.3,2.2,4.6,"triangle",0.05],[659.3,2.2,4.6,"triangle",0.05],[784.0,2.2,4.6,"triangle",0.05],[1046.5,2.2,4.6,"triangle",0.05],[1318.5,2.2,4.6,"triangle",0.05]]};
function playNotes(notes, t) {
  for (const [f, t0, d, ty, v] of notes) { tone(f, t + t0, d, ty, v); tone(f, t + t0 + .32, d, ty, v * .32); tone(f, t + t0 + .64, d, ty, v * .1); }
}
function playChime(name, big) {
  const s = getSet(); name = name || s.chime; if (!name || name === "off") return;
  try {
    AC = AC || new (window.AudioContext || window.webkitAudioContext)(); if (AC.state === "suspended") AC.resume();
    if (AC._master) { try { AC._master.gain.cancelScheduledValues(0); AC._master.disconnect(); } catch (e) {} }   // a new chime replaces one still ringing
    AC._master = AC.createGain(); AC._master.connect(AC.destination);
    playNotes(big ? CHIME_NOTES.fanfare : (CHIME_NOTES[name] || CHIME_NOTES.bell), AC.currentTime + .02);
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
  document.body.appendChild(m); confetti(m.querySelector(".rw-confetti")); playChime(null, true); fireworks(); popSound(5, .5);
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
const CHEERS = {approve: ["Note approved!", "Another one done!", "Sharp work!", "On a roll!", "Board-ready thinking!"],
  take: ["Take saved!", "Your voice, on record!", "Strategist move!", "Insight captured!"],
  answer: ["Reflection saved!", "Deep thinking!", "Connected the dots!"],
  fix: ["Flagged for fixing!", "Good catch!"], edit: ["Take polished!", "Sharper now!"]};
function nudge(kinds, r) {               // achievement card with the character, as long as the chime plays
  const s = getSet(); if (s.rewards === "off") return;
  const map = {approve: "approved", take: "takes", answer: "reflections", fix: "approved", edit: "takes"};
  const k = ["approve", "take", "answer", "fix", "edit"].find(x => kinds.includes(x)); if (!k) return;
  const c = CREW.find(x => x.stat === map[k]), v = statOf(r, c.stat), L = levelOf(c, r), nextT = c.lv[L], prevT = c.lv[L - 1] || 0;
  const bd = BADGES.find(x => x.stat === c.stat), nb = bd && bd.at.find(t => v < t);
  const pct = nextT ? Math.round((v - prevT) / (nextT - prevT) * 100) : 100;
  const both = kinds.includes("approve") && kinds.includes("take") ? " + take saved" : "";
  const cheer = CHEERS[k][Math.floor(Math.random() * CHEERS[k].length)];
  let el = document.getElementById("rw-nudge"); if (!el) { el = document.createElement("div"); el.id = "rw-nudge"; document.body.appendChild(el); el.onclick = () => el.classList.remove("show"); }
  el.innerHTML = `<div class="rn-art">${charSVG(c.id, Math.max(1, L), 78)}</div><div class="rn-txt"><span class="rn-kick">🏅 Achievement</span><b>${cheer}${both}</b>
    <small>${c.name} · ${L ? "level " + L : "on the way"} · ${v} ${c.unit}</small><div class="cbar"><i></i></div>
    <small>${nextT ? `${nextT - v} more to ${c.name} level ${L + 1}` : nb ? `${nb - v} more to the ${nb} badge` : "Fully grown 👑"}${nb && nextT ? ` · ${nb - v} to the ${nb} badge` : ""}</small></div>`;
  el.classList.remove("show"); void el.offsetWidth; el.classList.add("show");
  const bar = el.querySelector(".cbar i"); bar.style.width = "0%"; setTimeout(() => bar.style.width = Math.max(4, pct) + "%", 250);
  clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("show"), getSet().chime === "off" ? 4000 : 6500);
}

/* ---------- party poppers & fireworks (one full-screen canvas, clicks pass through) ---------- */
const FX_COL = ["#ffd34d", "#ff6b9a", "#5cc97a", "#4dabf7", "#b197fc", "#ff922b", "#ffffff"];
let fxParts = [], fxRun = false, fxCv = null;
function fxCanvas() {
  if (!fxCv) { fxCv = document.createElement("canvas"); fxCv.id = "fx"; document.body.appendChild(fxCv); }
  fxCv.width = innerWidth * devicePixelRatio; fxCv.height = innerHeight * devicePixelRatio; return fxCv;
}
function fxLoop() {
  const cv = fxCv, g = cv.getContext("2d"), d = devicePixelRatio; g.setTransform(d, 0, 0, d, 0, 0); g.clearRect(0, 0, innerWidth, innerHeight);
  const add = [];
  fxParts = fxParts.filter(p => {
    p.t++; p.vx *= p.drag; p.vy = p.vy * p.drag + p.g; p.x += p.vx; p.y += p.vy;
    if (p.kind === "rocket") { g.fillStyle = "#fff6d0"; g.fillRect(p.x - 1.5, p.y, 3, 7);
      if (p.vy > -1.5 || p.t > p.life) { for (let i = 0; i < 70; i++) { const a = Math.PI * 2 * i / 70, s = 2 + Math.random() * 3.2;
          add.push({kind: "spark", x: p.x, y: p.y, vx: Math.cos(a) * s, vy: Math.sin(a) * s, g: .045, drag: .985, t: 0, life: 70 + Math.random() * 30, c: p.c}); } return false; }
      return true; }
    const a = Math.max(0, 1 - p.t / p.life); g.globalAlpha = a; g.fillStyle = p.c;
    if (p.kind === "spark") { g.beginPath(); g.arc(p.x, p.y, 2.2, 0, 7); g.fill(); }
    else { g.save(); g.translate(p.x, p.y); g.rotate(p.r += p.vr); g.fillRect(-p.w / 2, -p.h / 2, p.w, p.h); g.restore(); }
    g.globalAlpha = 1; return p.t < p.life && p.y < innerHeight + 40;
  });
  fxParts.push(...add);
  if (fxParts.length) requestAnimationFrame(fxLoop); else { fxRun = false; g.clearRect(0, 0, innerWidth, innerHeight); }
}
function fxStart() { if (!fxRun) { fxRun = true; requestAnimationFrame(fxLoop); } }
function partyPopper() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  fxCanvas();
  for (const side of [0, 1]) for (let i = 0; i < 90; i++) {
    const ang = (side ? -1 : 1) * (0.35 + Math.random() * 0.5), sp = 11 + Math.random() * 9;
    fxParts.push({kind: "paper", x: side ? innerWidth - 20 : 20, y: innerHeight - 20, vx: Math.sin(ang) * sp, vy: -Math.cos(ang) * sp,
      g: .28, drag: .975, t: 0, life: 150 + Math.random() * 60, c: FX_COL[i % FX_COL.length], w: 6 + Math.random() * 6, h: 4 + Math.random() * 8, r: Math.random() * 6, vr: (Math.random() - .5) * .4});
  }
  fxStart();
}
function fireworks() {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  fxCanvas();
  for (let k = 0; k < 7; k++) setTimeout(() => {
    fxParts.push({kind: "rocket", x: innerWidth * (.15 + Math.random() * .7), y: innerHeight, vx: (Math.random() - .5) * 2, vy: -(10 + Math.random() * 4),
      g: .16, drag: .995, t: 0, life: 90, c: FX_COL[k % FX_COL.length]}); fxStart(); }, k * 520);
  setTimeout(partyPopper, 300);
}
function popSound(n, delay) {                 // little "pop" bursts made from noise
  if (getSet().chime === "off") return;
  try {
    AC = AC || new (window.AudioContext || window.webkitAudioContext)();
    const len = AC.sampleRate * .12, buf = AC.createBuffer(1, len, AC.sampleRate), ch = buf.getChannelData(0);
    for (let i = 0; i < len; i++) ch[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 4);
    for (let k = 0; k < n; k++) { const s = AC.createBufferSource(), g = AC.createGain(), f = AC.createBiquadFilter();
      f.type = "bandpass"; f.frequency.value = 900 + Math.random() * 1500; s.buffer = buf; g.gain.value = .35;
      s.connect(f); f.connect(g); g.connect(AC.destination); s.start(AC.currentTime + delay + k * (n > 2 ? .52 : .07) + Math.random() * .05); }
  } catch (e) {}
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
  RW_PREV = RW; RW = r; fillCrewRow(); fillCrew();
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
  else if (kinds && kinds.length) {
    nudge(kinds, r);
    const prev = RW_PREV || {}, hit = ["approved", "takes", "reflections"].find(k => statOf(r, k) > (prev[k] || 0) && statOf(r, k) % 5 === 0);
    if (hit) { partyPopper(); popSound(2, .0); }              // every 5th: party poppers
  }
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
window.partyPopper = partyPopper; window.fireworks = fireworks;
const tr = document.getElementById("s-rwtest"); if (tr) tr.onclick = () => celebrate({art: charSVG("fox", 2, 150), kicker: "Preview", title: "This is a level-up", text: "Pop-ups like this appear when a crew member joins or grows, or you earn a badge."});
refreshRewards();
