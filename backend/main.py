"""
FastAPI application with WebSocket support for todo management
"""
import os
import sys
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the parent directory to the Python path to import common module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

from auth import AuthService
from database import get_db, create_tables, Todo as TodoModel, UserPreferences as UserPreferencesModel, User
from common.events import (
    Todo, UserPreferences, TodoCreateData, TodoUpdateData, 
    TodoToggleData, TodoDeleteData, TodoSetAllData
)

# Database will be used instead of in-memory storage

# Initialize services
auth_service = AuthService()

# Helper function to convert database model to Pydantic model
def db_todo_to_pydantic(db_todo: TodoModel) -> Todo:
    """Convert database Todo model to Pydantic Todo model"""
    return Todo(
        id=db_todo.id,
        title=db_todo.title,
        completed=db_todo.completed,
        priority=db_todo.priority,
        assigned_to=db_todo.assignedTo,
        created_at=db_todo.createdAt.isoformat() if db_todo.createdAt else None,
        updated_at=db_todo.updatedAt.isoformat() if db_todo.updatedAt else None,
        ai_priority=None,  # Column doesn't exist in your database
        ai_reason=None     # Column doesn't exist in your database
    )

security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting FastAPI server with WebSocket support")
    print("📊 Creating database tables...")
    create_tables()
    print("✅ Database tables created successfully")
    yield
    # Shutdown
    print("🛑 Shutting down server")

# Create FastAPI app
app = FastAPI(
    title="Todo Management API",
    description="A todo management system with AI prioritization and WebSocket support",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "User-Agent"],
    expose_headers=["*"],
)

# Socket.IO is now handled by a separate server on port 3002

# Dependency to get current user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        username = auth_service.verify_token(credentials.credentials)
        return username
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

# WebSocket handling is now done by the separate socket_server.py on port 3002

# REST API endpoints
@app.get("/")
async def root():
    return {"message": "Todo Management API with WebSocket support"}

@app.get("/api/todos", response_model=List[Todo])
async def get_todos(current_user: str = Depends(get_current_user)):
    """Get all todos"""
    db = next(get_db())
    try:
        todos = db.query(TodoModel).all()
        return [db_todo_to_pydantic(todo) for todo in todos]
    finally:
        db.close()

@app.post("/api/todos", response_model=Todo)
async def create_todo(todo_data: TodoCreateData, current_user: str = Depends(get_current_user)):
    """Create a new todo via HTTP API"""
    db = next(get_db())
    try:
        todo_model = TodoModel(
            id=str(uuid.uuid4()),
            title=todo_data.title,
            assignedTo=todo_data.assigned_to,
            priority=todo_data.priority or "999"
        )
        db.add(todo_model)
        db.commit()
        db.refresh(todo_model)
        
        todo = db_todo_to_pydantic(todo_model)
        print(f"✅ Created todo via HTTP API: {todo.title}")
        return todo
    finally:
        db.close()

@app.get("/api/users")
async def get_users(current_user: str = Depends(get_current_user)):
    """Get available users from database"""
    db = next(get_db())
    try:
        users = db.query(User).all()
        return [{"username": user.username} for user in users]
    finally:
        db.close()

@app.get("/api/user-preferences", response_model=UserPreferences)
async def get_user_preferences(current_user: str = Depends(get_current_user)):
    """Get user preferences"""
    db = next(get_db())
    try:
        user_prefs = db.query(UserPreferencesModel).filter(UserPreferencesModel.username == current_user).first()
        if user_prefs:
            return UserPreferences(
                pet_care=user_prefs.petCare,
                laundry=user_prefs.laundry,
                cooking=user_prefs.cooking,
                organization=user_prefs.organization,
                plant_care=user_prefs.plantCare,
                house_work=user_prefs.houseWork,
                yard_work=user_prefs.yardWork,
                family_care=user_prefs.familyCare
            )
        return UserPreferences()
    finally:
        db.close()

@app.post("/api/user-preferences")
async def update_user_preferences(
    preferences: UserPreferences,
    current_user: str = Depends(get_current_user)
):
    """Update user preferences"""
    db = next(get_db())
    try:
        user_prefs = db.query(UserPreferencesModel).filter(UserPreferencesModel.username == current_user).first()
        if user_prefs:
            # Update existing preferences
            user_prefs.petCare = preferences.pet_care
            user_prefs.laundry = preferences.laundry
            user_prefs.cooking = preferences.cooking
            user_prefs.organization = preferences.organization
            user_prefs.plantCare = preferences.plant_care
            user_prefs.houseWork = preferences.house_work
            user_prefs.yardWork = preferences.yard_work
            user_prefs.familyCare = preferences.family_care
            user_prefs.updatedAt = datetime.utcnow()
        else:
            # Create new preferences
            user_prefs = UserPreferencesModel(
                username=current_user,
                petCare=preferences.pet_care,
                laundry=preferences.laundry,
                cooking=preferences.cooking,
                organization=preferences.organization,
                plantCare=preferences.plant_care,
                houseWork=preferences.house_work,
                yardWork=preferences.yard_work,
                familyCare=preferences.family_care
            )
            db.add(user_prefs)
        
        db.commit()
        return {"message": "Preferences updated successfully"}
    finally:
        db.close()

# AI endpoints have been completely disabled

# Authentication endpoints
@app.post("/api/auth/login")
async def login(request: Dict[str, str]):
    """User login"""
    username = request.get('username')
    password = request.get('password')
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    
    try:
        token = auth_service.login(username, password)
        return {"token": token, "username": username}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/api/auth/register")
async def register(request: Dict[str, str]):
    """User registration"""
    username = request.get('username')
    password = request.get('password')
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    
    try:
        auth_service.register(username, password)
        return {"message": "User registered successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=3001,
        reload=True,
        log_level="info"
    )
