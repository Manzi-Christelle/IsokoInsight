"use strict";
// Sign in and sign up. The token is kept for this browser session only, and the server checks the role on every request.
const $ = (id) => document.getElementById(id);
const ROLE_NOTES = {
  customer: "You can sign in straight away.",
  farmer_seller: "You can sign in straight away and submit market prices for verification.",
  enumerator: "An administrator must approve this account before you can sign in.",
  nisr: "An administrator must approve this account before you can sign in. Please enter your NISR organisation.",
};
const NEEDS_ORG = ["enumerator", "nisr"];

function showMsg(id, text, ok) {
  const m = $(id); m.textContent = text; m.className = ok ? "ok" : "err";
}
function saveSession(r) {
  try {
    sessionStorage.setItem("isoko_token", r.access_token);
    sessionStorage.setItem("isoko_role", r.role);
  } catch (e) { /* storage blocked: the user can still sign in for this page visit */ }
}
async function post(path, body) {
  const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  let data = {}; try { data = await res.json(); } catch (e) {}
  if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Something went wrong. Please try again.");
  return data;
}
function syncRole() {
  const role = $("sRole").value;
  const needsOrg = NEEDS_ORG.includes(role);
  $("orgLabel").hidden = !needsOrg;
  $("sOrg").required = role === "nisr";
  $("roleNote").textContent = ROLE_NOTES[role];
}
$("sRole").addEventListener("change", syncRole);
syncRole();

$("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = new URLSearchParams({ username: $("lEmail").value.trim(), password: $("lPass").value });
  try {
    const res = await fetch("/api/auth/login", { method: "POST", body });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Sign-in failed.");
    saveSession(data);
    showMsg("loginMsg", "Signed in. Opening the dashboard...", true);
    window.location.href = "/dashboard";
  } catch (err) { showMsg("loginMsg", err.message, false); }
});

$("signupForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const role = $("sRole").value;
  const body = { full_name: $("sName").value.trim(), email: $("sEmail").value.trim(), password: $("sPass").value, role };
  if (NEEDS_ORG.includes(role) && $("sOrg").value.trim()) body.organisation = $("sOrg").value.trim();
  try {
    const r = await post("/api/auth/register", body);
    if (r.access_token) {
      saveSession(r);
      showMsg("signupMsg", r.message, true);
      window.location.href = "/dashboard";
    } else {
      showMsg("signupMsg", r.message, true);
      $("signupForm").reset(); syncRole();
    }
  } catch (err) { showMsg("signupMsg", err.message, false); }
});
