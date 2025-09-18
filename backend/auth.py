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
from database import get_db, User

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
    
    def create_access_token(self, username: str) -> str:
        """Create a JWT access token"""
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": username,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> str:
        """Verify and decode a JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise Exception("Invalid token")
            return username
        except jwt.PyJWTError:
            raise Exception("Invalid token")
    
    def register(self, username: str, password: str, db: Session = None) -> bool:
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
                passwordHash=hashed_password
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
            
            if not self.verify_password(password, user.passwordHash):
                raise Exception("Invalid username or password")
            
            return self.create_access_token(username)
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
                    "created_at": user.createdAt.isoformat() if user.createdAt else None
                }
            return None
        finally:
            db.close()
