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

# Add the parent directory to the Python path to import common module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import socketio
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

from auth import AuthService
from ai_handlers import AIHandlers
from database import get_db, create_tables, Todo as TodoModel, UserPreferences as UserPreferencesModel, User
from common.events import (
    Todo, UserPreferences, TodoCreateData, TodoUpdateData, 
    TodoToggleData, TodoDeleteData, TodoSetAllData
)

# Initialize Socket.IO
sio = socketio.AsyncServer(
    cors_allowed_origins=["http://localhost:3000", "http://localhost:4200"],
    async_mode='asgi'
)

# Database will be used instead of in-memory storage

# Initialize services
auth_service = AuthService()
ai_handlers = AIHandlers()

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
        ai_priority=db_todo.aiPriority,
        ai_reason=db_todo.aiReason
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
    allow_origins=["http://localhost:3000", "http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Mount Socket.IO
app.mount("/", socketio.ASGIApp(sio, app))

# Dependency to get current user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        username = auth_service.verify_token(credentials.credentials)
        return username
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

# WebSocket connection handling
@sio.event
async def connect(sid, environ, auth=None):
    """Handle WebSocket connection"""
    try:
        if auth and 'token' in auth:
            username = auth_service.verify_token(auth['token'])
            print(f"✅ User {username} connected with sid: {sid}")
            await sio.emit('connect', {'message': f'Welcome {username}!'}, room=sid)
        else:
            print(f"❌ Unauthenticated connection attempt from sid: {sid}")
            await sio.disconnect(sid)
    except Exception as e:
        print(f"❌ Connection error: {e}")
        await sio.disconnect(sid)

@sio.event
async def disconnect(sid):
    """Handle WebSocket disconnection"""
    print(f"👋 Client {sid} disconnected")

# Todo WebSocket events
@sio.event
async def todo_create(sid, data):
    """Create a new todo"""
    try:
        todo_data = TodoCreateData(**data)
        db = next(get_db())
        try:
            todo_model = TodoModel(
                id=str(uuid.uuid4()),
                title=todo_data.title,
                assignedTo=todo_data.assigned_to
            )
            db.add(todo_model)
            db.commit()
            db.refresh(todo_model)
            
            # Convert to Pydantic model for response
            todo = db_todo_to_pydantic(todo_model)
            
            await sio.emit('todo:created', todo.dict())
            print(f"✅ Created todo: {todo.title}")
        finally:
            db.close()
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def todo_update(sid, data):
    """Update an existing todo"""
    try:
        update_data = TodoUpdateData(**data)
        db = next(get_db())
        try:
            todo_model = db.query(TodoModel).filter(TodoModel.id == update_data.id).first()
            if not todo_model:
                await sio.emit('error', {'message': 'Todo not found'}, room=sid)
                return
            
            if update_data.title is not None:
                todo_model.title = update_data.title
            if update_data.completed is not None:
                todo_model.completed = update_data.completed
            if update_data.priority is not None:
                todo_model.priority = update_data.priority
            if update_data.assigned_to is not None:
                todo_model.assignedTo = update_data.assigned_to
            
            todo_model.updatedAt = datetime.utcnow()
            
            db.commit()
            db.refresh(todo_model)
            
            # Convert to Pydantic model for response
            todo = db_todo_to_pydantic(todo_model)
            
            await sio.emit('todo:updated', todo.dict())
            print(f"✅ Updated todo: {todo.title}")
        finally:
            db.close()
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def todo_toggle(sid, data):
    """Toggle todo completion status"""
    try:
        toggle_data = TodoToggleData(**data)
        db = next(get_db())
        try:
            todo_model = db.query(TodoModel).filter(TodoModel.id == toggle_data.id).first()
            if not todo_model:
                await sio.emit('error', {'message': 'Todo not found'}, room=sid)
                return
            
            todo_model.completed = not todo_model.completed
            todo_model.updatedAt = datetime.utcnow()
            
            db.commit()
            db.refresh(todo_model)
            
            # Convert to Pydantic model for response
            todo = db_todo_to_pydantic(todo_model)
            
            await sio.emit('todo:updated', todo.dict())
            print(f"✅ Toggled todo: {todo.title} -> {todo.completed}")
        finally:
            db.close()
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def todo_delete(sid, data):
    """Delete a todo"""
    try:
        delete_data = TodoDeleteData(**data)
        db = next(get_db())
        try:
            todo_model = db.query(TodoModel).filter(TodoModel.id == delete_data.id).first()
            if not todo_model:
                await sio.emit('error', {'message': 'Todo not found'}, room=sid)
                return
            
            db.delete(todo_model)
            db.commit()
            
            await sio.emit('todo:deleted', {'id': delete_data.id})
            print(f"✅ Deleted todo: {delete_data.id}")
        finally:
            db.close()
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def todo_set_all(sid, data):
    """Set all todos to completed/uncompleted"""
    try:
        set_all_data = TodoSetAllData(**data)
        db = next(get_db())
        try:
            todos = db.query(TodoModel).all()
            for todo_model in todos:
                todo_model.completed = set_all_data.completed
                todo_model.updatedAt = datetime.utcnow()
                
                # Convert to Pydantic model for response
                todo = db_todo_to_pydantic(todo_model)
                await sio.emit('todo:updated', todo.dict())
            
            db.commit()
            print(f"✅ Set all todos to completed: {set_all_data.completed}")
        finally:
            db.close()
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def todo_remove_completed(sid, data):
    """Remove all completed todos"""
    try:
        db = next(get_db())
        try:
            completed_todos = db.query(TodoModel).filter(TodoModel.completed == True).all()
            for todo_model in completed_todos:
                db.delete(todo_model)
                await sio.emit('todo:deleted', {'id': todo_model.id})
            
            db.commit()
            print(f"✅ Removed {len(completed_todos)} completed todos")
        finally:
            db.close()
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, room=sid)

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

@app.post("/api/ai/prioritize")
async def prioritize_todos(
    request: Dict[str, Any],
    current_user: str = Depends(get_current_user)
):
    """Prioritize todos using AI"""
    todos = request.get('todos', [])
    preferences = request.get('preferences', {})
    prompt = request.get('prompt', '')
    
    try:
        enhanced_todos = await ai_handlers.prioritize_todos(todos, preferences, prompt)
        return enhanced_todos
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/ai/insights")
async def get_ai_insights(
    request: Dict[str, Any],
    current_user: str = Depends(get_current_user)
):
    """Get AI insights for todos"""
    todos = request.get('todos', [])
    preferences = request.get('preferences', {})
    
    try:
        insights = await ai_handlers.get_insights(todos, preferences)
        return {"insights": insights}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
