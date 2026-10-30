from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..permissions import AUTO_APPROVED, ROLE_LABELS, permissions_for
from ..schemas import AuthOut, RegisterIn
from ..security import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """Create an account. Customers and farmers/sellers are approved at once; enumerators and
    NISR staff wait for an administrator. Administrators are created only by the seed command."""
    email = body.email.lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(409, "Email already registered")
    approved = body.role in AUTO_APPROVED
    user = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name.strip(),
                organisation=(body.organisation or None), role=body.role,
                status="active" if approved else "pending")
    db.add(user)
    db.commit()
    if approved:
        return AuthOut(access_token=create_token(user), role=user.role, status="active",
                       message="Account created. You are now signed in.")
    return AuthOut(access_token=None, role=user.role, status="pending",
                   message=f"Account created as {ROLE_LABELS[user.role]}. An administrator must approve it "
                           "before you can sign in. You will be able to sign in once it is approved.")


@router.post("/login", response_model=AuthOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=form.username.lower()).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    if user.status == "pending":
        raise HTTPException(403, "Your account is awaiting administrator approval.")
    if user.status == "disabled":
        raise HTTPException(403, "This account has been disabled. Contact an administrator.")
    return AuthOut(access_token=create_token(user), role=user.role, status=user.status)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "full_name": user.full_name,
            "organisation": user.organisation, "role": user.role,
            "role_label": ROLE_LABELS.get(user.role, user.role), "status": user.status,
            "permissions": sorted(permissions_for(user.role))}
