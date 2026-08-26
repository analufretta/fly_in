/*
  SCAFFOLD (pseudocode only). Runs in the BROWSER, not Python.
  Reads the JSON payload from <script id="run-data">, draws the network into
  <svg id="stage">, then animates drones turn by turn.

  Payload shape (from visualizer.build_timeline):
    zones: [{name,x,y,color,max_drones,type,is_start,is_end}]
    edges: [{a,b,capacity}]
    turns: [ { "<drone_id>": {kind:"zone",zone} | {kind:"edge",src,dst} } ]
    nb_drones: int
*/

// ------------------------------------------------------------------ //
// 0. Load data                                                        //
// ------------------------------------------------------------------ //
// PSEUDOCODE: DATA = JSON.parse(text of #run-data)

// ------------------------------------------------------------------ //
// 1. Coordinate transform (map grid -> SVG pixels)                    //
// ------------------------------------------------------------------ //
// PSEUDOCODE:
//   scan all zones -> minX,maxX,minY,maxY
//   scale grid units to canvas + padding
//   project(x, y):
//       px = pad + (x - minX) * spacing
//       py = pad + (maxY - y) * spacing   // FLIP: SVG y grows downward
//       return {px, py}

// ------------------------------------------------------------------ //
// 2. Build static scene (once)                                        //
// ------------------------------------------------------------------ //
// PSEUDOCODE:
//   for each edge: draw <line> between project(a) and project(b);
//                  optional label = capacity
//   for each zone: draw <circle> at project(zone) filled with zone.color
//                  (fallback color if name unknown/None);
//                  outline start/end differently;
//                  label = name (+ "occupied/max_drones" updated per turn)
//   keep a name -> pixel lookup for drone placement

// ------------------------------------------------------------------ //
// 3. Drone sprites                                                    //
// ------------------------------------------------------------------ //
// PSEUDOCODE:
//   create one <circle> (or dot) per drone id, initially at start zone
//   overlap fan-out: when many drones share a zone, offset each by index
//     around a small ring so they don't stack on one point

// ------------------------------------------------------------------ //
// 4. Placement for a given turn                                       //
// ------------------------------------------------------------------ //
// PSEUDOCODE:
//   positionFor(pos):
//       if pos.kind == "zone": return project(zone)
//       if pos.kind == "edge": return midpoint(project(src), project(dst))
//   renderTurn(t):
//       for each drone id in DATA.turns[t]:
//           target = positionFor(pos) + fan-out offset
//           move sprite to target (CSS transition OR lerp animates it)
//       update per-zone occupancy labels + highlight over-capacity zones
//       update turn counter + slider value

// ------------------------------------------------------------------ //
// 5. Animation loop + controls                                        //
// ------------------------------------------------------------------ //
// PSEUDOCODE:
//   state: currentTurn, playing, speed
//   play():   requestAnimationFrame loop, advance currentTurn on interval,
//             call renderTurn; stop at last turn
//   pause():  cancel loop
//   step(+/-1): renderTurn(currentTurn +/- 1), clamp to [0, lastTurn]
//   slider oninput: currentTurn = slider.value; renderTurn(currentTurn)
//   wire buttons -> play/pause/step
//
// NOTE: requestAnimationFrame is a browser API (no Python equivalent).
//   Alternative simpler loop = setInterval; smoother = rAF + lerp.
