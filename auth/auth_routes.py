from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Dict

router = APIRouter(prefix="/auth", tags=["auth"])

# TEMP in-memory users (delete later when DB is ready)
_fake_users: Dict[str, str] = {}

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/register")
async def register_user(payload: RegisterRequest):
    email = payload.email.lower()
    if email in _fake_users:
        raise HTTPException(status_code=400, detail="User already exists")

    _fake_users[email] = payload.password

    return {
        "success": True,
        "message": "User registered (TEMP)",
        "email": email,
        "full_name": payload.full_name,
    }

@router.post("/login")
async def login_user(payload: LoginRequest):
    email = payload.email.lower()
    stored = _fake_users.get(email)

    if stored is None or stored != payload.password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    fake_token = f"fake-token-for-{email}"

    return {
        "success": True,
        "access_token": fake_token,
        "token_type": "bearer",
        "email": email,
    }

