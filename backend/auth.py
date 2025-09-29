"""
Authentication service for user management
"""
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional
import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from database import get_db, User

# Load environment variables from .env file
load_dotenv()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class AuthService:
    def __init__(self):
        # Auth service now only works with existing database users
        # No default users are created
        pass
    
    def hash_password(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, username: str, household_id: str) -> str:
        """Create a JWT access token"""
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": username,
            "household_id": household_id,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> tuple[str, str]:
        """Verify and decode a JWT token, returns (username, household_id)"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            household_id: str = payload.get("household_id")
            if username is None or household_id is None:
                raise Exception("Invalid token")
            return username, household_id
        except jwt.PyJWTError:
            raise Exception("Invalid token")
    
    def register(self, username: str, password: str, household_id: str, is_admin: bool = False, db: Session = None) -> bool:
        """Register a new user"""
        if db is None:
            db = next(get_db())
            should_close = True
        else:
            should_close = False
            
        try:
            existing_user = db.query(User).filter(User.username == username).first()
            if existing_user:
                raise Exception("Username already exists")
            
            hashed_password = self.hash_password(password)
            new_user = User(
                username=username,
                passwordHash=hashed_password,
                householdId=household_id,
                isAdmin=is_admin
            )
            db.add(new_user)
            db.commit()
            return True
        finally:
            if should_close:
                db.close()
    
    def login(self, username: str, password: str) -> str:
        """Authenticate user and return JWT token"""
        db = next(get_db())
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                raise Exception("Invalid username or password")
            
            # Verify password, with legacy plaintext migration support
            verified = False
            try:
                verified = self.verify_password(password, user.passwordHash)
            except Exception:
                verified = False
            if not verified:
                # Legacy: if stored password isn't a bcrypt hash, allow one-time migration
                stored = user.passwordHash or ""
                is_bcrypt = stored.startswith("$2a$") or stored.startswith("$2b$") or stored.startswith("$2y$")
                if (not is_bcrypt) and (stored == password):
                    # Migrate to bcrypt
                    try:
                        user.passwordHash = self.hash_password(password)
                        db.commit()
                        verified = True
                    except Exception:
                        verified = False
            if not verified:
                raise Exception("Invalid username or password")
            
            # Safety: ensure user has a household_id
            if not getattr(user, 'householdId', None):
                import uuid as _uuid
                user.householdId = f"household_{_uuid.uuid4().hex[:8]}"
                db.commit()
            return self.create_access_token(username, user.householdId)
        finally:
            db.close()
    
    def get_user(self, username: str) -> Optional[Dict]:
        """Get user by username"""
        db = next(get_db())
        try:
            user = db.query(User).filter(User.username == username).first()
            if user:
                return {
                    "username": user.username,
                    "household_id": user.householdId,
                    "created_at": user.createdAt.isoformat() if user.createdAt else None
                }
            return None
        finally:
            db.close()
