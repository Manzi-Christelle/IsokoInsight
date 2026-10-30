"""Roles and what each role may do. Every check is made on the server, never only in the page.

Roles
  customer       - buys or follows food prices. Reads the dashboard and downloads verified prices.
  farmer_seller  - farmers and sellers who report prices. Submits prices and sees the status of their own.
  enumerator     - field data collectors who record market prices for the statistics team.
  nisr           - NISR statisticians. Full dataset export (including pending and rejected records) and
                   statistics generation.
  admin          - runs the platform: verifies prices, imports CPI, manages accounts, sees the audit trail.

Sign-up: customers and farmers/sellers are approved at once. Enumerators and NISR staff are created as
"pending" and cannot sign in until an administrator approves them. Administrators are never self-registered.
"""

ROLE_LABELS = {
    "customer": "Customer",
    "farmer_seller": "Farmer / seller",
    "enumerator": "Enumerator (field data collector)",
    "nisr": "NISR statistician",
    "admin": "Administrator",
}

SELF_REGISTRABLE = ("customer", "farmer_seller", "enumerator", "nisr")
AUTO_APPROVED = ("customer", "farmer_seller")

PERMISSION_LABELS = {
    "download_verified_csv": "download verified prices",
    "submit_price": "submit market prices",
    "view_own_submissions": "see the status of your own submissions",
    "export_full_dataset": "export the full dataset, including pending and rejected records",
    "view_statistics": "generate statistics",
    "review_prices": "verify, correct or reject prices",
    "manage_users": "approve and manage accounts",
    "import_cpi": "import NISR CPI files",
    "view_audit": "see the audit trail",
}

_BASE = {"download_verified_csv"}
_FIELD = _BASE | {"submit_price", "view_own_submissions"}
_NISR = _BASE | {"export_full_dataset", "view_statistics"}
_ADMIN = set(PERMISSION_LABELS)

ROLE_PERMISSIONS = {
    "customer": _BASE,
    "farmer_seller": _FIELD,
    "enumerator": _FIELD,
    "nisr": _NISR,
    "admin": _ADMIN,
}


def permissions_for(role: str) -> set[str]:
    return set(ROLE_PERMISSIONS.get(role, set()))


def denied_message(permission: str, role: str) -> str:
    label = ROLE_LABELS.get(role, role)
    return f"Your role ({label}) cannot {PERMISSION_LABELS.get(permission, permission)}."
