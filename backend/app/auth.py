from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .database import User

# JWT ayarları
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7  # 7 gün

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Şifreyi hash'le."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Şifreyi doğrula."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(username: str) -> str:
    """JWT token oluştur."""
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode = {"sub": username, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[str]:
    """JWT token'ı decode et ve username döndür."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        return username
    except jwt.ExpiredSignatureError:
        return None
    except jwt.JWTError:
        return None


def create_user(db: Session, username: str, password: str) -> Optional[User]:
    """Yeni kullanıcı oluştur."""
    # Kullanıcı adı kontrolü
    username = username.strip().lower()
    if not username or len(username) < 3:
        return None
    
    # Kullanıcı zaten var mı?
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return None
    
    # Şifre kontrolü
    password = password.strip()
    if not password or len(password) < 6:
        return None
    
    # Yeni kullanıcı oluştur
    password_hash = hash_password(password)
    db_user = User(
        username=username,
        password_hash=password_hash,
        created_at=datetime.utcnow()
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    """Kullanıcıyı doğrula ve döndür."""
    username = username.strip().lower()
    password = password.strip()
    
    if not username or not password:
        return None
    
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    return user

