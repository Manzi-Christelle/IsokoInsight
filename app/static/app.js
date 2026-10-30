"use strict";
const $ = (id) => document.getElementById(id);
const api = async (path, opts = {}) => {
  const headers = Object.assign({}, opts.headers || {});
  if (token) headers.Authorization = "Bearer " + token;
  const res = await fetch(path, Object.assign({}, opts, { headers }));
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch (e) {}
    throw new Error(msg);
  }
  return res.json();
};
let token = null, role = null, me = null, perms = new Set();
try { token = sessionStorage.getItem("isoko_token"); role = sessionStorage.getItem("isoko_role"); } catch (e) {}
const can = (p) => perms.has(p);
const ROLE_NOTE = { customer: "Customer", farmer_seller: "Farmer / seller", enumerator: "Enumerator", nisr: "NISR statistician", admin: "Administrator" };
let cpiChart = null, histChart = null, products = [];

// Safe DOM helpers: never put user-supplied text into innerHTML.
function el(tag, props = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") n.className = v; else if (k === "text") n.textContent = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v); else n.setAttribute(k, v);
  }
  kids.forEach((c) => n.append(c));
  return n;
}
const fmtPct = (v) => (v === null || v === undefined ? "n/a" : (v > 0 ? "+" : "") + v.toFixed(1) + "%");
const pctClass = (v) => (v > 0 ? "up" : v < 0 ? "down" : "");
function fillSelect(sel, items, label, allOption) {
  sel.replaceChildren();
  if (allOption) sel.append(el("option", { value: "", text: allOption }));
  items.forEach((i) => sel.append(el("option", { value: i.id, text: label(i) })));
}
function setRows(tableId, rows) {
  const tb = $(tableId).querySelector("tbody"); tb.replaceChildren(...rows);
}
function td(text, cls) { return el("td", { text: String(text), class: cls || "" }); }

// ---- Tabs
function showTab(name) {
  document.querySelectorAll(".tab").forEach((s) => (s.hidden = s.id !== "tab-" + name));
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  if (name === "admin") loadAdmin();
  if (name === "sources") loadSources();
  if (name === "map" && !mapData) loadMap(null);
  if (name === "contribute") loadContribute();
  if (name === "indicators") loadIndicators();
  if (name === "climate") clLoad();
  if (name === "prices") mpLoad();
}
$("tabs").addEventListener("click", (e) => { if (e.target.dataset.tab) showTab(e.target.dataset.tab); });

// ---- Overview
async function loadOverview() {
  const [summary, inds, official] = await Promise.all(
    [api("/api/summary"), api("/api/official/indicators"), api("/api/official/series")]);
  $("demoBanner").hidden = !(summary.synthetic_observations > 0 || official.series.some((s) => s.is_synthetic));
  const k = $("kpis"); k.replaceChildren();
  const headline = inds.find((i) => i.name.startsWith("Headline"));
  const card = (big, label) => k.append(el("div", { class: "kpi" }, el("b", { text: big }), el("span", { text: label })));
  if (headline) card(headline.value.toFixed(1) + "%", `${headline.name} (${headline.period.slice(0, 7)}, NISR)`);
  card(summary.verified_observations, "Verified market observations");
  card(summary.markets_with_data, "Markets with verified prices");
  card(summary.latest_price_date || "none yet", "Latest verified price date");

  const sel = $("seriesSelect"); sel.replaceChildren();
  official.series.forEach((s) => sel.append(el("option", { value: s.code, text: s.name })));
  const food = official.series.find((s) => s.group === "headline") || official.series[0];
  if (food) { sel.value = food.code; drawCpi(); }
  const tb = official.series.filter((s) => s.yoy_pct !== null).sort((a, b) => b.yoy_pct - a.yoy_pct)
    .map((s) => el("tr", {}, td(s.name), td(s.latest_period.slice(0, 7)),
      td(fmtPct(s.yoy_pct), "num " + pctClass(s.yoy_pct)), td(fmtPct(s.mom_pct), "num " + pctClass(s.mom_pct))));
  setRows("seriesTable", tb);
}
async function drawCpi() {
  const code = $("seriesSelect").value; if (!code) return;
  const metric = $("seriesMetric").value;
  const d = await api("/api/official/series/" + encodeURIComponent(code));
  const pts = d.data.filter((p) => p[metric] !== null);
  if (cpiChart) cpiChart.destroy();
  cpiChart = new Chart($("cpiChart"), {
    type: "line",
    data: { labels: pts.map((p) => p.period.slice(0, 7)),
      datasets: [{ label: d.name, data: pts.map((p) => p[metric]), borderColor: "#1b4f9c", pointRadius: 0, tension: 0.2 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
      scales: { x: { ticks: { maxTicksLimit: 8 } } } },
  });
  const f = $("flags"); f.replaceChildren();
  d.review_flags.slice(-5).forEach((a) => f.append(el("div", { class: "flag",
    text: `${a.period.slice(0, 7)}: ${fmtPct(a.change_pct)} month-on-month. ${a.reasons.join("; ")}. ${a.message}` })));
  $("cpiSource").textContent = `Source: ${d.source.name} (${d.source.publisher})` + (d.source.is_synthetic ? " - SYNTHETIC DEMO DATA" : "");
}
$("seriesSelect").addEventListener("change", drawCpi);
$("seriesMetric").addEventListener("change", drawCpi);

// ---- Prices
function priceQuery() {
  const p = new URLSearchParams();
  if ($("fProduct").value) p.set("product_id", $("fProduct").value);
  if ($("fMarket").value) p.set("market_id", $("fMarket").value);
  if ($("fFrom").value) p.set("date_from", $("fFrom").value);
  if ($("fTo").value) p.set("date_to", $("fTo").value);
  return p.toString();
}
// Price search: the dates must fall inside the range the data covers. Outside it, the screen says "No data found".
let priceRange = null;
const NO_DATA = "No data found";
function longDate(iso) {
  return new Date(iso + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
}
async function loadPriceRange() {
  if (priceRange) return priceRange;
  priceRange = await api("/api/prices/coverage");
  for (const id of ["fFrom", "fTo"]) { $(id).min = priceRange.start; $(id).max = priceRange.end; }
  $("fRange").textContent = `Choose dates between ${longDate(priceRange.start)} and ${longDate(priceRange.end)}. `
    + "The demonstration prices are synthetic.";
  return priceRange;
}
// Returns a message when the chosen dates cannot have data, otherwise "".
function priceDateProblem() {
  const f = $("fFrom").value, t = $("fTo").value;
  if ((f && (f < priceRange.start || f > priceRange.end)) || (t && (t < priceRange.start || t > priceRange.end))) return NO_DATA;
  if (f && t && f > t) return "The From date must be on or before the To date.";
  return "";
}
function showPriceError(message) {
  $("fError").hidden = !message;
  $("fError").textContent = message;
}
function clearPriceHistory(note) {
  if (histChart) { histChart.destroy(); histChart = null; }
  $("histChart").parentElement.hidden = true;
  $("histNote").textContent = note;
}
async function loadPrices() {
  await loadPriceRange();
  const q = priceQuery();
  $("fExport").dataset.query = q;
  const problem = priceDateProblem();
  showPriceError(problem);
  if (problem) {
    setRows("priceTable", []);
    clearPriceHistory(problem === NO_DATA ? `${NO_DATA}. Choose dates between ${longDate(priceRange.start)} and ${longDate(priceRange.end)}.` : problem);
    return;
  }
  const rows = await api("/api/prices?" + q);
  setRows("priceTable", rows.map((r) => el("tr", {}, td(r.observed_on), td(r.product), td(r.market + ", " + r.district),
    td(r.price_rwf.toLocaleString(), "num"), td(r.unit), td(r.source + (r.is_synthetic ? " (DEMO)" : "")), td(r.status))));
  if (!rows.length) showPriceError(NO_DATA);
  await drawPriceHistory();
}
async function drawPriceHistory() {
  const pid = $("fProduct").value;
  const note = $("histNote");
  const chartBox = $("histChart").parentElement;
  if (histChart) { histChart.destroy(); histChart = null; }
  if (!pid) {
    chartBox.hidden = true;
    note.textContent = "Choose a product and press Search to see how its verified price changed over the dates you chose. Each line is one market; the table below lists the same records.";
    return;
  }
  const hq = `/api/prices/history?product_id=${pid}` + ($("fMarket").value ? `&market_id=${$("fMarket").value}` : "")
    + ($("fFrom").value ? `&date_from=${$("fFrom").value}` : "") + ($("fTo").value ? `&date_to=${$("fTo").value}` : "");
  const h = await api(hq);
  const lines = Object.entries(h);
  const dates = [...new Set(lines.flatMap(([, pts]) => pts.map((p) => p.date)))].sort();
  const pname = products.find((p) => String(p.id) === String(pid));
  if (!dates.length) {
    chartBox.hidden = true;
    note.textContent = `${NO_DATA} for ${pname ? pname.name : "this product"} between these dates.`;
    return;
  }
  chartBox.hidden = false;
  const unit = pname ? pname.standard_unit : "";
  note.textContent = `${pname ? pname.name : "Product"}: verified prices from ${dates[0]} to ${dates[dates.length - 1]}, `
    + `in Rwandan francs (RWF) per ${unit || "unit"}. Each line is one market. Points are the verified observation dates; gaps mean no verified price that day.`;
  const css = getComputedStyle(document.documentElement);
  const muted = css.getPropertyValue("--muted").trim() || "#405a73";
  const grid = css.getPropertyValue("--line").trim() || "#cfdcea";
  Chart.defaults.color = muted;
  const palette = ["#0b5ea8", "#e07b00", "#2e7d32", "#7b1fa2", "#b3261e", "#00838f", "#5d4037", "#c2185b"];
  histChart = new Chart($("histChart"), { type: "line",
    data: { labels: dates, datasets: lines.map(([name, pts], i) => ({ label: name, borderColor: palette[i % palette.length],
      backgroundColor: palette[i % palette.length], borderWidth: 3, pointRadius: 4, pointHoverRadius: 6,
      data: dates.map((d) => (pts.find((p) => p.date === d) || {}).price_rwf ?? null), spanGaps: true, tension: 0.2 })) },
    options: { responsive: true, maintainAspectRatio: false, interaction: { mode: "nearest", intersect: false },
      plugins: { legend: { position: "bottom", labels: { boxWidth: 28, font: { size: 14 } } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${Number(c.parsed.y).toLocaleString()} RWF` } } },
      scales: {
        x: { title: { display: true, text: "Date of verified observation", font: { size: 14 } }, grid: { color: grid },
          ticks: { maxRotation: 45, autoSkip: true, font: { size: 13 } } },
        y: { title: { display: true, text: `Price (RWF per ${unit || "unit"})`, font: { size: 14 } }, grid: { color: grid },
          ticks: { font: { size: 13 }, callback: (v) => Number(v).toLocaleString() } } } } });
}
$("fApply").addEventListener("click", loadPrices);

// ---- Session, roles and permissions (the server decides; this page only hides what a role cannot use)
async function loadSession() {
  if (token) {
    try {
      me = await api("/api/auth/me");
      role = me.role; perms = new Set(me.permissions);
      try { sessionStorage.setItem("isoko_role", role); } catch (e) {}
    } catch (e) { clearSession(); }
  }
  updateAuthUi();
}
function clearSession() {
  token = role = me = null; perms = new Set();
  try { sessionStorage.clear(); } catch (e) {}
}
function signOut() { clearSession(); updateAuthUi(); showTab("overview"); }
function updateAuthUi() {
  const box = $("accountBox"); box.replaceChildren();
  if (me) {
    box.append(el("span", { class: "muted", text: `${me.full_name || me.email} (${me.role_label})` }),
      el("button", { id: "logoutBtn", type: "button", text: "Sign out", onclick: signOut }));
  } else {
    box.append(el("a", { class: "btn primary", href: "/account", text: "Sign in / Create account" }));
  }
  const contributeVisible = can("submit_price") || can("view_own_submissions");
  document.querySelector('#tabs [data-tab="contribute"]').hidden = !!me && !contributeVisible;
  $("nisrTab").hidden = !(can("view_statistics") || can("export_full_dataset"));
  $("adminTab").hidden = !can("review_prices");
  $("contribSignin").hidden = !!me;
  $("contribBody").hidden = !me || !contributeVisible;
  $("submitCard").hidden = !can("submit_price");
  $("mineCard").hidden = !can("view_own_submissions");
  if (me && !contributeVisible) {
    $("contribSignin").hidden = false;
    $("contribSignin").firstElementChild.textContent = `Your role (${me.role_label}) cannot submit prices. Public and verified data are available on the other tabs.`;
  }
}

// Downloads need the sign-in token, so they are fetched and saved rather than linked directly.
async function downloadFile(url, filename) {
  const res = await fetch(url, { headers: token ? { Authorization: "Bearer " + token } : {} });
  if (!res.ok) {
    let msg = "This download is not available for your account.";
    try { const j = await res.json(); if (typeof j.detail === "string") msg = j.detail; } catch (e) {}
    alert(msg); return;
  }
  const a = el("a", { href: URL.createObjectURL(await res.blob()), download: filename });
  document.body.append(a); a.click(); a.remove();
}
$("fExport").addEventListener("click", () => {
  if (!me) { alert("Sign in to download verified prices."); return; }
  downloadFile("/api/prices/export.csv?" + ($("fExport").dataset.query || ""), "isoko_prices.csv");
});

// ---- Contribute: submit and track own prices
async function loadContribute() {
  if (!can("view_own_submissions")) return;
  const rows = await api("/api/me/submissions");
  $("mineEmpty").hidden = rows.length > 0;
  setRows("mineTable", rows.map((r) => el("tr", {}, td(r.observed_on), td(r.product), td(r.market + ", " + r.district),
    td(r.price_rwf.toLocaleString(), "num"), td(r.status === "verified" ? "Verified" : r.status === "rejected" ? "Rejected" : "Pending review"))));
}
$("sProduct").addEventListener("change", () => { const p = products.find((x) => String(x.id) === $("sProduct").value); if (p) $("sUnit").textContent = p.standard_unit; });
$("submitForm").addEventListener("submit", async (e) => {
  e.preventDefault(); const p = products.find((x) => String(x.id) === $("sProduct").value);
  try {
    const r = await api("/api/prices", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_id: +$("sProduct").value, market_id: +$("sMarket").value, price_rwf: +$("sPrice").value,
        unit: p.standard_unit, observed_on: $("sDate").value, collection_method: $("sMethod").value }) });
    $("submitMsg").textContent = r.message + (r.flagged_for_review ? " (Flagged for extra review: large change.)" : ""); $("submitMsg").className = "ok";
    loadContribute();
  } catch (err) { $("submitMsg").textContent = err.message; $("submitMsg").className = "err"; }
});

// ---- NISR statistics and full dataset
$("nisrCsv").addEventListener("click", () => downloadFile("/api/nisr/dataset.csv", "nisr_price_dataset.csv"));
$("nisrStats").addEventListener("click", async () => {
  const out = $("nisrOut"); out.replaceChildren(el("p", { class: "muted", text: "Generating statistics..." }));
  try {
    const s = await api("/api/nisr/statistics");
    const table = (heads, rows) => el("div", { class: "tablewrap" }, el("table", {},
      el("thead", {}, el("tr", {}, ...heads.map((h) => el("th", { class: h.num ? "num" : "", text: h.label })))),
      el("tbody", {}, ...rows)));
    const products = s.products.map((p) => el("tr", {}, td(p.product), td(p.unit), td(p.markets, "num"),
      td(p.min_rwf.toLocaleString(), "num"), td(p.median_rwf.toLocaleString(), "num"), td(p.max_rwf.toLocaleString(), "num"), td(p.latest_date)));
    const months = s.monthly_medians.map((m) => el("tr", {}, td(m.product), td(m.month), td(m.observations, "num"), td(m.median_rwf.toLocaleString(), "num")));
    const dist = s.districts.status_counts;
    out.replaceChildren(
      el("div", { class: "card" }, el("h2", { text: "Summary" }),
        el("p", { text: `Verified observations: ${s.verified_observations}. Generated ${s.generated_at.replace("T", " ")}.` }),
        el("p", { class: "muted", text: s.note }),
        s.contains_synthetic ? el("div", { class: "flag", text: "DEMO DATA: this output includes synthetic demonstration records." }) : el("span")),
      el("div", { class: "card" }, el("h2", { text: "Latest verified prices by product (across markets)" }),
        table([{ label: "Product" }, { label: "Unit" }, { label: "Markets", num: true }, { label: "Min (RWF)", num: true },
          { label: "Median (RWF)", num: true }, { label: "Max (RWF)", num: true }, { label: "Latest date" }], products)),
      el("div", { class: "card" }, el("h2", { text: "Monthly median price by product" }),
        table([{ label: "Product" }, { label: "Month" }, { label: "Observations", num: true }, { label: "Median (RWF)", num: true }], months)),
      el("div", { class: "card" }, el("h2", { text: "District colour counts" }),
        el("p", { text: `Critical: ${dist.critical}; medium: ${dist.medium}; good: ${dist.good}; limited data: ${dist.limited_data}; no verified data: ${dist.no_data}.` })),
      el("div", { class: "card" }, el("h2", { text: "Official NISR figures" }),
        el("p", { text: `CPI series loaded: ${s.official.series_count}.` }),
        ...s.official.headline.map((h) => el("p", { text: `${h.name} (${h.period.slice(0, 7)}): ${h.value}% - source: ${h.source}` }))));
  } catch (err) { out.replaceChildren(el("p", { class: "err", text: err.message })); }
});

// ---- Review and account management (administrators)
const USER_ROLES = ["customer", "farmer_seller", "enumerator", "nisr", "admin"];
async function patchUser(id, body) {
  try { await api(`/api/admin/users/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); loadAdmin(); }
  catch (e) { alert(e.message); loadAdmin(); }
}
async function loadUsers() {
  const f = $("userFilter").value;
  const users = await api("/api/admin/users" + (f ? "?status=" + f : ""));
  $("userEmpty").hidden = users.length > 0;
  setRows("userTable", users.map((u) => {
    const sel = el("select", { "aria-label": `Role for ${u.email}`, onchange: (e) => patchUser(u.id, { role: e.target.value }) });
    USER_ROLES.forEach((r) => { const o = el("option", { value: r, text: ROLE_NOTE[r] }); o.selected = r === u.role; sel.append(o); });
    const acts = [];
    if (u.status === "pending") acts.push(el("button", { class: "primary", type: "button", text: "Approve", onclick: () => patchUser(u.id, { status: "active" }) }));
    if (u.status === "active") acts.push(el("button", { type: "button", text: "Disable", onclick: () => patchUser(u.id, { status: "disabled" }) }));
    if (u.status === "disabled") acts.push(el("button", { type: "button", text: "Reactivate", onclick: () => patchUser(u.id, { status: "active" }) }));
    return el("tr", {}, td(u.full_name || "-"), td(u.email), td(u.organisation || "-"), el("td", {}, sel),
      td(u.status === "pending" ? "Waiting for approval" : u.status === "active" ? "Active" : "Disabled"), el("td", {}, ...acts));
  }));
}
$("userFilter").addEventListener("change", loadUsers);

async function loadAdmin() {
  if (!can("review_prices")) return;
  loadUsers();
  const pending = await api("/api/admin/pending");
  $("pendingEmpty").hidden = pending.length > 0;
  setRows("pendingTable", pending.map((r) => {
    const act = (action) => async () => {
      let body = { action, note: prompt("Note (optional)") || null };
      if (action === "correct") { const v = parseInt(prompt("Corrected price (RWF)"), 10); if (!v) return; body.new_price_rwf = v; }
      try { await api(`/api/admin/observations/${r.id}/review`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); loadAdmin(); }
      catch (e) { alert(e.message); }
    };
    return el("tr", {}, td(r.observed_on), td(r.product), td(r.market), td(r.price_rwf.toLocaleString() + " / " + r.unit, "num"),
      el("td", {}, el("button", { class: "primary", text: "Approve", onclick: act("approve") }), " ",
        el("button", { text: "Correct", onclick: act("correct") }), " ", el("button", { text: "Reject", onclick: act("reject") })));
  }));
  const alerts = await api("/api/admin/alerts");
  $("alertList").replaceChildren(...alerts.filter((a) => a.status === "open").map((a) => el("li", { text: a.message })));
  const audit = await api("/api/admin/audit");
  setRows("auditTable", audit.map((a) => el("tr", {}, td(a.at.slice(0, 16).replace("T", " ")), td(a.observation_id), td(a.action),
    td(a.old_price_rwf ?? ""), td(a.new_price_rwf ?? ""), td(a.note || ""))));
}


// ---- Sources
async function loadSources() {
  const s = await api("/api/sources"); const box = $("sourceList"); box.replaceChildren();
  s.forEach((x) => box.append(el("div", { class: "flag", style: x.is_synthetic ? "" : "background:transparent;border:1px solid var(--line);color:inherit" },
    el("b", { text: x.name + (x.is_synthetic ? " (SYNTHETIC DEMO)" : "") }),
    el("div", { text: `Publisher: ${x.publisher}${x.period ? " | Period: " + x.period : ""}${x.downloaded_on ? " | Downloaded: " + x.downloaded_on : ""}` }),
    el("div", { text: x.description || "" }), el("div", { text: x.transformations ? "Processing: " + x.transformations : "" }))));
}


// ---- Compare and map: overall colours, or one product compared across districts and markets
const SVG_NS = "http://www.w3.org/2000/svg";
const STATUS_TEXT = { critical: "Critical zone (red)", medium: "Medium (yellow)", good: "Good (green)",
  limited_data: "Limited data (grey)", no_data: "No verified data (grey)" };
let mapGeo = null, mapData = null, mapProduct = null;

let mapRequest = 0;
async function loadMap(productId) {
  const reqId = ++mapRequest;
  try {
    if (!mapGeo) mapGeo = await fetch("/static/data/rwanda_districts.geojson").then((r) => r.json());
    const pid = productId ? +productId : null;
    const data = await api("/api/districts/status" + (pid ? "?product_id=" + pid : ""));
    if (reqId !== mapRequest) return; // a newer choice was made while this one was loading
    mapProduct = pid;
    mapData = data;
    renderMap();
  } catch (e) { $("mapBox").replaceChildren(el("p", { class: "err", text: "Could not load map: " + e.message })); }
}
function buildTable(heads, rows) {
  return el("div", { class: "tablewrap" }, el("table", {},
    el("thead", {}, el("tr", {}, ...heads.map((h) => el("th", { class: h.num ? "num" : "", text: h.label })))),
    el("tbody", {}, ...rows)));
}
function renderMap() {
  const t = mapData.thresholds;
  const name = products.find((p) => p.id === mapProduct);
  $("mapLead").textContent = mapProduct
    ? `Comparing ${name ? name.name : "the product"} across districts. Each colour shows how that district's latest verified price compares with the national median for this product.`
    : "Each district is coloured by how its verified food prices compare with the national median for the same products. Choose a product above to compare districts.";
  $("cReset").hidden = !mapProduct;
  $("legend").replaceChildren(
    el("span", { class: "item" }, el("span", { class: "sw critical" }), `Critical zone (red): more than ${t.red_above_pct}% above the national median`),
    el("span", { class: "item" }, el("span", { class: "sw medium" }), `Medium (yellow): ${t.yellow_above_pct}% to ${t.red_above_pct}% above`),
    el("span", { class: "item" }, el("span", { class: "sw good" }), `Good (green): up to ${t.yellow_above_pct}% above`),
    el("span", { class: "item" }, el("span", { class: "sw nodata" }), mapProduct ? "Grey: no verified price for this product in the district" : `Grey: no verified data, or fewer than ${t.min_products} products`));

  const pts = mapGeo.features.flatMap((f) => (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates)
    .flatMap((poly) => poly.flat()));
  const minX = Math.min(...pts.map((p) => p[0])), maxX = Math.max(...pts.map((p) => p[0]));
  const minY = Math.min(...pts.map((p) => p[1])), maxY = Math.max(...pts.map((p) => p[1]));
  const kx = Math.cos(((minY + maxY) / 2) * Math.PI / 180);
  const W = (maxX - minX) * kx, H = maxY - minY, pad = 0.02 * Math.max(W, H);
  const project = ([lon, lat]) => [(lon - minX) * kx + pad, maxY - lat + pad];
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W + 2 * pad} ${H + 2 * pad}`);
  const byName = Object.fromEntries(mapData.districts.map((d) => [d.name, d]));
  mapGeo.features.forEach((f) => {
    const dname = f.properties.name, d = byName[dname] || { status: "no_data" };
    const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
    const dAttr = polys.map((poly) => poly.map((ring) => "M" + ring.map((c) => project(c).map((v) => v.toFixed(4)).join(" ")).join("L") + "Z").join("")).join("");
    const p = document.createElementNS(SVG_NS, "path");
    p.setAttribute("d", dAttr);
    p.setAttribute("class", `district status-${d.status}`);
    p.setAttribute("tabindex", "0");
    p.setAttribute("role", "button");
    p.dataset.name = dname;
    p.setAttribute("aria-label", `${dname}: ${STATUS_TEXT[d.status]}` + (d.index_pct !== null && d.index_pct !== undefined ? `, ${fmtPct(d.index_pct)} vs national median` : ""));
    const open = () => showDistrict(dname);
    p.addEventListener("click", open);
    p.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
    const title = document.createElementNS(SVG_NS, "title"); title.textContent = `${dname}: ${STATUS_TEXT[d.status]}`;
    p.append(title);
    svg.append(p);
  });
  $("mapBox").replaceChildren(svg);
  renderTable();
  $("mapNote").textContent = mapData.note + (mapData.contains_synthetic ? " DEMO DATA: colours include synthetic demo prices." : "")
    + (mapData.as_of ? ` Latest verified price date: ${mapData.as_of}.` : "")
    + " District boundaries: geoBoundaries, CC BY 4.0 (www.geoboundaries.org).";
}
// Horizontal bars for one product: the latest verified price per market, in one unit only.
// Bar length is the price as a share of the highest price; bar colour is the district's colour on the map.
function barChart(rows, product) {
  const unit = product.standard_unit;
  const same = rows.filter(({ x }) => x.unit === unit && x.product === product.name)
    .sort((a, b) => a.x.price_rwf - b.x.price_rwf);
  if (!same.length) return el("div", {});
  const max = same[same.length - 1].x.price_rwf, cheapest = same[0].x.price_rwf;
  const dates = [...new Set(same.map(({ x }) => x.observed_on).filter(Boolean))].sort();
  const dateText = dates.length === 1
    ? `All these prices were taken at the same time, on ${dates[0]}.`
    : dates.length > 1
      ? `These prices were taken on different dates (${dates[0]} to ${dates[dates.length - 1]}), so they do not all describe the same time.`
      : "";
  return el("section", { class: "bars", "aria-label": `${product.name} price comparison` },
    el("h3", { text: `${product.name} - price per ${unit}` }),
    ...same.map(({ d, x }) => {
      const diff = x.price_rwf === cheapest ? "cheapest" : fmtPct((x.price_rwf - cheapest) / cheapest * 100);
      return el("div", { class: "bar-row" },
        el("span", { class: "bar-label", text: `${x.market} (${d.name})` }),
        el("span", { class: "bar-track", role: "img", "aria-label": `${x.market}: ${x.price_rwf.toLocaleString()} RWF` },
          el("span", { class: `bar-fill status-${d.status}`, style: `width:${(x.price_rwf / max * 100).toFixed(1)}%` })),
        el("span", { class: "bar-value", text: `${x.price_rwf.toLocaleString()} RWF (${diff})` }));
    }),
    el("p", { class: "bar-note", text: `Only one unit is compared: ${unit}. ${dateText} These are local market observations collected for this app, not original NISR CPI statistics. Bar colours match the district colours on the map.` }));
}
function renderTable() {
  const box = $("tableBox");
  if (mapProduct) {
    const product = products.find((p) => p.id === mapProduct) || { name: "this product", standard_unit: "" };
    const pname = product.name;
    const rows = [];
    mapData.districts.forEach((d) => d.details.forEach((x) => rows.push({ d, x })));
    rows.sort((a, b) => a.x.price_rwf - b.x.price_rwf);
    $("tableTitle").textContent = `${pname}: price in each district, cheapest first`;
    if (!rows.length) { box.replaceChildren(el("p", { class: "muted", text: "No verified prices for this product yet." })); return; }
    const tr = rows.map(({ d, x }) => {
      const r = el("tr", { class: "dist-row", "data-name": d.name, tabindex: "0" },
        td(d.name), td(x.market), td(x.price_rwf.toLocaleString() + " RWF", "num"),
        td(fmtPct(x.deviation_pct), "num " + pctClass(x.deviation_pct)),
        el("td", {}, el("span", { class: `chip ${d.status}`, text: d.status_label })));
      r.addEventListener("click", () => showDistrict(d.name));
      r.addEventListener("keydown", (e) => { if (e.key === "Enter") showDistrict(d.name); });
      return r;
    });
    const without = mapData.districts.filter((d) => d.products_used === 0).map((d) => d.name);
    box.replaceChildren(
      barChart(rows, product),
      el("p", { text: `Cheapest: ${rows[0].x.market} (${rows[0].d.name}) at ${rows[0].x.price_rwf.toLocaleString()} RWF. National median: ${rows[0].x.national_median_rwf.toLocaleString()} RWF.` }),
      buildTable([{ label: "District" }, { label: "Market" }, { label: "Price", num: true }, { label: "Vs national median", num: true }, { label: "Status" }], tr),
      el("p", { class: "muted", text: without.length ? `No verified price for ${pname} yet in: ${without.join(", ")}.` : "" }));
  } else {
    $("tableTitle").textContent = "All 30 districts";
    const rows = [...mapData.districts].sort((a, b) => a.name.localeCompare(b.name)).map((d) => {
      const tr = el("tr", { class: "dist-row", "data-name": d.name, tabindex: "0" },
        td(d.name), el("td", {}, el("span", { class: `chip ${d.status}`, text: d.status_label })),
        td(d.index_pct === null ? "n/a" : fmtPct(d.index_pct), "num"), td(d.products_used, "num"),
        td(d.markets.length ? d.markets.join(", ") : "none yet"));
      tr.addEventListener("click", () => showDistrict(d.name));
      tr.addEventListener("keydown", (e) => { if (e.key === "Enter") showDistrict(d.name); });
      return tr;
    });
    box.replaceChildren(buildTable([{ label: "District" }, { label: "Status" }, { label: "Vs national median", num: true },
      { label: "Products", num: true }, { label: "Markets with data" }], rows));
  }
}
function showDistrict(name) {
  const d = mapData.districts.find((x) => x.name === name); if (!d) return;
  document.querySelectorAll("#mapBox path.district").forEach((p) => p.classList.toggle("selected", p.dataset.name === name));
  const box = $("districtInfo"); box.replaceChildren(
    el("h2", { text: name }),
    el("p", {}, el("span", { class: `chip ${d.status}`, text: d.status_label })));
  if (d.index_pct !== null) {
    box.append(el("p", { text: `Average difference from the national median: ${fmtPct(d.index_pct)} across ${d.products_used} ${d.products_used === 1 ? "product" : "products"}.` }));
    box.append(el("p", { class: "muted", text: `Markets with verified prices: ${d.markets.join(", ")}. Latest verified date: ${d.latest_date}.` }));
    const ul = el("ul", {});
    d.details.forEach((p) => ul.append(el("li", { text: `${p.product} at ${p.market}: ${p.price_rwf.toLocaleString()} RWF (national median ${p.national_median_rwf.toLocaleString()} RWF, ${fmtPct(p.deviation_pct)})` })));
    box.append(ul);
  } else {
    box.append(el("p", { class: "muted", text: "No verified market prices for this district yet, so it cannot be coloured. Grey is not a judgement." }));
  }
  if (d.contains_synthetic) box.append(el("div", { class: "flag", text: "DEMO DATA: these prices are synthetic examples." }));
  box.append(el("p", { class: "muted", text: `Bands: green up to ${mapData.thresholds.yellow_above_pct}% above the national median, yellow up to ${mapData.thresholds.red_above_pct}%, red above that.` }));
}
$("cApply").addEventListener("click", () => loadMap($("cProduct").value));
$("cReset").addEventListener("click", () => { $("cProduct").value = ""; loadMap(null); });

// ---- IsokoBot chat (answers come from the server; text is always inserted as text, never as HTML)
const chatLog = () => $("chatLog");
function chatMsg(role, text, sources) {
  const m = el("div", { class: "msg " + role, text });
  if (sources && sources.length) m.append(el("span", { class: "src", text: "Sources: " + sources.join("; ") }));
  chatLog().append(m); chatLog().scrollTop = chatLog().scrollHeight;
}
function setChips(list) {
  const box = $("chatChips"); box.replaceChildren();
  (list || []).forEach((q) => box.append(el("button", { type: "button", class: "chip-q", text: q, onclick: () => askBot(q) })));
}
let lastForecast = null;  // the last forecast IsokoBot gave, so follow-up questions can refer to it
async function askBot(text) {
  if (!text || !text.trim()) return;
  chatMsg("user", text);
  try {
    const r = await api("/api/chat", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, context: lastForecast }) });
    chatMsg("bot", r.reply, r.sources);
    lastForecast = r.context || null;
    if (r.choices && r.choices.length) chatChoices(r.choices);
    setChips(r.suggestions);
  } catch (e) { chatMsg("bot", "Sorry, IsokoBot could not answer right now: " + e.message); }
}
// Yes / No buttons. "Yes" asks the suggested question; "No" asks the person to rephrase. Buttons disable after use.
function chatChoices(choices) {
  const group = el("div", { class: "chat-choices", role: "group", "aria-label": "Choose an answer" });
  choices.forEach((c) => group.append(el("button", { type: "button", class: "chip-q", text: c.label, onclick: () => {
    group.querySelectorAll("button").forEach((b) => (b.disabled = true));
    if (c.ask) askBot(c.ask);
    else { chatMsg("user", c.label); chatMsg("bot", "No problem. Please rephrase your question, or pick one of the suggestions below."); }
  } })));
  chatLog().append(group); chatLog().scrollTop = chatLog().scrollHeight;
}
let chatStarted = false;
function openChat(open) {
  $("chatPanel").hidden = !open; $("chatFab").setAttribute("aria-expanded", String(open));
  if (open) {
    $("chatInput").focus();
    if (!chatStarted) { chatStarted = true; askBot("help"); }
  }
}
// ---- Movable "Ask IsokoBot" button: drag it, or move it with the arrow keys.
(function makeChatFabMovable() {
  const fab = $("chatFab");
  const KEY = "isoko.chatFabPos";
  const MARGIN = 8;
  let startX = 0, startY = 0, originLeft = 0, originTop = 0, dragging = false, moved = false;

  function clamp(left, top) {
    const maxLeft = window.innerWidth - fab.offsetWidth - MARGIN;
    const maxTop = window.innerHeight - fab.offsetHeight - MARGIN;
    return { left: Math.min(Math.max(left, MARGIN), Math.max(maxLeft, MARGIN)),
             top: Math.min(Math.max(top, MARGIN), Math.max(maxTop, MARGIN)) };
  }
  function place(left, top) {
    const p = clamp(left, top);
    fab.style.left = p.left + "px";
    fab.style.top = p.top + "px";
    fab.style.right = "auto";
    fab.style.bottom = "auto";
    return p;
  }
  function save(p) {
    try { localStorage.setItem(KEY, JSON.stringify(p)); } catch (e) { /* private window: the position is just not remembered */ }
  }
  function restore() {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY) || "null");
      if (saved && Number.isFinite(saved.left) && Number.isFinite(saved.top)) place(saved.left, saved.top);
    } catch (e) { /* a bad or unavailable saved position is ignored */ }
  }

  fab.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;  // left mouse button, or touch and pen
    const r = fab.getBoundingClientRect();
    startX = e.clientX; startY = e.clientY;
    originLeft = r.left; originTop = r.top;
    dragging = true; moved = false;
    fab.setPointerCapture(e.pointerId);
  });
  fab.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const dx = e.clientX - startX, dy = e.clientY - startY;
    if (!moved && Math.hypot(dx, dy) < 6) return;  // tiny movements still count as a click
    moved = true;
    save(place(originLeft + dx, originTop + dy));
  });
  fab.addEventListener("pointerup", () => { dragging = false; });
  fab.addEventListener("pointercancel", () => { dragging = false; moved = false; });
  fab.addEventListener("click", (e) => {
    if (moved) { e.preventDefault(); e.stopImmediatePropagation(); moved = false; return; }  // the press was a drag
    openChat($("chatPanel").hidden);
  });
  fab.addEventListener("keydown", (e) => {
    const step = e.shiftKey ? 40 : 10;
    const moves = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (!moves[e.key]) return;
    e.preventDefault();
    const r = fab.getBoundingClientRect();
    save(place(r.left + moves[e.key][0], r.top + moves[e.key][1]));
  });
  window.addEventListener("resize", () => {
    if (!fab.style.left) return;  // never moved: keep the default corner
    const r = fab.getBoundingClientRect();
    save(place(r.left, r.top));
  });
  restore();
})();

function setChatMaximised(on) {
  $("chatPanel").classList.toggle("maximized", on);
  $("chatMax").textContent = on ? "Restore" : "Maximise";
  $("chatMax").setAttribute("aria-pressed", String(on));
  $("chatMax").setAttribute("aria-label", on ? "Restore chat size" : "Maximise chat");
  $("chatInput").focus();
}
$("chatMax").addEventListener("click", () => setChatMaximised(!$("chatPanel").classList.contains("maximized")));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && $("chatPanel").classList.contains("maximized")) setChatMaximised(false);
});
$("chatClose").addEventListener("click", () => { openChat(false); $("chatFab").focus(); });
$("chatForm").addEventListener("submit", (e) => { e.preventDefault(); const v = $("chatInput").value; $("chatInput").value = ""; askBot(v); });

// ---- Init
(async function init() {
  try {
    products = await api("/api/products"); const markets = await api("/api/markets");
    fillSelect($("fProduct"), products, (p) => p.name, "All"); fillSelect($("cProduct"), products, (p) => p.name, "All products (overall colours)");
    fillSelect($("sProduct"), products, (p) => p.name);
    fillSelect($("fMarket"), markets, (m) => `${m.name} (${m.district})`, "All"); fillSelect($("sMarket"), markets, (m) => `${m.name} (${m.district})`);
    if (products[0]) $("sUnit").textContent = products[0].standard_unit;
    $("sDate").max = new Date().toISOString().slice(0, 10);
    await loadSession(); await loadOverview(); await loadPrices();
  } catch (e) { document.getElementById("main").prepend(el("p", { class: "err", text: "Could not load data: " + e.message })); }
})();
