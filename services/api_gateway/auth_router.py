from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from shared.models import User, UserCreate, UserProfile, UserPreferences
from shared.config import settings
from auth_utils import get_password_hash, verify_password, create_access_token, decode_access_token
from google.oauth2 import id_token
from google.auth.transport import requests
import uuid
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)

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

# In-memory user store for initial local dev
# In production, this would be a database (PostgreSQL)
users_db = {}

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
        hashed_password=hashed_password
    )
    users_db[user_in.email] = user
    return user

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_db.get(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

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
