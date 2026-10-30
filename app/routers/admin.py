from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..importers.cpi import load_cpi, parse_cpi
from ..models import Alert, DataSource, PriceObservation, User, VerificationLog
from ..permissions import ROLE_LABELS
from ..schemas import ReviewIn, UserUpdate
from ..security import require_admin
from .prices import obs_to_dict

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/pending")
def pending(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    rows = (db.query(PriceObservation)
            .options(joinedload(PriceObservation.product), joinedload(PriceObservation.market),
                     joinedload(PriceObservation.source))
            .filter_by(status="pending").order_by(PriceObservation.created_at).all())
    return [obs_to_dict(o) for o in rows]


@router.post("/observations/{obs_id}/review")
def review(obs_id: int, body: ReviewIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    obs = db.get(PriceObservation, obs_id)
    if not obs:
        raise HTTPException(404, "Observation not found")
    if obs.status != "pending":
        raise HTTPException(409, f"Already {obs.status}")
    old = obs.price_rwf
    if body.action == "approve":
        obs.status = "verified"
    elif body.action == "reject":
        obs.status = "rejected"
    else:  # correct
        if not body.new_price_rwf:
            raise HTTPException(422, "new_price_rwf is required to correct an observation")
        obs.price_rwf = body.new_price_rwf
        obs.status = "verified"
    db.add(VerificationLog(observation_id=obs.id, admin_id=admin.id, action=body.action, note=body.note,
                           old_price_rwf=old, new_price_rwf=obs.price_rwf))
    for a in db.query(Alert).filter_by(kind="price_observation", ref=str(obs.id), status="open"):
        a.status = "reviewed"
    db.commit()
    return {"id": obs.id, "status": obs.status}


@router.get("/audit")
def audit(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    rows = db.query(VerificationLog).order_by(VerificationLog.created_at.desc()).limit(200)
    return [{"observation_id": r.observation_id, "admin_id": r.admin_id, "action": r.action,
             "note": r.note, "old_price_rwf": r.old_price_rwf, "new_price_rwf": r.new_price_rwf,
             "at": r.created_at.isoformat()} for r in rows]


@router.get("/alerts")
def alerts(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return [{"id": a.id, "kind": a.kind, "ref": a.ref, "period": a.period.isoformat() if a.period else None,
             "change_pct": a.change_pct, "message": a.message, "status": a.status}
            for a in db.query(Alert).order_by(Alert.created_at.desc()).limit(200)]


@router.post("/import-cpi")
async def import_cpi(name: str, period: str, url: str | None = None, file: UploadFile = File(...),
                     db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Upload the NISR CPI CSV. Records the source in the register with today's download date."""
    raw = await file.read()
    try:
        parsed = parse_cpi(raw)
    except ValueError as e:
        raise HTTPException(422, str(e))
    source = db.query(DataSource).filter_by(name=name).one_or_none()
    if not source:
        source = DataSource(name=name, publisher="National Institute of Statistics of Rwanda (NISR)",
                            url=url, period=period, downloaded_on=date.today(), is_synthetic=False,
                            transformations="Parsed by app/importers/cpi.py: encoding normalised, "
                                            "title/footer rows removed, weights converted to numbers.")
        db.add(source)
        db.flush()
    return load_cpi(db, parsed, source)


def _user_row(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "organisation": u.organisation,
            "role": u.role, "role_label": ROLE_LABELS.get(u.role, u.role), "status": u.status,
            "created_at": u.created_at.isoformat() if u.created_at else None}


@router.get("/users")
def list_users(status: str | None = None, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    q = db.query(User).order_by(User.status != "pending", User.created_at.desc())
    if status:
        q = q.filter_by(status=status)
    return [_user_row(u) for u in q.limit(500)]


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db),
                admin: User = Depends(require_admin)):
    """Approve pending accounts, disable accounts, or change a role. Administrators cannot lock
    themselves out."""
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(404, "User not found")
    if target.id == admin.id and ((body.status and body.status != "active")
                                  or (body.role and body.role != "admin")):
        raise HTTPException(422, "You cannot disable or demote your own account.")
    if body.role is not None:
        target.role = body.role
    if body.status is not None:
        target.status = body.status
    db.commit()
    return _user_row(target)
