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
  for (let i = 1; i <= rankOf(xpOf(r)); i++) out.push(`rank:${i}`);
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
/* Kalimba (thumb piano) save tune, about 3 seconds, made in the browser with Web Audio. */
const KALIMBA = [[72,0,.8,-.2],[76,.13,.7,.2],[79,.26,.75,0],[84,.4,.8,.2],[81,.62,.7,-.2],[79,.75,.7,0],[76,.88,.7,.2],
  [77,1.1,.65,-.2],[76,1.23,.65,0],[74,1.36,.65,.2],[72,1.62,.85,0],[79,1.62,.45,-.2],[84,1.65,.5,.2]];
const KALIMBA_SHORT = [[72,0,.8,-.2],[76,.1,.7,.2],[79,.2,.75,0],[84,.3,.8,.2],[72,.55,.8,0],[79,.55,.45,-.2],[84,.58,.5,.2]];
const KALIMBA_BIG = KALIMBA.concat([[88,1.95,.55,.2],[91,2.08,.5,-.2],[96,2.21,.6,0]]);
function playKalimba(ac, big, dest, volume = .22, short = false) {
  const t0 = ac.currentTime + .03, out = ac.createGain(); out.gain.value = volume;
  const echo = ac.createDelay(); echo.delayTime.value = .13; const fb = ac.createGain(); fb.gain.value = .28; const wet = ac.createGain(); wet.gain.value = .35;
  dest = dest || ac.destination; out.connect(dest); out.connect(echo); echo.connect(fb); fb.connect(echo); echo.connect(wet); wet.connect(dest);
  for (const [m, t, v, pan] of (big ? KALIMBA_BIG : short ? KALIMBA_SHORT : KALIMBA)) {
    const f = 440 * 2 ** ((m - 69) / 12), at = t0 + t, p = ac.createStereoPanner ? ac.createStereoPanner() : ac.createGain();
    if (p.pan) p.pan.value = pan; p.connect(out);
    for (const [mul, amp, len] of [[1, v, short ? .95 : 1.5], [5.4, v * .22, .09]]) {      // tine + its bright "click"
      const o = ac.createOscillator(), g = ac.createGain(); o.type = "sine"; o.frequency.value = f * mul;
      g.gain.setValueAtTime(0.0001, at); g.gain.exponentialRampToValueAtTime(amp, at + .004); g.gain.exponentialRampToValueAtTime(0.0001, at + len);
      o.connect(g); g.connect(p); o.start(at); o.stop(at + len + .05);
    }
  }
  setTimeout(() => { try { fb.gain.value = 0; } catch (e) {} }, (big ? 3.6 : 3.0) * 1000);
}

function playNotes(notes, t) {
  for (const [f, t0, d, ty, v] of notes) { tone(f, t + t0, d, ty, v); tone(f, t + t0 + .32, d, ty, v * .32); tone(f, t + t0 + .64, d, ty, v * .1); }
}
function playChime(name, big) {
  const s = getSet(); name = name || s.chime; if (!name || name === "off") return;
  try {
    AC = AC || new (window.AudioContext || window.webkitAudioContext)(); if (AC.state === "suspended") AC.resume();
    if (AC._master) { try { AC._master.gain.cancelScheduledValues(0); AC._master.disconnect(); } catch (e) {} }   // a new chime replaces one still ringing
    AC._master = AC.createGain(); AC._master.connect(AC.destination);
    if (name === "kalimba" || name === "kalimba-short") playKalimba(AC, big, AC._master, .22, name === "kalimba-short" && !big);
    else playNotes(big ? CHIME_NOTES.fanfare : (CHIME_NOTES[name] || CHIME_NOTES.bell), AC.currentTime + .02);
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
  m.innerHTML = `<div class="rw-card"><div class="rw-confetti"></div><div class="rw-art">${it.ellieDone ? it.art : `<div class="rw-duo">${it.art}<div class="m-jump">${ellie("graduate", 120)}</div></div>`}</div><div class="rw-kicker">${it.kicker}</div>
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
  if (k === "rank") { const R = RANKS[+a], w = WARDROBE.find(x => x.rank === +a && x.id);
    return {art: `<div class="m-dance">${ellie(w ? w.id : "champion", 150)}</div>`, kicker: "🎖 Promotion!", ellieDone: true,
      title: `You are now ${R.icon} ${R.name}`, text: `${xpOf(RW).toLocaleString()} XP.${w ? ` New outfit unlocked for Ellie: ${w.name}.` : ""}${RANKS[+a + 1] ? ` Next: ${RANKS[+a + 1].name} at ${RANKS[+a + 1].xp.toLocaleString()} XP.` : " The top of the ladder!"}`}; }
  return {art: charSVG("dragon", 1, 150), kicker: "Course complete!", title: `${a} fully approved`, text: "Every note in this course is reviewed. Boardroom ready."};
}
const CHEERS = {approve: ["Note approved!", "Another one done!", "Sharp work!", "On a roll!", "Board-ready thinking!"],
  take: ["Take saved!", "Your voice, on record!", "Strategist move!", "Insight captured!"],
  answer: ["Reflection saved!", "Deep thinking!", "Connected the dots!"],
  fix: ["Flagged for fixing!", "Good catch!"], edit: ["Take polished!", "Sharper now!"]};
const ELLIE_LOOK = {approve: ["", "m-wave"], take: ["boss", "m-toot"], edit: ["boss", "m-toot"], answer: ["graduate", "m-wave"], fix: ["", "m-toot"],
  five: ["party", "m-dance"], goal: ["champion", "m-dance"]};
function nudge(kinds, r, moment, update) {       // Ellie's achievement card, shown while the tune plays
  const s = getSet(); if (s.rewards === "off") return;
  const map = {approve: "approved", take: "takes", answer: "reflections", fix: "approved", edit: "takes"};
  const k = ["approve", "take", "answer", "fix", "edit"].find(x => kinds.includes(x)); if (!k) return;
  const c = CREW.find(x => x.stat === map[k]), v = statOf(r, c.stat), L = levelOf(c, r), nextT = c.lv[L], prevT = c.lv[L - 1] || 0;
  const bd = BADGES.find(x => x.stat === c.stat), nb = bd && bd.at.find(t => v < t), goal = typeof weeklyGoal === "function" ? weeklyGoal() : 25;
  let pct = nextT ? Math.round((v - prevT) / (nextT - prevT) * 100) : 100;
  const both = "";                                       // (approve + take is shown in the status line instead)
  if (!update || !nudge._cheer) nudge._cheer = CHEERS[k][Math.floor(Math.random() * CHEERS[k].length)];
  let kick = "🏅 Achievement", title = nudge._cheer + both,
      line1 = `${c.name} · ${L ? "level " + L : "on the way"} · ${v} ${c.unit}`,
      line2 = nextT ? `${nextT - v} more to ${c.name} level ${L + 1}` : nb ? `${nb - v} more to the ${nb} badge` : "Fully grown 👑";
  if (moment === "five") { kick = "🎉 Party time"; title = `${v} ${c.unit}!`; line2 = `Every 5 is a party. Next one at ${v + 5}.`; }
  if (moment === "goal" && r.approved_week > goal) { kick = "🚀 Stretch goal"; title = `${r.approved_week} approved: stretch reached!`; line1 = `${r.approved_week - goal} above your goal of ${goal} · 🔥 ${r.week_streak || 0}-week streak`; line2 = "Great going this week!"; pct = 100; }
  else if (moment === "goal") { kick = "👑 Weekly goal"; title = `${r.approved_week} / ${goal}: goal reached!`; line1 = `🔥 ${r.week_streak || 0}-week streak · boardroom ready`; line2 = "Great week! Anything more is a bonus."; pct = 100; }
  let [costume, motion] = ELLIE_LOOK[moment || k];
  const pick = chosenCostume(); if (pick !== null && !moment) costume = pick;
  const gained = Math.max(0, xpOf(r) - xpOf(update ? RW_PREV : RW)), xpTxt = gained ? `<span class="rn-xp">+${gained} XP</span>` : "";
  if (combo >= 2 && !moment) kick = `🔥 Combo x${combo}`;
  let el = document.getElementById("rw-nudge"); if (!el) { el = document.createElement("div"); el.id = "rw-nudge"; document.body.appendChild(el); el.onclick = () => el.classList.remove("show"); }
  el.innerHTML = `<div class="rn-art ${motion}">${ellie(costume, 92)}</div><div class="rn-txt"><div class="rn-top"><span class="rn-kick">${kick}</span>${xpTxt}</div><b>${title}</b>
    <small>${line1}</small><div class="cbar"><i></i></div><small>${line2}</small></div>`;
  const keep = update && el.classList.contains("show") && !moment;   // refresh the numbers without replaying the entrance
  if (!keep) { el.classList.remove("show"); void el.offsetWidth; el.classList.add("show"); }
  const bar = el.querySelector(".cbar i"); bar.style.width = keep ? Math.max(4, pct) + "%" : "0%"; if (!keep) setTimeout(() => bar.style.width = Math.max(4, pct) + "%", 120);
  el.classList.toggle("combo", combo >= 3 && !moment);
  if (!keep) { clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("show"), moment ? 5200 : 4000); }
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
    <p class="weekline"><b>Up next</b></p><div class="badges next">${next.join("")}</div>
    <h2>🎖 Career ladder <small class="muted">${xpOf(r).toLocaleString()} XP</small></h2><div class="ladder">${RANKS.map((R, i) => `<div class="rung${i <= rankOf(xpOf(r)) ? " got" : ""}${i === rankOf(xpOf(r)) ? " now" : ""}"><span>${R.icon}</span><b>${R.name}</b><small>${R.xp.toLocaleString()} XP</small></div>`).join("")}</div>
    <p class="muted small">XP: approve a note +10 · write a take +25 · answer a reflection +15 · each memory line +20</p>
    <h2>👗 Ellie's wardrobe</h2><div class="wardrobe">${[{id: "auto", name: "Auto (fits the moment)", rank: 0}].concat(WARDROBE).map(w => { const open = w.id === "auto" || rankOf(xpOf(r)) >= w.rank, cur = (getSet().ellie || "auto") === (w.id === "" ? "everyday" : w.id);
      return `<button class="wcard${open ? "" : " locked"}${cur ? " on" : ""}" data-ellie="${w.id === "" ? "everyday" : w.id}" ${open ? "" : "disabled"}>${ellie(w.id === "auto" ? "" : w.id, 84)}<b>${w.name}</b><small>${open ? (cur ? "Wearing" : "Tap to wear") : "Unlocks at " + RANKS[w.rank].name}</small></button>`; }).join("")}</div>`;
  box.querySelectorAll("[data-ellie]").forEach(b => b.onclick = () => { saveSet("ellie", b.dataset.ellie); fillCrew(); const n = document.getElementById("rw-nudge"); });
  box.querySelectorAll("[data-w]").forEach(i => i.style.width = i.dataset.w + "%");   // CSP: no inline style attributes
}
function fillCrewRow() {
  const row = document.getElementById("um-crew"); if (!row || !RW) return;     // lives in the profile menu
  row.innerHTML = `<small class="td-lbl">🌟 My crew <a href="#" id="td-crewall">see all</a></small><div class="crew-row">${CREW.map(c => { const L = levelOf(c, RW);
    return `<span class="crew-mini" title="${c.secret && !L ? "Secret" : c.name}${L ? " · level " + L : " · locked"}">${charSVG(c.id, L, 30)}${L ? `<i>${L}</i>` : ""}</span>`; }).join("")}</div>`;
  document.getElementById("td-crewall").onclick = e => { e.preventDefault(); document.getElementById("umenu").hidden = true; openCrew(); };
  row.querySelector(".crew-row").onclick = () => { document.getElementById("umenu").hidden = true; openCrew(); };
}
async function openCrew() {
  if (mode !== "activity") setMode("activity"); else await showActivity();
  setTimeout(() => { const h = document.getElementById("crew"); if (h) h.scrollIntoView({behavior: "smooth", block: "start"}); }, 350);
}


/* ---------- XP & career ladder, combo, Ellie's wardrobe, quote of the day ---------- */
const XP_PER = {approved: 10, takes: 25, reflections: 15, memory_lines: 20};
function xpOf(r) { return r ? Object.entries(XP_PER).reduce((a, [k, v]) => a + (r[k] || 0) * v, 0) : 0; }
const RANKS = [
  {name: "Analyst", xp: 0, icon: "📋"}, {name: "Senior Analyst", xp: 500, icon: "📈", unlock: "party"},
  {name: "Manager", xp: 1200, icon: "🧭", unlock: "graduate"}, {name: "Senior Manager", xp: 2200, icon: "🗂️"},
  {name: "Director", xp: 3500, icon: "🎯", unlock: "boss"}, {name: "Vice President", xp: 5500, icon: "🚀"},
  {name: "C-suite", xp: 8000, icon: "🏛️", unlock: "champion"}, {name: "Board Chair", xp: 12000, icon: "👑"}];
function rankOf(xp) { let i = 0; RANKS.forEach((r, k) => { if (xp >= r.xp) i = k; }); return i; }
const WARDROBE = [
  {id: "", name: "Everyday", rank: 0}, {id: "party", name: "Party hat", rank: 1}, {id: "graduate", name: "Graduate", rank: 2},
  {id: "boss", name: "C-suite", rank: 4}, {id: "champion", name: "Champion", rank: 6}];
function wardrobeOpen(id) { const w = WARDROBE.find(x => x.id === id); return !!w && RW && rankOf(xpOf(RW)) >= w.rank; }
function chosenCostume() { const c = getSet().ellie; return c && c !== "auto" && wardrobeOpen(c === "everyday" ? "" : c) ? (c === "everyday" ? "" : c) : null; }

let combo = 0, lastSave = 0;
function bumpCombo() { const now = Date.now(); combo = now - lastSave < 180e3 ? combo + 1 : 1; lastSave = now; return combo; }

function fillRank() {
  const row = document.getElementById("rankpill"); if (!row || !RW) return;    // compact rank & XP in the header
  const xp = xpOf(RW), i = rankOf(xp), R = RANKS[i], N = RANKS[i + 1];
  const pct = N ? Math.round((xp - R.xp) / (N.xp - R.xp) * 100) : 100;
  row.hidden = false;
  row.title = `${R.name} · ${xp.toLocaleString()} XP` + (N ? ` · ${(N.xp - xp).toLocaleString()} XP to ${N.name}` : " · top of the ladder") + ". Click for your crew and ladder.";
  row.innerHTML = `<span class="rk-badge">${R.icon}</span><span class="rk-txt"><b>${R.name}</b><small>${xp.toLocaleString()} XP</small><span class="rk-bar"><i></i></span></span>`;
  row.querySelector(".rk-bar i").style.width = Math.max(3, pct) + "%";
  row.onclick = () => openCrew();
}

const QUOTES = [
  ["The best way to predict the future is to create it.", "attributed to Peter Drucker"],
  ["Management is doing things right; leadership is doing the right things.", "Peter Drucker"],
  ["The greatest danger in times of turbulence is not the turbulence; it is to act with yesterday's logic.", "Peter Drucker"],
  ["Culture eats strategy for breakfast.", "attributed to Peter Drucker"],
  ["The essence of strategy is choosing what not to do.", "Michael Porter"],
  ["Leadership is the capacity to translate vision into reality.", "Warren Bennis"],
  ["A leader is one who knows the way, goes the way, and shows the way.", "John C. Maxwell"],
  ["Before you are a leader, success is all about growing yourself. When you become a leader, success is all about growing others.", "Jack Welch"],
  ["Change before you have to.", "Jack Welch"],
  ["Innovation distinguishes between a leader and a follower.", "Steve Jobs"],
  ["Your most unhappy customers are your greatest source of learning.", "Bill Gates"],
  ["If you are not embarrassed by the first version of your product, you've launched too late.", "Reid Hoffman"],
  ["People don't buy what you do; they buy why you do it.", "Simon Sinek"],
  ["Leadership is not about being in charge. It is about taking care of those in your charge.", "Simon Sinek"],
  ["The function of leadership is to produce more leaders, not more followers.", "Ralph Nader"],
  ["Vision without execution is hallucination.", "attributed to Thomas Edison"],
  ["It always seems impossible until it's done.", "Nelson Mandela"],
  ["Education is the most powerful weapon which you can use to change the world.", "Nelson Mandela"],
  ["Success is not final, failure is not fatal: it is the courage to continue that counts.", "attributed to Winston Churchill"],
  ["Strategy without tactics is the slowest route to victory. Tactics without strategy is the noise before defeat.", "attributed to Sun Tzu"],
  ["We are what we repeatedly do. Excellence, then, is not an act, but a habit.", "Will Durant"],
  ["An investment in knowledge pays the best interest.", "Benjamin Franklin"],
  ["Live as if you were to die tomorrow. Learn as if you were to live forever.", "attributed to Mahatma Gandhi"],
  ["Price is what you pay. Value is what you get.", "Warren Buffett"],
  ["Risk comes from not knowing what you're doing.", "Warren Buffett"],
  ["Whether you think you can, or you think you can't, you're right.", "attributed to Henry Ford"],
  ["Coming together is a beginning, staying together is progress, and working together is success.", "attributed to Henry Ford"],
  ["Quality means doing it right when no one is looking.", "attributed to Henry Ford"],
  ["Ideas are easy. Implementation is hard.", "Guy Kawasaki"],
  ["If you want to go fast, go alone. If you want to go far, go together.", "proverb"],
  ["The secret of getting ahead is getting started.", "attributed to Mark Twain"],
  ["Done is better than perfect.", "Sheryl Sandberg"],
  ["A goal without a plan is just a wish.", "attributed to Antoine de Saint-Exupéry"],
  ["Learning never exhausts the mind.", "attributed to Leonardo da Vinci"],
  ["The only way to do great work is to love what you do.", "Steve Jobs"],
  ["Patience, persistence and perspiration make an unbeatable combination for success.", "Napoleon Hill"]];
let qIdx = null;
function showQuote(step) {
  const t = document.getElementById("td-qtext"); if (!t) return;
  const day = Math.floor((Date.now() - new Date().getTimezoneOffset() * 60e3) / 864e5);
  qIdx = qIdx === null ? day % QUOTES.length : (qIdx + step + QUOTES.length) % QUOTES.length;
  const [q, by] = QUOTES[qIdx]; t.textContent = "“" + q + "”"; document.getElementById("td-qby").textContent = "— " + by;
}
window.fillRank = fillRank; window.showQuote = showQuote;
const qn = document.getElementById("td-qnext"); if (qn) qn.onclick = () => showQuote(1);
showQuote(0);

/* ---------- the loop ---------- */
async function refreshRewards(kinds) {
  let r; try { r = await api("/api/rewards"); } catch (e) { return; }
  RW_PREV = RW; RW = r; fillCrewRow(); fillCrew(); fillRank();
  if (!RW_PREV && typeof weeklyTarget === "function" && (r.approved_week || 0) >= weeklyTarget() && getSet().rewards !== "off") setTimeout(askStretch, 2500);   // already past the target when the app opens
  const keys = unlockedKeys(r), seen = seenGet();
  if (seen === null) {                              // first time: welcome, don't replay every past unlock
    seenSet(keys);
    if (keys.length && getSet().rewards !== "off") celebrate({art: `<div class="rw-trio">${CREW.filter(c => levelOf(c, r)).slice(0, 3).map(c => charSVG(c.id, levelOf(c, r), 96)).join("") || charSVG("sprout", 1, 120)}</div>`,
      kicker: "Meet your crew!", title: "Your study rewards are here", text: `You have already earned ${keys.filter(k => k.startsWith("b:") || k.startsWith("course:")).length} badges and ${CREW.filter(c => levelOf(c, r)).length} crew members. They grow as you keep going.`});
    return;
  }
  let fresh = keys.filter(k => !seen.includes(k)); seenSet([...new Set([...seen, ...keys])]);
  const newRanks = fresh.filter(k => k.startsWith("rank:"));                 // a promotion: celebrate only the highest new rank, first
  if (newRanks.length) fresh = [newRanks[newRanks.length - 1], ...fresh.filter(k => !k.startsWith("rank:"))];
  if (getSet().rewards === "off") return;
  if (fresh.length) fresh.slice(0, 4).forEach(k => celebrate(describe(k, r)));
  else if (kinds && kinds.length) {
    const prev = RW_PREV || {}, goal = typeof weeklyGoal === "function" ? weeklyGoal() : 25;
    const wk0 = prev.approved_week, wk1 = r.approved_week, tgt = typeof weeklyTarget === "function" ? weeklyTarget() : goal;
    const goalHit = wk0 != null && wk0 < tgt && wk1 >= tgt;                     // reached this week's target (goal or accepted stretch)
    const five = ["approved", "takes", "reflections"].find(k => statOf(r, k) > (prev[k] || 0) && statOf(r, k) % 5 === 0);
    const moment = goalHit ? "goal" : five ? "five" : null;
    nudge(kinds, r, moment, true);
    if (moment === "goal") { playChime(null, true); fireworks(); popSound(5, .5); setTimeout(askStretch, 3200); }   // weekly goal: fireworks, then ask about a stretch
    else if (wk1 > tgt && wk1 > (wk0 || 0) && wk1 % 5 === 0) setTimeout(askStretch, 3200);   // already past the target: suggest a higher one at every 5th
    else if (moment === "five") { partyPopper(); popSound(2, 0); }                     // every 5th: party poppers
  }
}
let pend = [], pendT = null;
function rewardsTick(path) {                         // called after every successful save
  const kind = ({"/api/approve": "approve", "/api/take": "take", "/api/answer": "answer", "/api/take-edit": "edit", "/api/needs-fix": "fix"})[path];
  if (!kind) return;
  pend.push(kind); if (pendT) return;
  if (kind !== "edit") bumpCombo();
  if ((kind === "take" || kind === "edit") && typeof loadMemLine === "function") setTimeout(loadMemLine, 400);   // a new take may hold a new memory line
  if (RW && getSet().rewards !== "off") {           // show Ellie *with* the sound, using a quick estimate; real numbers fill in a moment later
    const est = Object.assign({}, RW), st = {approve: "approved", take: "takes", answer: "reflections"}[kind];
    if (st) est[st] = (est[st] || 0) + 1; if (kind === "approve") est.approved_week = (est.approved_week || 0) + 1;
    nudge([kind], est, null);
  }
  playChime();
  pendT = setTimeout(() => { const k = pend; pend = []; pendT = null; refreshRewards(k); }, 300);
}
window.rewardsTick = rewardsTick; window.fillCrew = fillCrew; window.fillCrewRow = fillCrewRow;
document.querySelectorAll('[data-set="chime"] button').forEach(b => b.addEventListener("click", () => playChime(b.dataset.v)));
window.partyPopper = partyPopper; window.fireworks = fireworks;
try { if (!localStorage.getItem("mytutor-chime-v2")) { saveSet("chime", "kalimba"); localStorage.setItem("mytutor-chime-v2", "1"); } } catch (e) {}
const tr = document.getElementById("s-rwtest"); if (tr) tr.onclick = () => celebrate({art: charSVG("fox", 2, 150), kicker: "Preview", title: "This is a level-up", text: "Pop-ups like this appear when a crew member joins or grows, or you earn a badge."});
refreshRewards();

/* ---------- move break: after N minutes at the laptop, Ellie asks you to stand up and walk for 2 minutes ---------- */
const MB = {start: Date.now(), last: Date.now(), snoozeTo: 0, shown: false};
function mbMinutes() { const v = getSet().movebreak; return v === "off" ? 0 : +(v || 30); }
function mbCount(add) {
  const k = "mytutor-breaks-" + new Date().toLocaleDateString("en-CA");
  let n = 0; try { n = +localStorage.getItem(k) || 0; if (add) localStorage.setItem(k, n += add); } catch (e) {} return n;
}
function mbReset() { MB.start = Date.now(); MB.snoozeTo = 0; MB.shown = false; }
function mbTick() {
  const now = Date.now(), mins = mbMinutes();
  if (now - MB.last > 10 * 60e3) mbReset();          // laptop asleep or away 10+ min: that already counts as a break
  MB.last = now;
  if (!mins || MB.shown || now < MB.snoozeTo || now - MB.start < mins * 60e3) return;
  MB.shown = true; mbAsk(Math.round((now - MB.start) / 60e3));
}
function mbAsk(sat) {
  playChime("kalimba-short");
  if (document.hidden && "Notification" in window && Notification.permission === "granted") {
    try { new Notification("myTutor · time to move 🚶", {body: `You've been sitting about ${sat} minutes. Stand up and walk for 2 minutes.`, icon: "/static/logo64.png"}); } catch (e) {}
  }
  const m = document.createElement("div"); m.className = "reward-modal mb-modal";
  m.innerHTML = `<div class="rw-card"><div class="rw-art m-walk">${ellie("", 140)}</div><div class="rw-kicker">🚶 Move break</div>
    <h2>Time to stand up!</h2><p>You've been sitting for about ${sat} minutes. A 2-minute walk refreshes your focus. Your notes will wait.</p>
    <div class="mb-btns"><button class="b ok" data-a="go">Start 2-min walk</button><button class="b" data-a="snooze">In 5 min</button><button class="b" data-a="skip">Skip</button></div></div>`;
  document.body.appendChild(m);
  m.onclick = e => { const a = e.target.closest("[data-a]"); if (!a) return;
    if (a.dataset.a === "go") return mbWalk(m);
    m.remove(); if (a.dataset.a === "snooze") { MB.shown = false; MB.snoozeTo = Date.now() + 5 * 60e3; } else mbReset(); };
}
function mbWalk(m) {
  let left = 120; const card = m.querySelector(".rw-card");
  card.innerHTML = `<div class="rw-art m-walk">${ellie("", 140)}</div><div class="rw-kicker">🚶 Walking with Ellie</div><div class="mb-clock">2:00</div>
    <div class="cbar mb-bar"><i></i></div><p>Stretch, get some water, look out of the window.</p><button class="b" data-a="done">I'm back</button>`;
  const clock = card.querySelector(".mb-clock"), bar = card.querySelector(".mb-bar i");
  const finish = () => { clearInterval(t); mbReset(); const n = mbCount(1);
    card.innerHTML = `<div class="rw-art m-jump">${ellie("party", 140)}</div><div class="rw-kicker">💪 Welcome back</div><h2>Break done!</h2>
      <p>${n} move break${n > 1 ? "s" : ""} today. Fresh mind, better takes.</p><button class="b ok" data-a="close">Back to learning</button>`;
    playChime("kalimba-short"); fillBreaks(); };
  const t = setInterval(() => { left--; clock.textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`; bar.style.width = ((120 - left) / 120 * 100) + "%"; if (left <= 0) finish(); }, 1000);
  m.onclick = e => { const a = e.target.closest("[data-a]"); if (!a) return; if (a.dataset.a === "done") finish(); else if (a.dataset.a === "close") m.remove(); };
}
function fillBreaks() { const el = document.getElementById("td-breaks"); if (!el) return; const n = mbCount(0), mins = mbMinutes();
  el.textContent = mins ? `🚶 ${n} move break${n === 1 ? "" : "s"} today · next in ${Math.max(0, Math.ceil((MB.start + mins * 60e3 - Date.now()) / 60e3))} min` : ""; }
setInterval(() => { mbTick(); fillBreaks(); }, 20e3);
document.querySelectorAll('[data-set="movebreak"] button').forEach(b => b.addEventListener("click", () => {
  mbReset(); fillBreaks(); if (b.dataset.v !== "off" && "Notification" in window && Notification.permission === "default") Notification.requestPermission().catch(() => {}); }));
const mbt = document.getElementById("s-mbtest"); if (mbt) mbt.onclick = () => { document.getElementById("settings").hidden = true; mbAsk(mbMinutes() || 30); };
fillBreaks();

/* ---------- stretch goal: asked, never automatic ---------- */
function weekId() { const d = new Date(), t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate())); const day = t.getUTCDay() || 7; t.setUTCDate(t.getUTCDate() + 4 - day);
  const y0 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1)); return t.getUTCFullYear() + "-W" + String(Math.ceil(((t - y0) / 864e5 + 1) / 7)).padStart(2, "0"); }
// Stretch: offers the next three targets above your current count (e.g. at 48 → 50, 55, 60).
// "Not now" pauses the question until you are 10 notes further; tapping the header ring always asks.
function stretchSnoozed(done) {
  try { const v = localStorage.getItem("mytutor-nostretch-" + weekId()); if (!v) return false;
        return v === "1" ? done < 0 : done < +v + 10; } catch (e) { return false; }
}
function askStretch(force) {
  const tgt = weeklyTarget(), done = (RW && RW.approved_week) || (S.stats && S.stats.approved_week) || 0;
  if (force !== true && (done < tgt || stretchSnoozed(done))) return;
  if (document.querySelector(".stretch-ask")) return;
  let n1 = tgt + 5; while (n1 <= done) n1 += 5;
  const opts = [n1, n1 + 5, n1 + 10];
  const m = document.createElement("div"); m.className = "reward-modal stretch-ask";
  m.innerHTML = `<div class="rw-card"><div class="rw-art m-wave">${ellie("champion", 120)}</div><div class="rw-kicker">🎯 ${done >= tgt ? "Target reached" : "Stretch target"}</div>
    <h2>Stretch this week?</h2><p>${done > tgt ? `You're at <b>${done}</b>, past your target of ${tgt}.` : done === tgt ? `You reached your target of ${tgt}.` : `You're at ${done} of ${tgt}.`} Pick a new target for this week. It's optional, and next week starts again at your normal goal (${weeklyGoal()}).</p>
    <div class="mb-btns st-opts">${opts.map((n, k) => `<button class="b${k ? "" : " ok"}" data-s="${n}">${n}</button>`).join("")}</div>
    <div class="mb-btns"><button class="b" data-s="no">Not now</button></div></div>`;
  document.body.appendChild(m);
  m.onclick = async e => { if (e.target === m) { m.remove(); return; } const b = e.target.closest("[data-s]"); if (!b) return; m.remove();
    if (b.dataset.s !== "no") { try { const r = await api("/api/stretch", {step: +b.dataset.s - tgt}); S.weekly_extra = r.weekly_extra; renderProg(); toast(`🎯 New target: ${weeklyTarget()} this week`); } catch (err) { toast(err.message); } }
    else { try { localStorage.setItem("mytutor-nostretch-" + weekId(), String(done)); } catch (err) {} toast(`👍 OK. I'll ask again at ${done + 10}, or tap the weekly ring any time`); } };
}
window.askStretch = askStretch;
