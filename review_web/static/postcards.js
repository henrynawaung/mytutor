/* myTutor: LinkedIn post images drawn on your laptop (no outside service).
   titleCard(card) -> 1200x627 canvas (headline + topic illustration + name)
   endingCard(card) -> 1080x1350 canvas (key points as steps, takeaway, closing question, name)
   card = {headline, points:[{label,line}], takeaway, question, topic} */
const PC_NAME = "Henry N. Aung";
const PC_FONT = '"Segoe UI", Inter, Arial, sans-serif';
const PC_ICONS = {
  risk: "M12 3l7 3v5c0 5-3.5 8.5-7 10-3.5-1.5-7-5-7-10V6z M9 12l2 2 4-4",
  people: "M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6 M17 11a2.5 2.5 0 1 0 0-5 M21 20c0-2.6-1.6-4.8-4-5.6",
  growth: "M3 17l6-6 4 4 8-8 M15 7h6v6",
  strategy: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M12 12l7-7",
  data: "M4 20V10 M10 20V4 M16 20v-7 M22 20H2",
  innovation: "M9 18h6 M10 21h4 M12 3a6 6 0 0 0-4 10.5c.8.8 1 1.5 1 2.5h6c0-1 .2-1.7 1-2.5A6 6 0 0 0 12 3z",
  health: "M20.8 6.6a5 5 0 0 0-8.8-2 5 5 0 0 0-8.8 2C2 10 5 13.5 12 20c7-6.5 10-10 8.8-13.4z M3 12h4l2-3 3 6 2-3h7",
  leadership: "M5 21V4 M5 4h11l-2 4 2 4H5",
  change: "M21 12a9 9 0 0 1-15.5 6.3L3 16 M3 12A9 9 0 0 1 18.5 5.7L21 8 M21 3v5h-5 M3 21v-5h5",
  time: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 7v5l3 2",
};
const PC_STEP_ICONS = ["strategy", "people", "data", "innovation"];

function pcAccent() {
  const v = getComputedStyle(document.documentElement).getPropertyValue("--brand").trim();
  return /^#[0-9a-f]{6}$/i.test(v) ? v : "#2f6fde";
}
function pcTint(hex, a) { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`; }
function pcWrap(ctx, text, maxW, maxLines) {
  const words = String(text || "").split(/\s+/).filter(Boolean), lines = [];
  let line = "";
  for (const w of words) {
    const t = line ? line + " " + w : w;
    if (ctx.measureText(t).width > maxW && line) { lines.push(line); line = w; } else line = t;
  }
  if (line) lines.push(line);
  if (lines.length > maxLines) { lines.length = maxLines; lines[maxLines - 1] = lines[maxLines - 1].replace(/\s*\S*$/, "") + "…"; }
  return lines;
}
function pcFit(ctx, text, maxW, maxLines, start, min, weight) {   // biggest font size that fits
  for (let s = start; s >= min; s -= 2) { ctx.font = `${weight} ${s}px ${PC_FONT}`; const l = pcWrap(ctx, text, maxW, 99); if (l.length <= maxLines) return {size: s, lines: l}; }
  ctx.font = `${weight} ${min}px ${PC_FONT}`; return {size: min, lines: pcWrap(ctx, text, maxW, maxLines)};
}
function pcIcon(ctx, name, x, y, size, color, width) {
  ctx.save(); ctx.translate(x, y); ctx.scale(size / 24, size / 24);
  ctx.strokeStyle = color; ctx.lineWidth = width * 24 / size; ctx.lineCap = ctx.lineJoin = "round";
  ctx.stroke(new Path2D(PC_ICONS[name] || PC_ICONS.leadership)); ctx.restore();
}
function pcRound(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.roundRect(x, y, w, h, r); }
function pcSign(ctx, x, y, accent) {
  ctx.fillStyle = accent; ctx.fillRect(x, y - 30, 56, 5);
  ctx.fillStyle = "#1f2633"; ctx.font = `600 28px ${PC_FONT}`; ctx.textBaseline = "alphabetic"; ctx.fillText(PC_NAME, x, y + 6);
}

function titleCard(card) {
  const W = 1200, H = 627, c = document.createElement("canvas"); c.width = W; c.height = H;
  const ctx = c.getContext("2d"), A = pcAccent();
  ctx.fillStyle = "#fbfaf7"; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = A; ctx.fillRect(0, 0, 12, H);
  // illustration: soft rings + topic icon
  ctx.fillStyle = pcTint(A, .07); ctx.beginPath(); ctx.arc(955, 300, 250, 0, 7); ctx.fill();
  ctx.fillStyle = pcTint(A, .12); ctx.beginPath(); ctx.arc(955, 300, 175, 0, 7); ctx.fill();
  ctx.fillStyle = "#fff"; ctx.beginPath(); ctx.arc(955, 300, 118, 0, 7); ctx.fill();
  pcIcon(ctx, card.topic, 955 - 72, 300 - 72, 144, A, 7);
  (card.points || []).slice(0, 4).forEach((p, i) => {            // small labelled dots around the ring
    const ang = -2.4 + i * 0.95, x = 955 + Math.cos(ang) * 215, y = 300 + Math.sin(ang) * 215;
    ctx.fillStyle = "#fff"; ctx.strokeStyle = pcTint(A, .5); ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x, y, 26, 0, 7); ctx.fill(); ctx.stroke();
    pcIcon(ctx, PC_STEP_ICONS[i % 4], x - 14, y - 14, 28, A, 3);
  });
  // text
  ctx.fillStyle = A; ctx.font = `700 22px ${PC_FONT}`; ctx.textBaseline = "top";
  ctx.fillText("LEADERSHIP INSIGHT", 72, 78);
  const h = pcFit(ctx, card.headline, 600, 4, 62, 40, 800);
  ctx.fillStyle = "#141a24"; ctx.font = `800 ${h.size}px ${PC_FONT}`;
  h.lines.forEach((l, i) => ctx.fillText(l, 72, 124 + i * h.size * 1.16));
  if (card.takeaway) {
    const y = 124 + h.lines.length * h.size * 1.16 + 22;
    ctx.fillStyle = "#4a5568"; ctx.font = `400 26px ${PC_FONT}`;
    pcWrap(ctx, card.takeaway, 600, 2).forEach((l, i) => ctx.fillText(l, 72, y + i * 36));
  }
  pcSign(ctx, 72, H - 64, A);
  return c;
}

function endingCard(card) {
  const W = 1080, H = 1350, c = document.createElement("canvas"); c.width = W; c.height = H;
  const ctx = c.getContext("2d"), A = pcAccent(), X = 80, CW = W - 160;
  ctx.fillStyle = "#fbfaf7"; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = A; ctx.fillRect(0, 0, W, 12);
  ctx.textBaseline = "top"; ctx.fillStyle = A; ctx.font = `700 24px ${PC_FONT}`; ctx.fillText("KEY TAKEAWAYS", X, 82);
  const h = pcFit(ctx, card.headline, CW, 3, 56, 38, 800);
  ctx.fillStyle = "#141a24"; ctx.font = `800 ${h.size}px ${PC_FONT}`;
  h.lines.forEach((l, i) => ctx.fillText(l, X, 124 + i * h.size * 1.15));
  let y = 124 + h.lines.length * h.size * 1.15 + 44;
  const pts = (card.points || []).slice(0, 4), gap = 20;
  ctx.font = `700 32px ${PC_FONT}`; const tkH = card.takeaway ? 44 + pcWrap(ctx, card.takeaway, CW - 80, 3).length * 42 + 30 : 0;
  ctx.font = `italic 500 30px ${PC_FONT}`; const qH = card.question ? pcWrap(ctx, card.question, CW, 2).length * 40 : 0;
  const room = H - 150 - y - 14 - tkH - qH;                       // keep clear of the signature at the bottom
  const boxH = Math.max(104, Math.min(160, Math.floor((room - gap * (pts.length - 1)) / Math.max(1, pts.length))));
  pts.forEach((p, i) => {
    ctx.fillStyle = "#fff"; ctx.strokeStyle = "#e6e2d8"; ctx.lineWidth = 2; pcRound(ctx, X, y, CW, boxH, 22); ctx.fill(); ctx.stroke();
    ctx.fillStyle = A; ctx.beginPath(); ctx.arc(X + 58, y + boxH / 2, 34, 0, 7); ctx.fill();
    ctx.fillStyle = "#fff"; ctx.font = `800 32px ${PC_FONT}`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(String(i + 1), X + 58, y + boxH / 2 + 1); ctx.textAlign = "left";
    pcIcon(ctx, PC_STEP_ICONS[i % 4], X + CW - 74, y + boxH / 2 - 22, 44, pcTint(A, .55), 2.4);
    ctx.textBaseline = "top"; ctx.fillStyle = "#141a24"; ctx.font = `700 34px ${PC_FONT}`;
    const tx = X + 118, tw = CW - 118 - 100;
    ctx.fillText(pcWrap(ctx, p.label, tw, 1)[0] || "", tx, y + boxH / 2 - 46);
    ctx.fillStyle = "#4a5568"; ctx.font = `400 26px ${PC_FONT}`;
    pcWrap(ctx, p.line, tw, 2).forEach((l, k) => ctx.fillText(l, tx, y + boxH / 2 - 2 + k * 32));
    y += boxH + gap;
  });
  y += 14;
  if (card.takeaway) {
    ctx.font = `700 32px ${PC_FONT}`; const tl = pcWrap(ctx, card.takeaway, CW - 80, 3), th = 44 + tl.length * 42;
    ctx.fillStyle = pcTint(A, .12); pcRound(ctx, X, y, CW, th, 22); ctx.fill();
    ctx.fillStyle = A; ctx.fillRect(X, y + 18, 6, th - 36);
    ctx.fillStyle = "#141a24"; tl.forEach((l, i) => ctx.fillText(l, X + 40, y + 22 + i * 42));
    y += th + 30;
  }
  if (card.question) {
    ctx.fillStyle = "#2b3442"; ctx.font = `italic 500 30px ${PC_FONT}`;
    pcWrap(ctx, card.question, CW, 2).forEach((l, i) => ctx.fillText(l, X, y + i * 40));
  }
  pcSign(ctx, X, H - 70, A);
  return c;
}

function downloadCanvas(canvas, name) {
  canvas.toBlob(b => { const a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = name;
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500); }, "image/png");
}
