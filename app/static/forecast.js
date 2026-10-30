"use strict";
(function () {
  let chart = null, started = false;
  const UNIT_LABEL = { rain: "Rainfall (mm per month)", temp: "Temperature (°C)" };
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const TESTED_MONTHS = 6;  // the backtest covers months 1 to 6 only
  const monthName = (y, m) => `${MONTHS[m - 1]} ${y}`;
  const fmt = (v) => (v === null || v === undefined ? "n/a" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 1 }));

  async function init() {
    if (started) return;
    started = true;
    try {
      const status = await api("/api/climate/status");
      const names = status.districts.map((d) => d.name).sort((a, b) => a.localeCompare(b));
      const select = $("fcDistrict");
      select.replaceChildren(...names.map((n) => el("option", { value: n, text: n })));
      select.value = names.includes("Musanze") ? "Musanze" : names[0];
      ["fcDistrict", "fcVariable", "fcHorizon"].forEach((id) => $(id).addEventListener("change", refresh));
      await refresh();
    } catch (e) {
      $("fcNote").textContent = "Could not load the forecast panel: " + e.message;
    }
  }

  async function refresh() {
    const district = $("fcDistrict").value, variable = $("fcVariable").value, horizon = $("fcHorizon").value;
    try {
      const f = await api(`/api/forecast/climate?district=${encodeURIComponent(district)}&variable=${variable}&horizon=${horizon}`);
      render(f);
    } catch (e) {
      $("fcNote").textContent = "Could not load the forecast: " + e.message;
    }
  }

  function render(f) {
    const n = f.forecast.length;
    const last = f.forecast[n - 1];
    $("fcLabel").textContent = f.label;
    $("fcLead").textContent = `${UNIT_LABEL[f.variable]} for ${f.district}: the last 24 months of synthetic data, then a forecast to ${monthName(last.year, last.month)}. Method: ${f.method}.`;
    drawChart(f);
    $("fcTable").replaceChildren(buildForecastTable(f));
    $("fcBacktest").replaceChildren(f.backtest_table ? buildBacktestTable(f) : el("p", { class: "muted", text: "The backtest has not been run yet. Run python -m app.ml.forecast_climate to create it." }));
    const base = f.backtest_table
      ? `${f.method_note} Backtest: ${f.backtest_origins} forecast origins for this measure, generated ${f.backtest_generated_on}. A method is only useful where its error is lower than the climatology baseline. Source: ${f.source}.`
      : `${f.method_note} Source: ${f.source}.`;
    const beyond = n > TESTED_MONTHS
      ? " Ranges are shown only for the first 6 months, the period the backtest tested. Later values only continue the smoothed seasonal pattern. They are not a projection of climate change."
      : "";
    $("fcNote").textContent = base + beyond;
  }

  function drawChart(f) {
    const hist = f.history.map((h) => h.value);
    const labels = [...f.history.map((h) => monthName(h.year, h.month)), ...f.forecast.map((p) => monthName(p.year, p.month))];
    const lastHist = hist[hist.length - 1];
    const data = {
      labels,
      datasets: [
        { label: "History (synthetic)", data: [...hist, ...Array(f.forecast.length).fill(null)], borderColor: "#1d4f7c", backgroundColor: "#1d4f7c", pointRadius: 2, tension: 0.25 },
        { label: "Forecast", data: [...Array(f.history.length - 1).fill(null), lastHist, ...f.forecast.map((p) => p.point)],
          borderColor: "#0b5ea8", borderDash: [6, 4], backgroundColor: "#0b5ea8", pointRadius: f.forecast.length > 24 ? 0 : 3, tension: 0.25 },
        { label: "Lower 80% range", data: f.forecast[0].lower80 === null ? [] : [...Array(f.history.length).fill(null), ...f.forecast.map((p) => p.lower80)],
          borderColor: "transparent", pointRadius: 0, fill: false },
        { label: "80% range", data: f.forecast[0].upper80 === null ? [] : [...Array(f.history.length).fill(null), ...f.forecast.map((p) => p.upper80)],
          borderColor: "transparent", pointRadius: 0, backgroundColor: "rgba(11,94,168,0.15)", fill: "-1" },
      ],
    };
    const options = {
      responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
      scales: { y: { title: { display: true, text: `${f.unit}` } }, x: { ticks: { maxRotation: 60, autoSkip: true, maxTicksLimit: 16 } } },
      plugins: { legend: { labels: { filter: (item) => item.text !== "Lower 80% range" } },
        tooltip: { callbacks: { label: (c) => c.dataset.label + ": " + fmt(c.parsed.y) + " " + f.unit } } },
    };
    if (chart) chart.destroy();
    chart = new Chart($("fcChart"), { type: "line", data, options });
  }

  function buildForecastTable(f) {
    const n = f.forecast.length;
    // Long forecasts: show the first 12 months, then each December, then the final month, to keep the table short.
    const shown = n <= 24 ? f.forecast : f.forecast.filter((p, i) => i < 12 || p.month === 12 || i === n - 1);
    const rows = shown.map((p) => el("tr", {},
      td(monthName(p.year, p.month)), td(fmt(p.point) + " " + f.unit, "num"),
      td(p.lower80 === null ? "no tested range" : `${fmt(p.lower80)} to ${fmt(p.upper80)} ${f.unit}`, "num")));
    const table = buildTable([{ label: "Month" }, { label: "Forecast", num: true }, { label: "80% range", num: true }], rows);
    if (n <= 24) return table;
    return el("div", {}, el("p", { class: "muted", text: "Showing the first 12 months, then each December, and the final month." }), table);
  }

  function buildBacktestTable(f) {
    const rows = f.backtest_table.map((r) => el("tr", {},
      td("Month " + r.horizon, ""), td(fmt(r.holt_winters_mae) + " " + f.unit, "num"),
      td(fmt(r.seasonal_naive_mae) + " " + f.unit, "num"), td(fmt(r.climatology_mae) + " " + f.unit, "num"),
      el("td", {}, el("span", { class: "chip " + (r.beats_climatology ? "good" : "no_data"),
        text: r.beats_climatology ? "Beats baseline" : "Does not beat baseline" }))));
    return buildTable([{ label: "Horizon" }, { label: "Smoothing model error", num: true }, { label: "Seasonal naive error", num: true },
      { label: "Climatology error", num: true }, { label: "Verdict" }], rows);
  }

  const trigger = document.querySelector('#tabs button[data-tab="climate"]');
  if (trigger) trigger.addEventListener("click", init);
})();