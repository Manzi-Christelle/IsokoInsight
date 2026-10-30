"use strict";
/* Draws Rwanda's districts as an SVG map. Shared by the weather and market price maps.
   The existing district maps keep their own drawing code and are not changed by this file.
   fillOf(name) returns a colour; titleOf(name) returns the tooltip and screen-reader text;
   onPick(name) runs when a district is clicked or activated with the keyboard. */
function drawDistrictMap(geo, fillOf, titleOf, onPick, selectedName) {
  const NS = "http://www.w3.org/2000/svg";
  const polys = (f) => (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates);
  const pts = geo.features.flatMap((f) => polys(f).flatMap((poly) => poly.flat()));
  const minX = Math.min(...pts.map((p) => p[0])), maxX = Math.max(...pts.map((p) => p[0]));
  const minY = Math.min(...pts.map((p) => p[1])), maxY = Math.max(...pts.map((p) => p[1]));
  const kx = Math.cos((((minY + maxY) / 2) * Math.PI) / 180);
  const W = (maxX - minX) * kx, H = maxY - minY, pad = 0.02 * Math.max(W, H);
  const project = ([lon, lat]) => [(lon - minX) * kx + pad, maxY - lat + pad];
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W + 2 * pad} ${H + 2 * pad}`);
  geo.features.forEach((f) => {
    const name = f.properties.name;
    const d = polys(f).map((poly) => poly.map((ring) =>
      "M" + ring.map((c) => project(c).map((v) => v.toFixed(4)).join(" ")).join("L") + "Z").join("")).join("");
    const p = document.createElementNS(NS, "path");
    p.setAttribute("d", d);
    p.setAttribute("class", "district" + (name === selectedName ? " selected" : ""));
    p.setAttribute("fill", fillOf(name));
    p.setAttribute("tabindex", "0");
    p.setAttribute("role", "button");
    p.setAttribute("aria-label", titleOf(name));
    p.dataset.name = name;
    const t = document.createElementNS(NS, "title");
    t.textContent = titleOf(name);
    p.append(t);
    p.addEventListener("click", () => onPick(name));
    p.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPick(name); } });
    svg.append(p);
  });
  return svg;
}
