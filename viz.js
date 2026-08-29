/*
  Runs in the BROWSER, not Python. Reads the JSON payload from
  <script id="run-data">, draws the network into <svg id="stage">, then
  animates the drones turn by turn.

  Payload shape (from visualizer._build_timeline):
    zones: [{name,x,y,color,max_drones,type,is_start,is_end}]
    edges: [{a,b,capacity}]
    turns: [ [ {kind:"zone",zone} | {kind:"edge",src,dst}, ... ], ... ]
            turns[t][i] = position of drone (i+1) on turn t; turns[0] = seed.
    nb_drones: int
*/

// ------------------------------------------------------------------ //
// 0. Load data                                                        //
// ------------------------------------------------------------------ //
const rawData = document.getElementById("run-data").textContent;
const DATA = JSON.parse(rawData);

const nbTurns = DATA.turns.length - 1;  // turns[0] is the seed frame
document.getElementById("summary").textContent =
  `${DATA.nb_drones} drones · ${DATA.zones.length} zones · ${nbTurns} turns`;

// ------------------------------------------------------------------ //
// 1. Coordinate transform (map grid -> SVG pixels)                    //
// ------------------------------------------------------------------ //
const VIEW_W = 900;   // viewBox width in svg units
const VIEW_H = 540;   // viewBox height
const PAD = 60;       // margin so nodes/labels never touch the edge
const NODE_R = 18;    // zone circle radius
const DRONE_R = 6;    // drone dot radius

const xs = DATA.zones.map((z) => z.x);
const ys = DATA.zones.map((z) => z.y);
const minX = Math.min(...xs);
const maxX = Math.max(...xs);
const minY = Math.min(...ys);
const maxY = Math.max(...ys);
const spanX = maxX - minX || 1;  // avoid /0 when all zones share a column
const spanY = maxY - minY || 1;

/** Map a grid (x, y) to svg pixels, flipping y (grid up = screen up). */
function project(x, y) {
  const px = PAD + ((x - minX) / spanX) * (VIEW_W - 2 * PAD);
  const py = PAD + ((maxY - y) / spanY) * (VIEW_H - 2 * PAD);
  return { px, py };
}

// ------------------------------------------------------------------ //
// 2. Build static scene (once)                                        //
// ------------------------------------------------------------------ //
const SVGNS = "http://www.w3.org/2000/svg";
const stage = document.getElementById("stage");
stage.setAttribute("viewBox", `0 0 ${VIEW_W} ${VIEW_H}`);

/** Create an SVG element with the given attributes. */
function svgEl(tag, attrs) {
  const el = document.createElementNS(SVGNS, tag);
  for (const key in attrs) {
    el.setAttribute(key, attrs[key]);
  }
  return el;
}

const zonePix = {};     // name -> {px, py}
const zoneMeta = {};    // name -> zone payload
const zoneCircle = {};  // name -> <circle> element
const zoneOcc = {};     // name -> occupancy <text> element

for (const z of DATA.zones) {
  zonePix[z.name] = project(z.x, z.y);
  zoneMeta[z.name] = z;
}

// Edges first so zones/drones paint on top of the lines.
for (const e of DATA.edges) {
  const a = zonePix[e.a];
  const b = zonePix[e.b];
  stage.appendChild(svgEl("line", {
    x1: a.px, y1: a.py, x2: b.px, y2: b.py, class: "edge",
  }));
  const mid = { px: (a.px + b.px) / 2, py: (a.py + b.py) / 2 };
  const label = svgEl("text", {
    x: mid.px, y: mid.py - 4, class: "edge-label", "text-anchor": "middle",
  });
  label.textContent = String(e.capacity);
  stage.appendChild(label);
}

// Zones on top of edges.
for (const z of DATA.zones) {
  const p = zonePix[z.name];
  let cls = "zone";
  if (z.is_start) cls += " zone--start";
  else if (z.is_end) cls += " zone--end";
  const circle = svgEl("circle", {
    cx: p.px, cy: p.py, r: NODE_R, class: cls, fill: z.color || "#888888",
  });
  stage.appendChild(circle);
  zoneCircle[z.name] = circle;

  const name = svgEl("text", {
    x: p.px, y: p.py - NODE_R - 6, class: "zone-label",
  });
  name.textContent = z.name;
  stage.appendChild(name);

  const occ = svgEl("text", {
    x: p.px, y: p.py + NODE_R + 14, class: "zone-label",
  });
  stage.appendChild(occ);
  zoneOcc[z.name] = occ;
}

// ------------------------------------------------------------------ //
// 3. Drone sprites                                                    //
// ------------------------------------------------------------------ //
const droneEls = [];
for (let i = 0; i < DATA.nb_drones; i++) {
  const dot = svgEl("circle", { r: DRONE_R, class: "drone" });
  stage.appendChild(dot);
  droneEls.push(dot);
}

// ------------------------------------------------------------------ //
// 4. Placement for a given turn                                       //
// ------------------------------------------------------------------ //
/** Pixel target for a drone position (zone center, or edge midpoint). */
function positionFor(pos) {
  if (pos.kind === "zone") {
    return zonePix[pos.zone];
  }
  const a = zonePix[pos.src];
  const b = zonePix[pos.dst];
  return { px: (a.px + b.px) / 2, py: (a.py + b.py) / 2 };
}

/** Spread drones sharing one point around a small ring so they don't stack. */
function fanOut(base, index, count) {
  if (count <= 1) {
    return base;
  }
  const angle = (2 * Math.PI * index) / count;
  const ring = NODE_R * 0.6;
  return {
    px: base.px + Math.cos(angle) * ring,
    py: base.py + Math.sin(angle) * ring,
  };
}

/** Draw one frame: move every drone, refresh occupancy + the turn labels. */
function renderTurn(t) {
  const frame = DATA.turns[t];

  // Group drone indices by the pixel they land on (for fan-out).
  const bases = frame.map(positionFor);
  const groups = {};
  bases.forEach((b, i) => {
    const key = `${Math.round(b.px)},${Math.round(b.py)}`;
    (groups[key] ||= []).push(i);
  });

  frame.forEach((pos, i) => {
    const key = `${Math.round(bases[i].px)},${Math.round(bases[i].py)}`;
    const members = groups[key];
    const target = fanOut(bases[i], members.indexOf(i), members.length);
    droneEls[i].setAttribute("cx", target.px);
    droneEls[i].setAttribute("cy", target.py);
  });

  // Occupancy per zone (in-flight drones count for neither endpoint).
  const occ = {};
  for (const pos of frame) {
    if (pos.kind === "zone") {
      occ[pos.zone] = (occ[pos.zone] || 0) + 1;
    }
  }
  for (const z of DATA.zones) {
    const count = occ[z.name] || 0;
    const unlimited = z.is_start || z.is_end;
    zoneOcc[z.name].textContent =
      count === 0 ? "" : (unlimited ? String(count) : `${count}/${z.max_drones}`);
    const over = !unlimited && count > z.max_drones;
    zoneCircle[z.name].classList.toggle("zone--over-capacity", over);
  }

  currentTurn = t;
  document.getElementById("scrub").value = String(t);
  document.getElementById("turn-label").textContent = `turn ${t} / ${nbTurns}`;
}

// ------------------------------------------------------------------ //
// 5. Animation loop + controls                                        //
// ------------------------------------------------------------------ //
const STEP_MS = 700;     // time each turn is shown while playing
let currentTurn = 0;
let timer = null;

const playBtn = document.getElementById("play");
const scrub = document.getElementById("scrub");
scrub.max = String(nbTurns);

/** Clamp to [0, nbTurns] and draw. */
function goTo(t) {
  renderTurn(Math.max(0, Math.min(nbTurns, t)));
}

function pause() {
  if (timer !== null) {
    clearInterval(timer);
    timer = null;
  }
  playBtn.textContent = "▶ Play";
}

function play() {
  if (currentTurn >= nbTurns) {
    goTo(0);  // restart from the beginning if parked at the end
  }
  playBtn.textContent = "⏸ Pause";
  timer = setInterval(() => {
    if (currentTurn >= nbTurns) {
      pause();
      return;
    }
    goTo(currentTurn + 1);
  }, STEP_MS);
}

function togglePlay() {
  if (timer === null) {
    play();
  } else {
    pause();
  }
}

playBtn.addEventListener("click", togglePlay);
document.getElementById("back").addEventListener("click", () => {
  pause();
  goTo(currentTurn - 1);
});
document.getElementById("fwd").addEventListener("click", () => {
  pause();
  goTo(currentTurn + 1);
});
scrub.addEventListener("input", () => {
  pause();
  goTo(Number(scrub.value));
});

goTo(0);  // initial frame: all drones at the start hub
