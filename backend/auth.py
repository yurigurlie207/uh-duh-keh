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

# Simple in-memory user storage (in production, use a database)
users_db: Dict[str, Dict] = {}

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class AuthService:
    def __init__(self):
        # Create some default users for testing
        self._create_default_users()
    
    def _create_default_users(self):
        """Create default users for testing"""
        default_users = [
            {"username": "mom", "password": "mom123"},
            {"username": "dad", "password": "dad123"},
            {"username": "kid", "password": "kid123"}
        ]
        
        for user in default_users:
            if user["username"] not in users_db:
                self.register(user["username"], user["password"])
    
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
    
    def register(self, username: str, password: str) -> bool:
        """Register a new user"""
        if username in users_db:
            raise Exception("Username already exists")
        
        hashed_password = self.hash_password(password)
        users_db[username] = {
            "username": username,
            "password": hashed_password,
            "created_at": datetime.utcnow().isoformat()
        }
        return True
    
    def login(self, username: str, password: str) -> str:
        """Authenticate user and return JWT token"""
        if username not in users_db:
            raise Exception("Invalid username or password")
        
        user = users_db[username]
        if not self.verify_password(password, user["password"]):
            raise Exception("Invalid username or password")
        
        return self.create_access_token(username)
    
    def get_user(self, username: str) -> Optional[Dict]:
        """Get user by username"""
        return users_db.get(username)
