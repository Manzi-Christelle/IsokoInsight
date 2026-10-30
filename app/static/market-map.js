"use strict";
/* Market prices tab: one product's verified prices compared across districts on a map.
   Green is the cheapest band and red the dearest. Prices are SYNTHETIC demo values and are labelled as such.
   Uses helpers from app.js ($, el, api, td, buildTable, products) and map-tools.js (drawDistrictMap). */
const MP = { geo: null, product: null, data: null, selected: null, seq: 0, ready: false };
const MP_BANDS = ["#1f6f4a", "#8cc9a0", "#f7e08a", "#f2a65a", "#b3261e"];
const MP_NODATA = "#d6d6d6";

async function mpLoad() {
  try {
    if (!MP.geo) MP.geo = await fetch("/static/data/rwanda_districts.geojson").then((r) => r.json());
    if (!MP.ready && products.length) {
      const sel = $("pmProduct"); sel.replaceChildren();
      products.forEach((p) => sel.append(el("option", { value: p.id, text: `${p.name} (${p.category}, per ${p.standard_unit})` })));
      const beef = products.find((p) => p.name === "Beef") || products[0];
      sel.value = beef.id; MP.product = beef.id; MP.ready = true;
    }
    if (MP.product) await mpRender();
  } catch (e) {
    $("pmMapBox").replaceChildren(el("p", { class: "err", text: "Could not load the price map: " + e.message }));
  }
}

async function mpRender() {
  const seq = ++MP.seq;
  try {
    const d = await api(`/api/prices/district-map?product_id=${MP.product}`);
    if (seq !== MP.seq) return;
    MP.data = d;
    if (MP.selected && !d.districts.find((x) => x.name === MP.selected && x.average_rwf !== null)) MP.selected = null;
    mpDrawLead(); mpDrawLegend(); mpDrawMap(); mpDrawTable(); mpDrawInfo();
  } catch (e) {
    if (seq === MP.seq) $("pmMapBox").replaceChildren(el("p", { class: "err", text: "Could not load this view: " + e.message }));
  }
}

function mpRow(name) { return MP.data ? MP.data.districts.find((d) => d.name === name) : null; }
function mpColour(row) {
  if (!row || row.band === null || row.band === undefined) return MP_NODATA;
  return MP_BANDS[row.band];
}

function mpDrawLead() {
  const d = MP.data;
  $("pmLead").textContent = `Average of the latest verified ${d.product} price at the markets in each district. `
    + `${d.districts_with_prices} of 30 districts have a verified price for this product.`
    + (d.cheapest_district && d.highest_district && d.spread_pct !== null
      ? ` The cheapest district is ${d.cheapest_district} and the dearest is ${d.highest_district}, a gap of ${d.spread_pct}%.` : "");
}

function mpDrawLegend() {
  const e = MP.data.band_edges_rwf;
  const items = MP_BANDS.map((c, i) => el("span", { class: "item" }, el("span", { class: "sw", style: `background:${c}` }),
    e.length ? `${Number(e[i]).toLocaleString()} to ${Number(e[i + 1]).toLocaleString()} RWF` : ""));
  $("pmLegend").replaceChildren(el("b", { text: "Average price: " }), ...items,
    el("span", { class: "item" }, el("span", { class: "sw", style: `background:${MP_NODATA}` }), "No verified price here"));
}

function mpDrawMap() {
  const svg = drawDistrictMap(MP.geo,
    (name) => mpColour(mpRow(name)),
    (name) => { const r = mpRow(name); return r && r.average_rwf !== null
      ? `${name}: average ${r.average_rwf.toLocaleString()} RWF (${r.markets_count} ${r.markets_count === 1 ? "market" : "markets"})`
      : `${name}: no verified price for this product`; },
    (name) => mpSelect(name), MP.selected);
  $("pmMapBox").replaceChildren(svg);
  $("pmNote").textContent = MP.data.note + (MP.data.contains_synthetic ? " DEMO DATA: these prices are synthetic demonstration values."
    : "") + (MP.data.as_of ? ` Latest verified price date: ${MP.data.as_of}.` : "");
}

function mpDrawTable() {
  const priced = MP.data.districts.filter((d) => d.average_rwf !== null).sort((a, b) => a.average_rwf - b.average_rwf);
  const rows = priced.map((r) => {
    const tr = el("tr", { class: "dist-row", "data-name": r.name, tabindex: "0" },
      td(r.name), td(r.markets.map((m) => m.market).join(", ")),
      td(r.average_rwf.toLocaleString() + " RWF", "num"),
      td(r.vs_cheapest_pct === null ? "n/a" : (r.vs_cheapest_pct > 0 ? "+" : "") + r.vs_cheapest_pct + "%", "num"),
      el("td", {}, el("span", { class: "chip", style: `background:${mpColour(r)};color:#111`,
        text: r.band === 0 ? "Cheapest band" : r.band === MP_BANDS.length - 1 ? "Dearest band" : "Middle band" })));
    tr.addEventListener("click", () => mpSelect(r.name));
    tr.addEventListener("keydown", (e) => { if (e.key === "Enter") mpSelect(r.name); });
    return tr;
  });
  const without = MP.data.districts.filter((d) => d.average_rwf === null).map((d) => d.name);
  $("pmTable").replaceChildren(
    buildTable([{ label: "District" }, { label: "Markets" }, { label: "Average (RWF)", num: true },
      { label: "Vs cheapest", num: true }, { label: "Band" }], rows),
    el("p", { class: "muted", text: without.length ? `No verified price for ${MP.data.product} yet in: ${without.join(", ")}.` : "" }));
}

function mpDrawInfo() {
  const box = $("pmInfo");
  const r = MP.selected ? mpRow(MP.selected) : null;
  if (!r || r.average_rwf === null) {
    box.replaceChildren(el("p", { class: "muted", text: "Select a district on the map or in the table to see its markets and prices." }));
    return;
  }
  box.replaceChildren(
    el("h2", { text: r.name }),
    el("p", { text: `Average ${MP.data.product} price: ${r.average_rwf.toLocaleString()} RWF per ${MP.data.unit}, ${r.vs_cheapest_pct > 0 ? "+" : ""}${r.vs_cheapest_pct}% against the cheapest district.` }),
    el("ul", {}, ...r.markets.map((m) => el("li", { text: `${m.market}: ${m.price_rwf.toLocaleString()} RWF (observed ${m.observed_on})` }))),
    r.contains_synthetic || r.markets.some((m) => m.is_synthetic)
      ? el("div", { class: "flag", text: "DEMO DATA: these prices are synthetic examples, not real market prices." }) : el("span"));
}

function mpSelect(name) {
  MP.selected = name;
  document.querySelectorAll("#pmMapBox path.district").forEach((p) => p.classList.toggle("selected", p.dataset.name === name));
  mpDrawInfo();
}

$("pmProduct").addEventListener("change", () => { MP.product = +$("pmProduct").value; MP.selected = null; mpRender(); });
