import os
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.hash import bcrypt
from fastapi import HTTPException, Depends, Cookie
from typing import Optional

SECRET_KEY = os.environ.get("SECRET_KEY", "ardiyamidly-secret-2024")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

def hash_password(password: str) -> str:
    return bcrypt.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.verify(password, hashed)

def create_token(user_id: int, nama: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "nama": nama, "role": role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token tidak valid")

def get_current_user(token: Optional[str] = Cookie(default=None)):
    if not token:
        raise HTTPException(status_code=401, detail="Belum login")
    return decode_token(token)

def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Akses hanya untuk Admin")
    return user
