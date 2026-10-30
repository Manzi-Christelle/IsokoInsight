# Access control

Roles and permissions are defined once in `app/permissions.py` and enforced on the server with
`require_permission(...)` (`app/security.py`). The web page only hides tabs. It is never the only check.

## Roles

| Role | Description | Sign-up | Account status at creation |
|---|---|---|---|
| `customer` | Buyers and people following food prices | Public | Active |
| `farmer_seller` | Farmers and sellers who report prices | Public | Active |
| `enumerator` | Field data collectors recording market prices | Public, then approval | Pending |
| `nisr` | NISR statisticians: data export and statistics | Public, then approval | Pending |
| `admin` | Platform administrators | Not possible (seed command only) | Active |

Account statuses: `pending` (cannot sign in), `active`, `disabled` (cannot sign in and existing sessions are refused).

## Permissions by role

| Capability | Public (not signed in) | Customer | Farmer / seller | Enumerator | NISR | Admin |
|---|---|---|---|---|---|---|
| Dashboard, verified prices, compare, district map, IsokoBot, weather and climate, controbute, sources | Yes | Yes | Yes | Yes | Yes | Yes |
| Download verified prices (CSV) | No | Yes | Yes | Yes | Yes | Yes |
| Submit market prices | No | No | Yes | Yes | No | Yes |
| See status of own submissions | No | No | Yes | Yes | No | Yes |
| Export full dataset (incl. pending and rejected, no submitter identities) | No | No | No | No | Yes | Yes |
| Generate statistics | No | No | No | No | Yes | Yes |
| Verify, correct, reject prices | No | No | No | No | No | Yes |
| Approve, disable, change roles of accounts | No | No | No | No | No | Yes |
| Import NISR CPI files | No | No | No | No | No | Yes |
| See the audit trail | No | No | No | No | No | Yes |

## Safeguards
- Passwords are hashed with PBKDF2-SHA256 (240,000 iterations).
- Administrators cannot disable or demote their own account.
- Administrators cannot be created through public sign-up. The sign-up endpoint rejects `role: admin`.
- A disabled account is refused on its next request, even with a token issued earlier.
- Statistics and exports use verified records only, except the full export for NISR, which is marked by status.
- Submitter identities are never included in the NISR export.

## Tests
`tests/test_access.py` covers each role's allowed and refused actions, approval, self-lock-out protection,
disabled accounts, and the database upgrade.
