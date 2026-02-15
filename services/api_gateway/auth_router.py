from typing import Optional
import re
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from shared.models import (
    User, UserCreate, UserProfile, UserPreferences,
    UserRegister, OTPVerifyRequest, OTPResendRequest, LoginRequest, PendingUser,
)
from shared.config import settings
from auth_utils import get_password_hash, verify_password, create_access_token, decode_access_token
from email_utils import generate_otp, send_otp_email
from google.oauth2 import id_token
from google.auth.transport import requests
import uuid
from datetime import datetime, timedelta

logger = logging.getLogger("auth")

ADMIN_EMAILS = {"aanaruna@gmail.com"}

# ─── Password policy (moderate) ──────────────────────────────────
PASSWORD_MIN_LENGTH = 8
PASSWORD_RULES = [
    (r"[A-Z]", "at least one uppercase letter"),
    (r"[a-z]", "at least one lowercase letter"),
    (r"[0-9]", "at least one digit"),
    (r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", "at least one special character"),
]

def validate_password(password: str) -> list[str]:
    """Return list of validation error messages (empty = valid)."""
    errors = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    for pattern, msg in PASSWORD_RULES:
        if not re.search(pattern, password):
            errors.append(f"Password must contain {msg}")
    return errors


router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)

# ─── In-memory stores ────────────────────────────────────────────
users_db: dict[str, User] = {}
pending_users: dict[str, PendingUser] = {}  # email -> PendingUser (awaiting OTP)

async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)):
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    email = payload.get("sub")
    user = users_db.get(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

async def require_admin(user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ─── Registration with OTP ───────────────────────────────────────

@router.post("/register")
async def register(body: UserRegister):
    """Register a new user — sends OTP to email for verification."""
    email = body.email.strip().lower()

    # Already a verified user?
    if email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered. Please login.")

    # Password match
    if body.password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    # Password strength
    pwd_errors = validate_password(body.password)
    if pwd_errors:
        raise HTTPException(status_code=400, detail=pwd_errors)

    # Generate OTP & store pending
    otp = generate_otp()
    now = datetime.utcnow()
    pending_users[email] = PendingUser(
        email=email,
        full_name=body.full_name.strip(),
        hashed_password=get_password_hash(body.password),
        otp=otp,
        otp_created_at=now,
        last_resend_at=now,
    )

    # Send email (non-blocking best-effort)
    sent = send_otp_email(email, otp, body.full_name)
    if not sent:
        logger.warning(f"OTP email dispatch failed for {email}, OTP still stored")

    response = {
        "status": "otp_sent",
        "message": f"Verification code sent to {email}",
        "resend_cooldown_seconds": settings.OTP_RESEND_COOLDOWN_SECONDS,
    }
    # DEV MODE: include OTP in response so it can be shown on-screen
    if settings.ENVIRONMENT == "development":
        response["dev_otp"] = otp
    return response


@router.post("/verify-otp")
async def verify_otp(body: OTPVerifyRequest, request: Request):
    """Verify OTP and finalize registration."""
    email = body.email.strip().lower()
    pending = pending_users.get(email)

    if not pending:
        raise HTTPException(status_code=400, detail="No pending registration for this email. Please register first.")

    # Check expiry
    elapsed = (datetime.utcnow() - pending.otp_created_at).total_seconds()
    if elapsed > settings.OTP_EXPIRE_MINUTES * 60:
        del pending_users[email]
        raise HTTPException(status_code=400, detail="OTP expired. Please register again.")

    if pending.otp != body.otp.strip():
        raise HTTPException(status_code=400, detail="Invalid OTP")

    # Create the real user
    user_id = str(uuid.uuid4())
    login_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "ip": request.client.host if request.client else "unknown",
        "method": "email",
    }
    user = User(
        id=user_id,
        email=email,
        full_name=pending.full_name,
        hashed_password=pending.hashed_password,
        is_admin=email in ADMIN_EMAILS,
        login_history=[login_entry],
    )
    users_db[email] = user
    del pending_users[email]

    access_token = create_access_token(data={"sub": email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "full_name": user.full_name,
            "email": user.email,
            "picture": user.picture,
            "is_admin": user.is_admin,
            "onboarded": user.onboarded,
            "preferences": user.preferences.model_dump() if user.preferences else {},
        },
    }


@router.post("/resend-otp")
async def resend_otp(body: OTPResendRequest):
    """Resend OTP with 30-second cooldown."""
    email = body.email.strip().lower()
    pending = pending_users.get(email)

    if not pending:
        raise HTTPException(status_code=400, detail="No pending registration for this email.")

    # Cooldown check
    since_last = (datetime.utcnow() - pending.last_resend_at).total_seconds()
    if since_last < settings.OTP_RESEND_COOLDOWN_SECONDS:
        remaining = int(settings.OTP_RESEND_COOLDOWN_SECONDS - since_last)
        raise HTTPException(status_code=429, detail=f"Please wait {remaining} seconds before resending.")

    # New OTP
    otp = generate_otp()
    pending.otp = otp
    pending.otp_created_at = datetime.utcnow()
    pending.last_resend_at = datetime.utcnow()

    send_otp_email(email, otp, pending.full_name)
    response = {
        "status": "otp_sent",
        "message": f"New verification code sent to {email}",
        "resend_cooldown_seconds": settings.OTP_RESEND_COOLDOWN_SECONDS,
    }
    # DEV MODE: include OTP in response so it can be shown on-screen
    if settings.ENVIRONMENT == "development":
        response["dev_otp"] = otp
    return response


# ─── Password rules (public, for frontend display) ──────────────

@router.get("/password-rules")
async def password_rules():
    return {
        "min_length": PASSWORD_MIN_LENGTH,
        "rules": [msg for _, msg in PASSWORD_RULES],
    }


# ─── Email/Password Login ────────────────────────────────────────

@router.post("/login")
async def login(body: LoginRequest, request: Request):
    """Login with email and password."""
    email = body.email.strip().lower()
    user = users_db.get(email)
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    login_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "ip": request.client.host if request.client else "unknown",
        "method": "email",
    }
    user.login_history.append(login_entry)
    user.login_history = user.login_history[-50:]

    access_token = create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "full_name": user.full_name,
            "email": user.email,
            "picture": user.picture,
            "is_admin": user.is_admin,
            "onboarded": user.onboarded,
            "preferences": user.preferences.model_dump() if user.preferences else {},
        },
    }


# ─── Legacy signup (kept for backward compat) ────────────────────

@router.post("/signup", response_model=UserProfile)
async def signup(user_in: UserCreate):
    if user_in.email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = get_password_hash(user_in.password)
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=hashed_password,
    )
    users_db[user_in.email] = user
    return user


# ─── Google SSO Login ─────────────────────────────────────────────

class GoogleLoginRequest(BaseModel):
    token: str

@router.post("/google")
async def google_login(request_body: GoogleLoginRequest, request: Request):
    try:
        # Verify the Google token
        idinfo = id_token.verify_oauth2_token(
            request_body.token, requests.Request(), settings.GOOGLE_CLIENT_ID
        )

        # ID token is valid. Get user's Google ID and email.
        google_id = idinfo['sub']
        email = idinfo['email']
        full_name = idinfo.get('name', '')
        picture = idinfo.get('picture', '')

        # Audit entry
        login_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "ip": request.client.host if request.client else "unknown",
            "method": "google"
        }

        # Check if user exists
        user = next((u for u in users_db.values() if u.google_id == google_id or u.email == email), None)
        
        if not user:
            # Create new user for Google login
            user_id = str(uuid.uuid4())
            user = User(
                id=user_id,
                email=email,
                full_name=full_name,
                google_id=google_id,
                picture=picture,
                is_admin=email in ADMIN_EMAILS,
                login_history=[login_entry]
            )
            users_db[email] = user
        else:
            if not user.google_id:
                user.google_id = google_id
            user.picture = picture
            user.full_name = full_name or user.full_name
            user.login_history.append(login_entry)
            # Keep only last 50 logins
            user.login_history = user.login_history[-50:]

        # Generate access token
        access_token = create_access_token(data={"sub": user.email})
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "full_name": user.full_name,
                "email": user.email,
                "picture": user.picture,
                "is_admin": user.is_admin,
                "onboarded": user.onboarded,
                "preferences": user.preferences.model_dump() if user.preferences else {}
            }
        }

    except ValueError:
        # Invalid token
        raise HTTPException(status_code=401, detail="Invalid Google token")
    except Exception as e:
        # Catch google.auth errors, network issues, etc.
        import logging
        logging.getLogger("auth").error(f"Google login error: {e}")
        raise HTTPException(status_code=401, detail="Google authentication failed")

@router.post("/preferences")
async def update_preferences(prefs: UserPreferences, user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user.preferences = prefs
    user.onboarded = True
    return {"status": "success", "preferences": user.preferences}

@router.get("/me", response_model=UserProfile)
async def get_me(user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

@router.get("/login-history")
async def get_login_history(user: User = Depends(get_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"history": user.login_history[-20:]}

# ─── Admin Endpoints ──────────────────────────────────────────────

@router.get("/admin/users")
async def admin_list_users(admin: User = Depends(require_admin)):
    """List all registered users (admin only)."""
    users = []
    for u in users_db.values():
        users.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "picture": u.picture,
            "is_admin": u.is_admin,
            "onboarded": u.onboarded,
            "google_id": u.google_id is not None,
            "login_count": len(u.login_history),
            "last_login": u.login_history[-1]["timestamp"] if u.login_history else None,
            "created_at": u.login_history[0]["timestamp"] if u.login_history else None,
        })
    return users

@router.get("/admin/users/{user_email}/audit")
async def admin_user_audit(user_email: str, admin: User = Depends(require_admin)):
    """Get full audit log for a specific user (admin only)."""
    target = users_db.get(user_email)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "email": target.email,
        "full_name": target.full_name,
        "picture": target.picture,
        "is_admin": target.is_admin,
        "onboarded": target.onboarded,
        "preferences": target.preferences.model_dump() if target.preferences else {},
        "login_history": target.login_history
    }
