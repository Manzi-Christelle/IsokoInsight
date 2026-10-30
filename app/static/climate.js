"use strict";
/* Weather and climate tab: rainfall and temperature by district against normal, and the farming impact.
   All values come from SYNTHETIC demonstration data, and this screen says so. Uses helpers from app.js
   ($, el, api, td, fmtPct) and map-tools.js (drawDistrictMap). */
const CL = { geo: null, years: null, year: null, metric: "rain", selected: null, status: null,
  chart: null, seq: 0, guideShown: false };

const clNum = (v, nd = 0) => (v === null || v === undefined ? "n/a"
  : Number(v).toLocaleString(undefined, { minimumFractionDigits: nd, maximumFractionDigits: nd }));
const clSigned = (v, nd = 0, unit = "") => (v === null || v === undefined ? "n/a" : (v > 0 ? "+" : "") + clNum(v, nd) + unit);

async function clLoad() {
  try {
    if (!CL.geo) CL.geo = await fetch("/static/data/rwanda_districts.geojson").then((r) => r.json());
    if (!CL.years) {
      CL.years = await api("/api/climate/years");
      const sel = $("clYear"); sel.replaceChildren();
      CL.years.years.slice().reverse().forEach((y) => sel.append(el("option", { value: y, text: String(y) })));
      CL.year = CL.years.years[CL.years.years.length - 1];
      sel.value = CL.year;
      $("clNote").textContent = CL.years.note;
    }
    $("clMetric").value = CL.metric;
    await clRender();
  } catch (e) {
    $("clMapBox").replaceChildren(el("p", { class: "err", text: "Could not load weather data: " + e.message }));
  }
}

async function clRender() {
  const seq = ++CL.seq;
  try {
    const s = await api(`/api/climate/status?year=${CL.year}`);
    if (seq !== CL.seq) return;
    CL.status = s;
    clDrawLegend(); clDrawMap(); clDrawTable(); clDrawGuide(); clDrawInfo();
    if (CL.selected) clLoadDistrict(CL.selected);
    else clDrawChart(null);
  } catch (e) {
    if (seq === CL.seq) $("clMapBox").replaceChildren(el("p", { class: "err", text: "Could not load this view: " + e.message }));
  }
}

function clRows() { return CL.status ? CL.status.districts : []; }
function clRow(name) { return clRows().find((d) => d.name === name); }
function clColour(row) {
  if (!row || !row.data_available) return "#d6d6d6";
  const key = CL.metric === "temp" ? row.temp_class : row.impact_class;
  const legend = CL.status.legend[CL.metric];
  const item = legend.find((l) => l.key === key);
  return item ? item.colour : "#d6d6d6";
}

function clDrawLegend() {
  const isTemp = CL.metric === "temp";
  const base = isTemp ? "Temperature" : "Rainfall";
  $("clLead").textContent = isTemp
    ? `Each district is coloured by how its mean temperature in ${CL.year} compared with its average for ${CL.status.baseline_years[0]} to ${CL.status.baseline_years[CL.status.baseline_years.length - 1]}.`
    : `Each district is coloured by how its rainfall in ${CL.year} compared with its normal (average for ${CL.status.baseline_years[0]} to ${CL.status.baseline_years[CL.status.baseline_years.length - 1]}). The colours show the likely effect on farming.`;
  $("clLegend").replaceChildren(el("b", { text: base + ": " }),
    ...CL.status.legend[CL.metric].map((l) => el("span", { class: "item" }, el("span", { class: "sw", style: `background:${l.colour}` }),
      `${l.label} (${l.range})`)));
  $("clLegend").append(el("span", { class: "muted", text: " Grey: no data for this district and year." }));
}

function clDrawMap() {
  const svg = drawDistrictMap(CL.geo,
    (name) => clColour(clRow(name)),
    (name) => { const r = clRow(name); return r && r.data_available
      ? `${name}: ${clSigned(r.rain_vs_normal_pct, 0, "%")} rain vs normal; ${clSigned(r.temp_vs_normal_c, 1, " C")} temperature vs normal`
      : `${name}: no data`; },
    (name) => clSelect(name), CL.selected);
  $("clMapBox").replaceChildren(svg);
}

function clDrawTable() {
  const rows = [...clRows()].sort((a, b) => a.name.localeCompare(b.name)).map((r) => {
    const tr = el("tr", { class: "dist-row", "data-name": r.name, tabindex: "0" },
      td(r.name), td(r.province || "-"),
      td(r.data_available ? clNum(r.rain_mm) : "n/a", "num"),
      td(r.data_available ? clSigned(r.rain_vs_normal_pct, 0, "%") : "n/a", "num " + (r.rain_vs_normal_pct < 0 ? "down" : r.rain_vs_normal_pct > 0 ? "up" : "")),
      td(r.data_available ? clNum(r.temp_c, 1) : "n/a", "num"),
      td(r.data_available ? clSigned(r.temp_vs_normal_c, 1, " C") : "n/a", "num"),
      el("td", {}, el("span", { class: "chip", style: `background:${clColour(r)};color:#111`, text: r.impact_label || "No data" })));
    tr.addEventListener("click", () => clSelect(r.name));
    tr.addEventListener("keydown", (e) => { if (e.key === "Enter") clSelect(r.name); });
    return tr;
  });
  $("clTable").replaceChildren(buildTable([{ label: "District" }, { label: "Province" }, { label: "Rain (mm)", num: true },
    { label: "Rain vs normal", num: true }, { label: "Mean temp (C)", num: true }, { label: "Temp vs normal", num: true },
    { label: "Farming impact (rain)" }], rows));
}

function clDrawGuide() {
  const ul = $("clGuide"); ul.replaceChildren();
  CL.status.impact_guide.forEach((g) => ul.append(el("li", {}, el("span", { class: "sw", style: `background:${g.colour}` }),
    el("b", { text: " " + g.label + ": " }), el("span", { text: g.text }))));
  $("clImpactNote").textContent = CL.status.impact_note;
}

function clDrawInfo() {
  const box = $("clInfo");
  if (!CL.selected) { box.replaceChildren(el("p", { class: "muted", text: "Select a district on the map or in the table to see its monthly rainfall and temperature." })); return; }
  const r = clRow(CL.selected);
  if (!r || !r.data_available) { box.replaceChildren(el("h2", { text: CL.selected }), el("p", { class: "muted", text: "No climate data for this district and year." })); return; }
  box.replaceChildren(
    el("h2", { text: r.name }),
    el("p", {}, el("span", { class: "chip", style: `background:${clColour(r)};color:#111`, text: r.impact_label }), " ", el("span", { class: "muted", text: r.province })),
    el("p", { text: `Rainfall in ${CL.year}: ${clNum(r.rain_mm)} mm, ${clSigned(r.rain_vs_normal_pct, 0, "%")} against a normal of ${clNum(r.rain_normal_mm)} mm.` }),
    el("p", { text: `Mean temperature: ${clNum(r.temp_c, 1)} C, ${clSigned(r.temp_vs_normal_c, 1, " C")} against normal.` }),
    el("p", { text: r.impact_text }),
    el("div", { class: "flag", text: "DEMO DATA: this rainfall and temperature is synthetic and is not a Meteo Rwanda observation." }));
}

async function clSelect(name) {
  CL.selected = name;
  document.querySelectorAll("#clMapBox path.district").forEach((p) => p.classList.toggle("selected", p.dataset.name === name));
  clDrawInfo();
  await clLoadDistrict(name);
}

async function clLoadDistrict(name) {
  try {
    const d = await api(`/api/climate/district?district=${encodeURIComponent(name)}&year=${CL.year}`);
    if (CL.selected !== name) return;
    clDrawChart(d);
  } catch (e) {
    clDrawChart(null, e.message);
  }
}

function clDrawChart(d, errorText) {
  if (CL.chart) { CL.chart.destroy(); CL.chart = null; }
  const note = $("clChartNote");
  if (!d) {
    note.textContent = errorText ? "Could not load this district: " + errorText : "Select a district to see its monthly rainfall and temperature against normal.";
    return;
  }
  note.textContent = `${d.district} (${d.province}), ${d.year}. Demo data: synthetic values, not Meteo Rwanda observations.`;
  const labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  CL.chart = new Chart($("clChart"), {
    type: "bar",
    data: { labels, datasets: [
      { type: "bar", label: "Rain (mm)", data: d.months.map((m) => m.rain_mm), backgroundColor: "#5ab4ac", yAxisID: "y" },
      { type: "line", label: "Normal rain (mm)", data: d.months.map((m) => m.rain_normal_mm), borderColor: "#8c510a", pointRadius: 0, tension: 0.2, yAxisID: "y" },
      { type: "line", label: "Mean temp (C)", data: d.months.map((m) => m.temp_c), borderColor: "#b2182b", pointRadius: 2, tension: 0.2, yAxisID: "y1" },
      { type: "line", label: "Normal temp (C)", data: d.months.map((m) => m.temp_normal_c), borderColor: "#b2182b", borderDash: [6, 4], pointRadius: 0, tension: 0.2, yAxisID: "y1" },
    ] },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
      scales: { y: { position: "left", title: { display: true, text: "Rain (mm)" }, beginAtZero: true },
        y1: { position: "right", title: { display: true, text: "Temperature (C)" }, grid: { drawOnChartArea: false } } } },
  });
}

$("clYear").addEventListener("change", () => { CL.year = +$("clYear").value; clRender(); });
$("clMetric").addEventListener("change", () => { CL.metric = $("clMetric").value; clRender(); });
