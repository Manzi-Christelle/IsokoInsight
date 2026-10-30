"use strict";
const IND_SVG = "http://www.w3.org/2000/svg";
const IND_YEAR_MIN = 2000, IND_YEAR_MAX = 2026;
const IND_NODATA = "#d6d6d6";
const IND_VALUE_COLS = ["#fbe9c6", "#f7c36b", "#b7d98a", "#5ea56b", "#1f6f4a"];   // low to high
const IND_CHANGE_COLS = ["#b3261e", "#e88b80", "#e9e4d6", "#8cc9a0", "#1f6f4a"];  // fall to rise
const IND_SEASONS = { A: "Season A (Sep to Feb)", B: "Season B (Mar to Jun)", C: "Season C (Jul to Sep)" };
const IND = { catalog: null, geo: null, key: "food_security", year: 2025, season: "A", mode: "value",
  seq: 0, panelSeq: 0, timer: null, map: null, summary: null, selected: null, chart: null, scores: null };

const indItem = (key) => (IND.catalog ? IND.catalog.items.find((i) => i.key === key) : null);
const indChangeUnit = (item) => (item.unit.startsWith("%") || item.unit.startsWith("score") ? "points" : item.unit);
const numTxt = (v, nd = 1) => (v === null || v === undefined ? "n/a"
  : Number(v).toLocaleString(undefined, { minimumFractionDigits: nd, maximumFractionDigits: nd }));
const changeTxt = (v) => (v === null || v === undefined ? "n/a" : (v > 0 ? "+" : "") + numTxt(v));
const pctTxt = (v) => (v === null || v === undefined ? "n/a" : (v > 0 ? "+" : "") + numTxt(v) + "%");
const indSign = (v) => (v === null || v === undefined ? "" : v > 0 ? "ind-pos" : v < 0 ? "ind-neg" : "");

// ---- Controls and loading
async function indLoadCatalog() {
  if (IND.catalog) return;
  IND.catalog = await api("/api/indicators/catalog");
  const groups = new Map();
  IND.catalog.items.forEach((it) => {
    if (!groups.has(it.group_title)) groups.set(it.group_title, []);
    groups.get(it.group_title).push(it);
  });
  const sel = $("iSelect"); sel.replaceChildren();
  groups.forEach((items, title) => {
    const og = el("optgroup", { label: title });
    items.forEach((it) => og.append(el("option", { value: it.key, text: it.label })));
    sel.append(og);
  });
  sel.value = IND.key;
}
function indSyncControls() {
  const item = indItem(IND.key);
  $("iSeasonWrap").hidden = !item.seasonal;
  $("iSeason").value = IND.season;
  $("iMode").value = IND.mode;
  $("iYear").value = IND.year;
  $("iYearOut").textContent = IND.year;
}
async function loadIndicators() {
  try {
    await indLoadCatalog();
    if (!IND.geo) IND.geo = await fetch("/static/data/rwanda_districts.geojson").then((r) => r.json());
    if (!IND.scores) { IND.scores = await api("/api/indicators/food-security"); indRenderScores(); }
    indSyncControls();
    await indLoadView();
  } catch (e) {
    $("iMapBox").replaceChildren(el("p", { class: "err", text: "Could not load indicators: " + e.message }));
  }
}
async function indLoadView() {
  const seq = ++IND.seq;
  const item = indItem(IND.key);
  const season = item.seasonal ? IND.season : "A";  // the API ignores season for annual indicators
  indSyncControls();
  try {
    const [map, summary] = await Promise.all([
      api(`/api/indicators/map?indicator=${encodeURIComponent(IND.key)}&year=${IND.year}&season=${season}`),
      api(`/api/indicators/summary?year=${IND.year}&season=${IND.season}`),
    ]);
    if (seq !== IND.seq) return;  // a newer request has replaced this one
    IND.map = map; IND.summary = summary;
    indRenderMap(); indRenderNational(); indRenderDistricts();
    if (IND.selected) indShowDistrict(IND.selected);
  } catch (e) {
    if (seq === IND.seq) $("iMapBox").replaceChildren(el("p", { class: "err", text: "Could not load this view: " + e.message }));
  }
}

// ---- Colour bands
function indColouring(map) {
  const item = indItem(map.indicator);
  const rows = map.districts;
  if (IND.mode === "change") {
    const deltas = rows.map((r) => r.change_abs).filter((v) => v !== null);
    const t = deltas.length ? Math.max(...deltas.map(Math.abs)) : 0;
    const small = t * 0.2, big = t * 0.6, unit = indChangeUnit(item);
    if (t === 0) {
      return { colour: (r) => (r.change_abs === null ? IND_NODATA : IND_CHANGE_COLS[2]),
        legend: [{ colour: IND_CHANGE_COLS[2], label: `No change in any district` }] };
    }
    const cls = (v) => (v <= -big ? 0 : v <= -small ? 1 : v < small ? 2 : v < big ? 3 : 4);
    const legend = [
      `Falls by ${numTxt(big)} ${unit} or more`,
      `Falls by ${numTxt(small)} to ${numTxt(big)} ${unit}`,
      `Little or no change (within ${numTxt(small)} ${unit})`,
      `Rises by ${numTxt(small)} to ${numTxt(big)} ${unit}`,
      `Rises by ${numTxt(big)} ${unit} or more`,
    ];
    return {
      colour: (r) => (r.change_abs === null ? IND_NODATA : IND_CHANGE_COLS[cls(r.change_abs)]),
      legend: legend.map((label, i) => ({ colour: IND_CHANGE_COLS[i], label })),
    };
  }
  const vals = rows.map((r) => r.value).filter((v) => v !== null);
  const lo = vals.length ? Math.min(...vals) : 0, hi = vals.length ? Math.max(...vals) : 0;
  const edge = (k) => lo + ((hi - lo) * k) / 5;
  if (hi <= lo) {
    return { colour: (r) => (r.value === null ? IND_NODATA : IND_VALUE_COLS[2]),
      legend: [{ colour: IND_VALUE_COLS[2], label: `All districts ${numTxt(lo)} ${item.unit}` }] };
  }
  const cls = (v) => Math.min(4, Math.floor(((v - lo) / (hi - lo)) * 5));
  return {
    colour: (r) => (r.value === null ? IND_NODATA : IND_VALUE_COLS[cls(r.value)]),
    legend: IND_VALUE_COLS.map((c, i) => ({ colour: c, label: `${numTxt(edge(i))} to ${numTxt(edge(i + 1))} ${item.unit}` })),
  };
}

// ---- Map
function indBuildSvg(geo, fillOf, titleOf, onPick) {
  const polys = (f) => (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates);
  const pts = geo.features.flatMap((f) => polys(f).flatMap((poly) => poly.flat()));
  const minX = Math.min(...pts.map((p) => p[0])), maxX = Math.max(...pts.map((p) => p[0]));
  const minY = Math.min(...pts.map((p) => p[1])), maxY = Math.max(...pts.map((p) => p[1]));
  const kx = Math.cos((((minY + maxY) / 2) * Math.PI) / 180);
  const W = (maxX - minX) * kx, H = maxY - minY, pad = 0.02 * Math.max(W, H);
  const project = ([lon, lat]) => [(lon - minX) * kx + pad, maxY - lat + pad];
  const svg = document.createElementNS(IND_SVG, "svg");
  svg.setAttribute("viewBox", `0 0 ${W + 2 * pad} ${H + 2 * pad}`);
  geo.features.forEach((f) => {
    const name = f.properties.name;
    const d = polys(f).map((poly) => poly.map((ring) =>
      "M" + ring.map((c) => project(c).map((v) => v.toFixed(4)).join(" ")).join("L") + "Z").join("")).join("");
    const p = document.createElementNS(IND_SVG, "path");
    p.setAttribute("d", d);
    p.setAttribute("class", "district");
    p.setAttribute("fill", fillOf(name));
    p.setAttribute("tabindex", "0");
    p.setAttribute("role", "button");
    p.setAttribute("aria-label", titleOf(name));
    p.dataset.name = name;
    const t = document.createElementNS(IND_SVG, "title");
    t.textContent = titleOf(name);
    p.append(t);
    p.addEventListener("click", () => onPick(name));
    p.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPick(name); } });
    svg.append(p);
  });
  return svg;
}
function indRenderMap() {
  const m = IND.map; if (!m || !IND.geo) return;
  const item = indItem(m.indicator);
  const byName = Object.fromEntries(m.districts.map((r) => [r.name, r]));
  const col = indColouring(m);
  const seasonTxt = item.seasonal ? `, ${IND_SEASONS[IND.season]}` : "";

  $("iLegend").replaceChildren(
    ...col.legend.map((x) => el("span", { class: "item" }, el("span", { class: "sw", style: `background:${x.colour}` }), x.label)),
    el("span", { class: "item" }, el("span", { class: "sw", style: `background:${IND_NODATA}` }),
      IND.mode === "change" ? "No figure (no earlier year, or no data)" : "No data for this year and season"));
  $("iLead").textContent = IND.mode === "change"
    ? `${item.label}: change from ${IND.year - 1} to ${IND.year}${seasonTxt}. Green is a rise and red a fall, in ${indChangeUnit(item)}. Select a district for its full history.`
    : `${item.label}, ${IND.year}${seasonTxt}. Unit: ${item.unit}. ${item.description} Colours split the values into five equal bands from the lowest to the highest district that year.`;

  const tip = (name) => {
    const r = byName[name];
    if (!r || r.value === null) return `${name}: no data for this year and season`;
    const change = r.change_abs === null ? "no earlier year to compare"
      : `change ${changeTxt(r.change_abs)} ${indChangeUnit(item)} (${pctTxt(r.change_pct)})`;
    return `${name}: ${numTxt(r.value)} ${item.unit}; ${change}`;
  };
  const svg = indBuildSvg(IND.geo, (name) => (byName[name] ? col.colour(byName[name]) : IND_NODATA), tip, indShowDistrict);
  $("iMapBox").replaceChildren(svg);
  indMarkSelected();
}
function indMarkSelected() {
  document.querySelectorAll("#iMapBox path.district")
    .forEach((p) => p.classList.toggle("selected", p.dataset.name === IND.selected));
}

// ---- District panel: chart, year-by-year changes and every indicator for the district
async function indShowDistrict(name) {
  IND.selected = name; indMarkSelected();
  const pseq = ++IND.panelSeq;
  try {
    const [series, panel] = await Promise.all([
      api(`/api/indicators/series?indicator=${encodeURIComponent(IND.key)}&district=${encodeURIComponent(name)}`),
      api(`/api/indicators/district?district=${encodeURIComponent(name)}&year=${IND.year}&season=${IND.season}`),
    ]);
    if (pseq !== IND.panelSeq) return;
    indDrawPanel(name, series, panel);
  } catch (e) {
    $("iDistrictInfo").replaceChildren(el("p", { class: "err", text: `Could not load ${name}: ${e.message}` }));
  }
}
function indDrawPanel(name, series, panel) {
  const item = indItem(IND.key);
  const seasonTxt = item.seasonal ? ` (season ${IND.season})` : "";
  const cur = series.points.find((p) => p.year === IND.year && (!item.seasonal || p.season === IND.season));
  const hasValue = cur && cur.value !== null;

  const yearLabel = (p) => (p.season ? `${p.year} ${p.season}` : String(p.year));
  const chartBox = el("div", { class: "chartbox", style: "height:220px" },
    el("canvas", { id: "iChart", role: "img", "aria-label": `${item.label} over time in ${name}` }));
  const yearRows = series.points.map((p) => el("tr", {}, td(yearLabel(p)), td(numTxt(p.value), "num"),
    td(changeTxt(p.change_abs), `num ${indSign(p.change_abs)}`), td(pctTxt(p.change_pct), `num ${indSign(p.change_pct)}`)));
  const itemRows = panel.items.map((it) => el("tr", {}, td(it.label + (it.season ? ` (season ${it.season})` : "")),
    td(numTxt(it.value), "num"), td(changeTxt(it.change_abs), `num ${indSign(it.change_abs)}`),
    td(pctTxt(it.change_pct), `num ${indSign(it.change_pct)}`), td(it.unit)));

  $("iDistrictInfo").replaceChildren(
    el("h2", { text: name }),
    el("p", { text: hasValue ? `${item.label}${seasonTxt}, ${IND.year}: ${numTxt(cur.value)} ${item.unit}.`
      : `No value for ${item.label}${seasonTxt} in ${IND.year}.` }),
    el("p", { class: indSign(cur && cur.change_abs), text: cur && cur.change_abs !== null
      ? `Change from the year before: ${changeTxt(cur.change_abs)} ${indChangeUnit(item)} (${pctTxt(cur.change_pct)}).`
      : "No earlier value to compare with." }),
    chartBox,
    el("details", { open: "" }, el("summary", { text: "Year by year: values and changes" }),
      buildTable([{ label: "Year" }, { label: "Value", num: true }, { label: "Change", num: true },
        { label: "Change (%)", num: true }], yearRows)),
    el("details", { open: "" }, el("summary", { text: `Every indicator in ${name}, ${IND.year}` }),
      buildTable([{ label: "Indicator" }, { label: "Value", num: true }, { label: "Change", num: true },
        { label: "Change (%)", num: true }, { label: "Unit" }], itemRows)),
    el("div", { class: "flag", text: "SYNTHETIC DEMO DATA: these district values are randomly generated and are not NISR statistics." }),
    el("p", { class: "muted", text: `Source: ${item.source}.` }));

  if (IND.chart) { IND.chart.destroy(); IND.chart = null; }
  IND.chart = new Chart(document.getElementById("iChart"), {
    type: "line",
    data: { labels: series.points.map(yearLabel),
      datasets: [{ label: item.unit, data: series.points.map((p) => p.value), borderColor: "#1f6f4a",
        pointRadius: 2, tension: 0.2, spanGaps: true }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
      scales: { x: { ticks: { maxTicksLimit: 8 } } } },
  });
}

// ---- Districts table and national summary
function indRenderDistricts() {
  const m = IND.map; const item = indItem(m.indicator);
  const seasonTxt = item.seasonal ? `, season ${IND.season}` : "";
  const rows = [...m.districts].sort((a, b) => {
    if (a.value === null) return 1;
    if (b.value === null) return -1;
    return b.value - a.value;
  });
  const trs = rows.map((r) => {
    const tr = el("tr", { class: "dist-row", tabindex: "0", "data-name": r.name },
      td(r.name), td(numTxt(r.value), "num"), td(changeTxt(r.change_abs), `num ${indSign(r.change_abs)}`),
      td(pctTxt(r.change_pct), `num ${indSign(r.change_pct)}`), td(r.rank === null ? "n/a" : String(r.rank), "num"));
    tr.addEventListener("click", () => indShowDistrict(r.name));
    tr.addEventListener("keydown", (e) => { if (e.key === "Enter") indShowDistrict(r.name); });
    return tr;
  });
  $("iTableTitle").textContent = `${item.label}, all districts, ${IND.year}${seasonTxt}`;
  $("iTable").replaceChildren(
    buildTable([{ label: "District" }, { label: "Value", num: true }, { label: "Change from the year before", num: true },
      { label: "Change (%)", num: true }, { label: "Rank (1 = highest)", num: true }], trs));
}
function indRenderNational() {
  const s = IND.summary; if (!s) return;
  const rows = s.items.map((it) => el("tr", {},
    td(it.label + (it.season ? ` (season ${it.season})` : "")), td(it.group_title),
    td(numTxt(it.mean_value), "num"), td(changeTxt(it.mean_change_abs), `num ${indSign(it.mean_change_abs)}`),
    td(pctTxt(it.mean_change_pct), `num ${indSign(it.mean_change_pct)}`),
    td(it.national_reported === null ? "-" : numTxt(it.national_reported), "num"),
    td(it.synthetic ? "Synthetic demo" : "Recorded national figure")));
  $("iNational").replaceChildren(
    el("p", { class: "muted", text: "Averages across the districts that reported. The change compares the same districts with the year before. A recorded national figure is the NISR input figure typed into the workbook, with its source named there; it has not been re-checked here." }),
    buildTable([{ label: "Indicator" }, { label: "Group" }, { label: "Average of districts", num: true },
      { label: "Change", num: true }, { label: "Change (%)", num: true }, { label: "National figure (recorded)", num: true },
      { label: "Data" }], rows));
}

// ---- Food security score by district and year
function indRenderScores() {
  const t = IND.scores; if (!t) return;
  $("iScoreNote").textContent = t.note;
  const mode = $("iScoreMode").value;
  const years = t.years;
  const scoreBg = (v) => IND_VALUE_COLS[Math.min(4, Math.max(0, Math.floor(v / 20)))];
  const head = el("tr", {}, el("th", { text: "District" }), ...years.map((y) => el("th", { class: "num", text: String(y) })));
  const body = t.districts.map((row) => el("tr", {}, el("td", { text: row.name }),
    ...years.map((y, i) => {
      const s = row.scores[String(y)];
      if (mode === "change") {
        const p = i > 0 ? row.scores[String(years[i - 1])] : undefined;
        const c = s !== undefined && p !== undefined ? Math.round((s - p) * 10) / 10 : null;
        return el("td", { class: `num ${indSign(c)}`, text: c === null ? "" : changeTxt(c) });
      }
      return el("td", { class: "num", style: s === undefined ? "" : `background:${scoreBg(s)};color:#1d2a22`,
        text: s === undefined ? "" : numTxt(s) });
    })));
  $("iScoreBox").replaceChildren(el("table", { class: "matrix" }, el("thead", {}, head), el("tbody", {}, ...body)));
}

// ---- Controls
function indSetYear(y) {
  IND.year = y;
  $("iYear").value = y; $("iYearOut").textContent = y;
  indLoadView();
}
function indStop() {
  clearInterval(IND.timer); IND.timer = null;
  $("iPlay").textContent = "Play years";
}
let indYearTimer = null;
$("iSelect").addEventListener("change", (e) => { IND.key = e.target.value; indLoadView(); });
$("iSeason").addEventListener("change", (e) => { IND.season = e.target.value; indLoadView(); });
$("iMode").addEventListener("change", (e) => { IND.mode = e.target.value; indRenderMap(); });
$("iYear").addEventListener("input", (e) => {
  indStop();
  IND.year = +e.target.value; $("iYearOut").textContent = IND.year;
  clearTimeout(indYearTimer);
  indYearTimer = setTimeout(indLoadView, 120);  // wait briefly so dragging does not send a request per pixel
});
$("iPlay").addEventListener("click", () => {
  if (IND.timer) return indStop();
  if (IND.year >= IND_YEAR_MAX) indSetYear(IND_YEAR_MIN);
  $("iPlay").textContent = "Pause";
  IND.timer = setInterval(() => {
    if (IND.year >= IND_YEAR_MAX) return indStop();
    indSetYear(IND.year + 1);
  }, 1000);
});
$("iScoreMode").addEventListener("change", indRenderScores);
