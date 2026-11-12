/* Ellie the elephant: an original myTutor character. ellie(costume, size) -> SVG string.
   Parts are grouped (ears, trunk, head, body) so CSS motions can move them: .m-wave .m-jump .m-toot .m-dance */
function ellie(costume = "", size = 120) {
  const C = {skin: "#a9c3e3", dark: "#8aa9cf", light: "#c4d7ee", line: "#6f8db5", pink: "#f4b6c8"};
  const ear = s => `<g class="ear ear-${s}"><ellipse cx="${s === "l" ? 50 : 150}" cy="84" rx="30" ry="35" fill="${C.dark}"/><ellipse cx="${s === "l" ? 53 : 147}" cy="86" rx="19" ry="24" fill="${C.pink}"/></g>`;
  const costumes = {
    party: {head: `<g transform="rotate(16 116 44)"><path d="M100 50L117 6l17 44z" fill="#7c5ce0"/><path d="M104 39h26l2 6h-30zM108 27h18l2 5h-22zM112 16h10l1.6 5h-13z" fill="#ffd34d"/><circle cx="117" cy="6" r="7" fill="#ff6b9a"/><path d="M97 50q20 8 40 0" stroke="#ff6b9a" stroke-width="5" fill="none" stroke-linecap="round"/></g>`,},
    graduate: {head: `<path d="M64 46l36-16 36 16-36 16z" fill="#2b2f3a"/><path d="M78 52v12q22 10 44 0V52l-22 10z" fill="#3a404e"/><path d="M100 46l30 6v18" stroke="#ffd34d" stroke-width="2.5" fill="none"/><circle cx="130" cy="72" r="4" fill="#ffd34d"/>`,
      body: `<rect x="142" y="134" width="20" height="26" rx="3" fill="#f8f3e6" transform="rotate(15 152 147)"/><path d="M144 141h14" stroke="#c92a2a" stroke-width="3" transform="rotate(15 152 147)"/>`},
    boss: {face: `<g fill="none" stroke="#1d1d2b" stroke-width="3"><circle cx="82" cy="82" r="11"/><circle cx="118" cy="82" r="11"/><path d="M93 82h14M71 80l-10-4M129 80l10-4"/></g>`,
      body: `<path d="M88 124h24l-6 6 4 26-10 8-10-8 4-26z" fill="#c92a2a"/><path d="M88 124h24l-6 6h-12z" fill="#a51d1d"/><rect x="134" y="138" width="26" height="20" rx="3" fill="#5a3e2b"/><path d="M142 138v-4h10v4" stroke="#5a3e2b" stroke-width="3" fill="none"/>`},
    champion: {back: `<path d="M64 124q36-10 72 0l14 58H50z" fill="#c92a2a"/>`,
      head: `<path d="M72 48l8 12 20-24 20 24 8-12 2 22H70z" fill="#ffd34d" stroke="#e8a400" stroke-width="2"/><circle cx="100" cy="36" r="4" fill="#ff6b9a"/><circle cx="72" cy="48" r="3" fill="#4dabf7"/><circle cx="128" cy="48" r="3" fill="#4dabf7"/>`,
      body: `<circle cx="100" cy="140" r="9" fill="#ffd34d" stroke="#e8a400" stroke-width="2"/><path d="M96 131l-4-8M104 131l4-8" stroke="#4dabf7" stroke-width="4"/>`},
  };
  const k = costumes[costume] || {};
  return `<svg class="ellie" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="${size}" height="${size}" aria-hidden="true">
  <ellipse class="shadow" cx="100" cy="190" rx="48" ry="7" fill="#000" opacity=".15"/>
  <g class="whole">
   ${k.back || ""}
   <g class="bodyg">
    <rect x="70" y="150" width="24" height="36" rx="11" fill="${C.skin}"/><rect x="106" y="150" width="24" height="36" rx="11" fill="${C.skin}"/>
    <path d="M74 182q4-3 8 0M84 182q4-3 8 0M110 182q4-3 8 0M120 182q4-3 8 0" stroke="${C.light}" stroke-width="2.5" fill="none" stroke-linecap="round"/>
    <ellipse cx="100" cy="146" rx="40" ry="30" fill="${C.skin}"/><ellipse cx="100" cy="152" rx="24" ry="18" fill="${C.light}" opacity=".6"/>
    <g class="arm arm-l"><ellipse cx="62" cy="146" rx="10" ry="16" fill="${C.dark}" transform="rotate(20 62 146)"/></g>
    <g class="arm arm-r"><ellipse cx="138" cy="146" rx="10" ry="16" fill="${C.dark}" transform="rotate(-20 138 146)"/></g>
    ${k.body || ""}
   </g>
   <g class="headg">
    ${ear("l")}${ear("r")}
    <circle cx="100" cy="84" r="44" fill="${C.skin}"/><ellipse cx="96" cy="62" rx="24" ry="11" fill="${C.light}" opacity=".6"/>
    <circle cx="82" cy="82" r="7.5" fill="#1d1d2b"/><circle cx="84.6" cy="79" r="2.8" fill="#fff"/><circle cx="118" cy="82" r="7.5" fill="#1d1d2b"/><circle cx="120.6" cy="79" r="2.8" fill="#fff"/>
    <ellipse cx="70" cy="100" rx="8" ry="4.5" fill="#ff8fa3" opacity=".55"/><ellipse cx="130" cy="100" rx="8" ry="4.5" fill="#ff8fa3" opacity=".55"/>
    <path d="M114 108q5 5 10 0" stroke="#1d1d2b" stroke-width="2.6" fill="none" stroke-linecap="round"/>
    <g class="trunk">
     <path d="M100 94C100 112 102 124 110 130C118 136 128 132 128 124" stroke="${C.line}" stroke-width="19" fill="none" stroke-linecap="round"/>
     <path d="M100 94C100 112 102 124 110 130C118 136 128 132 128 124" stroke="${C.skin}" stroke-width="15" fill="none" stroke-linecap="round"/>
     <path d="M95 106h10M96 116h10M101 125l7-5" stroke="${C.line}" stroke-width="1.8" stroke-linecap="round" opacity=".6"/>
    </g>
    ${k.face || ""}${k.head || ""}
   </g>
  </g></svg>`;
}

