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

  JS note: two slashes start a line comment; slash-star ... star-slash is a
  block comment. const = a name that can't be reassigned; let = one that can.
*/

// ------------------------------------------------------------------ //
// 0. Load data                                                        //
// ------------------------------------------------------------------ //
// document = the whole page; getElementById finds one element by its id.
// .textContent = the raw text sitting inside that <script> tag (our JSON).
const rawData = document.getElementById("run-data").textContent;
// JSON.parse turns that JSON *string* into real JS objects/arrays.
const DATA = JSON.parse(rawData);

const nbTurns = DATA.turns.length - 1;  // turns[0] is the seed frame, so -1
// Backticks = a "template literal": ${...} splices a value into the string.
// The dots are literal middot characters, just decoration.
document.getElementById("summary").textContent =
  `${DATA.nb_drones} drones · ${DATA.zones.length} zones · ${nbTurns} turns`;

// ------------------------------------------------------------------ //
// 1. Coordinate transform (map grid -> SVG pixels)                    //
// ------------------------------------------------------------------ //
// The map gives grid coords (small ints); the SVG needs pixel coords.
// These constants define the drawing box and how big things are drawn.
const VIEW_H = 540;   // viewBox height (fixed); width derives from grid aspect
const PAD = 60;       // margin so nodes/labels never touch the edge
const NODE_R = 18;    // zone circle radius
const DRONE_R = 12;   // drone dot radius (big enough to hold its id label)

// .map((z) => z.x) = "make a new array of just the x of every zone".
// (z) => z.x is an arrow function (a short inline function).
const xs = DATA.zones.map((z) => z.x);
const ys = DATA.zones.map((z) => z.y);
// Math.min(...xs): the ... "spreads" the array into separate arguments,
// so Math.min(...[2,5,9]) becomes Math.min(2, 5, 9).
const minX = Math.min(...xs);
const maxX = Math.max(...xs);
const minY = Math.min(...ys);
const maxY = Math.max(...ys);
// a || b = "a, unless a is falsy (here 0), then b". Guards divide-by-zero
// when every zone shares one column (span 0) -> use 1 instead.
const spanX = maxX - minX || 1;
const spanY = maxY - minY || 1;

// Width tracks the grid aspect so px-per-unit is equal on both axes: a
// wide/flat map gets a wide canvas instead of cramming columns together.
// Math.max(480, ...) stops tiny maps from getting a too-narrow canvas.
const VIEW_W = Math.max(480, PAD * 2 + (VIEW_H - PAD * 2) * (spanX / spanY));

/** Map a grid (x, y) to svg pixels, flipping y (grid up = screen up). */
function project(x, y) {
  // (x - minX) / spanX = where x sits from 0..1 across the grid width;
  // times the usable pixel width, plus the left pad = the pixel x.
  const px = PAD + ((x - minX) / spanX) * (VIEW_W - 2 * PAD);
  // (maxY - y) flips: biggest grid-y maps to the TOP (small pixel-y),
  // because in SVG y grows downward but on a map "up" should be up.
  const py = PAD + ((maxY - y) / spanY) * (VIEW_H - 2 * PAD);
  return { px, py };   // return both as one object
}

// ------------------------------------------------------------------ //
// 2. Build static scene (once)                                        //
// ------------------------------------------------------------------ //
// SVG elements live in their own XML "namespace"; you must create them
// with createElementNS + this URL, or the browser won't treat them as SVG.
const SVGNS = "http://www.w3.org/2000/svg";
const stage = document.getElementById("stage");
// viewBox = "the coordinate system inside the svg": 0..VIEW_W by 0..VIEW_H.
// The CSS width/height then scales that box to fit the screen.
stage.setAttribute("viewBox", `0 0 ${VIEW_W} ${VIEW_H}`);

/** Create an SVG element with the given attributes. */
function svgEl(tag, attrs) {
  const el = document.createElementNS(SVGNS, tag);
  // for..in walks the KEYS of the attrs object; set each as an attribute.
  for (const key in attrs) {
    el.setAttribute(key, attrs[key]);
  }
  return el;
}

// Plain objects used as lookup tables (name -> something).
const zonePix = {};     // name -> {px, py}
const zoneMeta = {};    // name -> zone payload
const zoneCircle = {};  // name -> <circle> element
const zoneOcc = {};     // name -> occupancy <text> element

// First pass: precompute every zone's pixel spot and stash its data.
for (const z of DATA.zones) {   // for..of walks the VALUES of an array
  zonePix[z.name] = project(z.x, z.y);
  zoneMeta[z.name] = z;
}

// Edges first so zones/drones paint on top of the lines.
// (SVG has no z-index: draw order = stacking order, later = on top.)
for (const e of DATA.edges) {
  const a = zonePix[e.a];   // pixel spot of endpoint a
  const b = zonePix[e.b];
  // appendChild inserts the new element into the live SVG (it now shows).
  stage.appendChild(svgEl("line", {
    x1: a.px, y1: a.py, x2: b.px, y2: b.py, class: "edge",
  }));
  const mid = { px: (a.px + b.px) / 2, py: (a.py + b.py) / 2 };  // line middle
  const label = svgEl("text", {
    x: mid.px, y: mid.py - 4, class: "edge-label", "text-anchor": "middle",
  });
  label.textContent = String(e.capacity);   // the number shown on the edge
  stage.appendChild(label);
}

// Zones on top of edges.
for (const z of DATA.zones) {
  const p = zonePix[z.name];
  // Build the class string: every zone gets "zone"; start/end add a modifier
  // so the CSS can ring them in white.
  let cls = "zone";
  if (z.is_start) cls += " zone--start";
  else if (z.is_end) cls += " zone--end";
  const circle = svgEl("circle", {
    // fill set inline because the colour comes from the MAP data, not a
    // fixed CSS rule; || "#888888" is a grey fallback if none was given.
    cx: p.px, cy: p.py, r: NODE_R, class: cls, fill: z.color || "#888888",
  });
  stage.appendChild(circle);
  zoneCircle[z.name] = circle;   // remember it so we can restyle it per turn

  // Name label, placed just ABOVE the circle.
  const name = svgEl("text", {
    x: p.px, y: p.py - NODE_R - 6, class: "zone-label",
  });
  name.textContent = z.name;
  stage.appendChild(name);

  // Occupancy label, placed just BELOW the circle. Empty for now;
  // renderTurn fills its text each frame. We keep the handle in zoneOcc.
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
const droneEls = [];  // one <g> per drone (circle + id label), moved as a unit
for (let i = 0; i < DATA.nb_drones; i++) {
  const group = svgEl("g", { class: "drone" });
  group.appendChild(svgEl("circle", { r: DRONE_R }));   // cx/cy default to 0
  const tag = svgEl("text", { class: "drone-label" });
  tag.textContent = `D${i + 1}`;   // drone ids are 1-based
  group.appendChild(tag);
  stage.appendChild(group);
  droneEls.push(group);   // index i in this array == drone (i+1)
}

// ------------------------------------------------------------------ //
// 4. Placement for a given turn                                       //
// ------------------------------------------------------------------ //
/** Pixel target for a drone position (zone center, or edge midpoint). */
function positionFor(pos) {
  // pos.kind tells us which shape the JSON used: a zone, or an edge.
  if (pos.kind === "zone") {   // === is strict equality (no type coercion)
    return zonePix[pos.zone];
  }
  // In-flight: sit the drone at the midpoint of the src->dst edge.
  const a = zonePix[pos.src];
  const b = zonePix[pos.dst];
  return { px: (a.px + b.px) / 2, py: (a.py + b.py) / 2 };
}

/** Spread drones sharing one point around a small ring so they don't stack. */
function fanOut(base, index, count) {
  if (count <= 1) {
    return base;   // alone here -> no need to offset
  }
  // Place drone #index evenly around a circle (2*PI radians = full turn).
  const angle = (2 * Math.PI * index) / count;
  const ring = NODE_R + DRONE_R;   // radius of the fan-out ring
  // cos/sin give a point on that ring at the chosen angle.
  return {
    px: base.px + Math.cos(angle) * ring,
    py: base.py + Math.sin(angle) * ring,
  };
}

/** Draw one frame: move every drone, refresh occupancy + the turn labels. */
function renderTurn(t) {
  const frame = DATA.turns[t];   // array: frame[i] = where drone (i+1) is now

  // Group drone indices by the pixel they land on (for fan-out).
  const bases = frame.map(positionFor);   // each drone's un-fanned target
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
