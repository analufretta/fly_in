/*
  Runs in the BROWSER. Reads the JSON payload from
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
// 0. Load data                                                       //
// ------------------------------------------------------------------ //
const rawData = document.getElementById("run-data").textContent;
const DATA = JSON.parse(rawData);

const nbTurns = DATA.turns.length - 1;  // turns[0] is the seed frame, so -1
document.getElementById("summary").textContent =
  `${DATA.nb_drones} drones · ${DATA.zones.length} zones · ${nbTurns} turns`;

/* These constants define the drawing box and how big things are drawn. */
const VIEW_H = 540;
const PAD = 60;
const NODE_R = 18;
const DRONE_R = 12;

const xs = DATA.zones.map((z) => z.x);
const ys = DATA.zones.map((z) => z.y);

const minX = Math.min(...xs);
const maxX = Math.max(...xs);
const minY = Math.min(...ys);
const maxY = Math.max(...ys);

/* when every zone shares one column (span 0) -> use 1 instead. */
const spanX = maxX - minX || 1;
const spanY = maxY - minY || 1;

const VIEW_W = Math.max(480, PAD * 2 + (VIEW_H - PAD * 2) * (spanX / spanY));

/* Map a grid (x, y) to svg pixels, flipping y (grid up = screen up). */
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
// viewBox = "the coordinate system inside the svg": 0..VIEW_W by 0..VIEW_H.
// The CSS width/height then scales that box to fit the screen.
stage.setAttribute("viewBox", `0 0 ${VIEW_W} ${VIEW_H}`);

/* Create an SVG element with the given attributes. */
function svgEl(tag, attrs) {
  const el = document.createElementNS(SVGNS, tag);
  for (const key in attrs) {
    el.setAttribute(key, attrs[key]);
  }
  return el;
}

const zonePos = {};
const zoneMeta = {};
const zoneCircle = {};
const zoneOcc = {};

for (const z of DATA.zones) {
  zonePos[z.name] = project(z.x, z.y);
  zoneMeta[z.name] = z;
}

for (const e of DATA.edges) {
  const a = zonePos[e.a];
  const b = zonePos[e.b];
  // Example : <line x1=... y1=... x2=... y2=... class="edge" />
  stage.appendChild(svgEl("line", {
    x1: a.px, y1: a.py, x2: b.px, y2: b.py, class: "edge",
  }));
  
  const mid = { px: (a.px + b.px) / 2, py: (a.py + b.py) / 2 };
  const label = svgEl("text", {
    x: mid.px, y: mid.py - 4, class: "edge-label", "text-anchor": "middle",
  });
  label.textContent = String(e.capacity);
  stage.appendChild(label);
  // Exmaple: <text x="240" y="266" class="edge-label" text-anchor="middle">3</text>
}

for (const z of DATA.zones) {
  const p = zonePos[z.name];
  let cls = "zone";
  if (z.is_start) cls += "zone--start";
  else if (z.is_end) cls += "zone--end";
  const circle = svgEl("circle", {
    cx: p.px, cy: p.py, r: NODE_R, class: cls, fill: z.color || "#b0b8c4",
  });
  stage.appendChild(circle);
  zoneCircle[z.name] = circle;
  // Example: <circle cx=... cy=... class="zone zone--start" fill="red"/>

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
// Each drone is a <g> (group) holding a circle + its id text, so moving
// the group moves both at once. Local coords: children sit at (0,0), and
// we translate the whole group to the target each turn.
const droneEls = [];
for (let i = 0; i < DATA.nb_drones; i++) {
  const group = svgEl("g", { class: "drone" });
  group.appendChild(svgEl("circle", { r: DRONE_R }));
  const tag = svgEl("text", { class: "drone-label" });
  tag.textContent = `D${i + 1}`;
  group.appendChild(tag);
  stage.appendChild(group);
  droneEls.push(group);
}

// ------------------------------------------------------------------ //
// 4. Placement for a given turn                                       //
// ------------------------------------------------------------------ //
/** Pixel target for a drone position (zone center, or edge midpoint). */
function positionFor(pos) {
  if (pos.kind === "zone") {
    return zonePos[pos.zone];
  }
  // In-flight
  const a = zonePos[pos.src];
  const b = zonePos[pos.dst];
  return { px: (a.px + b.px) / 2, py: (a.py + b.py) / 2 };
}

/* Spread drones sharing one point around a small ring so they don't stack. */
function fanOut(base, index, count) {
  if (count <= 1) {
    return base;
  }
  // Place drone #index evenly around a circle (2*PI radians = full turn).
  const angle = (2 * Math.PI * index) / count;
  const ring = NODE_R + DRONE_R;
  return {
    px: base.px + Math.cos(angle) * ring,
    py: base.py + Math.sin(angle) * ring,
  };
}

/* Draw one frame: move every drone, refresh occupancy + the turn labels. */
function renderTurn(t) {
  const frame = DATA.turns[t];
  const bases = frame.map(positionFor);
  const groups = {};
  bases.forEach((b, i) => {   // forEach gives (value, index)
    const key = `${Math.round(b.px)},${Math.round(b.py)}`;   // "px,py" string key
    // ||= : if groups[key] is missing, set it to []; then push i.
    (groups[key] ||= []).push(i);
  });

  frame.forEach((pos, i) => {
    const key = `${Math.round(bases[i].px)},${Math.round(bases[i].py)}`;
    const members = groups[key];   // all drone indices sharing this pixel
    // members.indexOf(i) = this drone's slot within the shared group.
    const target = fanOut(bases[i], members.indexOf(i), members.length);
    // Move the whole group; CSS transitions the transform -> it glides.
    droneEls[i].setAttribute("transform", `translate(${target.px} ${target.py})`);
  });

  // Occupancy per zone (in-flight drones count for neither endpoint).
  const occ = {};
  for (const pos of frame) {
    if (pos.kind === "zone") {
      occ[pos.zone] = (occ[pos.zone] || 0) + 1;   // tally per zone name
    }
  }
  for (const z of DATA.zones) {
    const count = occ[z.name] || 0;
    const unlimited = z.is_start || z.is_end;   // start/end have no cap
    // Unlimited zones show a plain count; capped zones show count/max.
    zoneOcc[z.name].textContent =
      unlimited ? String(count) : `${count}/${z.max_drones}`;
    const over = !unlimited && count > z.max_drones;
    // classList.toggle(name, cond): add the class if cond is true, else remove.
    zoneCircle[z.name].classList.toggle("zone--over-capacity", over);
  }

  currentTurn = t;   // remember where we are (used by play/step)
  document.getElementById("scrub").value = String(t);   // sync the slider
  document.getElementById("turn-label").textContent = `turn ${t} / ${nbTurns}`;
}

// ------------------------------------------------------------------ //
// 5. Animation loop + controls                                        //
// ------------------------------------------------------------------ //
const STEP_MS = 700;     // time each turn is shown while playing (ms)
let currentTurn = 0;     // let, not const: it changes as we step
let timer = null;        // holds the setInterval id while playing, else null

const playBtn = document.getElementById("play");
const scrub = document.getElementById("scrub");
scrub.max = String(nbTurns);   // slider's right end = last turn

/** Clamp to [0, nbTurns] and draw. */
function goTo(t) {
  // Math.max(0, Math.min(nbTurns, t)) keeps t inside [0, nbTurns].
  renderTurn(Math.max(0, Math.min(nbTurns, t)));
}

function pause() {
  if (timer !== null) {         // only if actually playing
    clearInterval(timer);       // stop the repeating callback
    timer = null;               // mark "not playing"
  }
  playBtn.textContent = "▶ Play";
}

function play() {
  if (currentTurn >= nbTurns) {
    goTo(0);  // restart from the beginning if parked at the end
  }
  playBtn.textContent = "⏸ Pause";
  // setInterval runs the callback every STEP_MS ms; returns an id to cancel.
  timer = setInterval(() => {
    if (currentTurn >= nbTurns) {
      pause();      // reached the end -> stop the loop
      return;
    }
    goTo(currentTurn + 1);   // advance one turn
  }, STEP_MS);
}

function togglePlay() {
  if (timer === null) {   // null means paused -> start
    play();
  } else {
    pause();
  }
}

// addEventListener("click", fn): run fn whenever the element is clicked.
playBtn.addEventListener("click", togglePlay);
document.getElementById("back").addEventListener("click", () => {
  pause();               // stepping manually stops autoplay
  goTo(currentTurn - 1);
});
document.getElementById("fwd").addEventListener("click", () => {
  pause();
  goTo(currentTurn + 1);
});
// "input" fires continuously as the slider is dragged.
scrub.addEventListener("input", () => {
  pause();
  goTo(Number(scrub.value));   // slider value is a string -> Number()
});

goTo(0);  // initial frame: all drones at the start hub
