"""
FastAPI application with WebSocket support for todo management
"""
import os
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

from auth import AuthService
from ai_handlers import AIHandlers
from common.events import (
    Todo, UserPreferences, TodoCreateData, TodoUpdateData, 
    TodoToggleData, TodoDeleteData, TodoSetAllData
)

# Initialize Socket.IO
sio = socketio.AsyncServer(cors_allowed_origins="*", async_mode='asgi')

# Global storage (in production, use a database)
todos_db: Dict[str, Todo] = {}
user_preferences_db: Dict[str, UserPreferences] = {}

# Initialize services
auth_service = AuthService()
ai_handlers = AIHandlers()

security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting FastAPI server with WebSocket support")
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
    allow_methods=["*"],
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
        todo = Todo(
            id=str(uuid.uuid4()),
            title=todo_data.title,
            assigned_to=todo_data.assigned_to,
            created_at=datetime.now().isoformat()
        )
        todos_db[todo.id] = todo
        
        await sio.emit('todo:created', todo.dict())
        print(f"✅ Created todo: {todo.title}")
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def todo_update(sid, data):
    """Update an existing todo"""
    try:
        update_data = TodoUpdateData(**data)
        if update_data.id not in todos_db:
            await sio.emit('error', {'message': 'Todo not found'}, room=sid)
            return
        
        todo = todos_db[update_data.id]
        if update_data.title is not None:
            todo.title = update_data.title
        if update_data.completed is not None:
            todo.completed = update_data.completed
        if update_data.priority is not None:
            todo.priority = update_data.priority
        if update_data.assigned_to is not None:
            todo.assigned_to = update_data.assigned_to
        
        todo.updated_at = datetime.now().isoformat()
        
        await sio.emit('todo:updated', todo.dict())
        print(f"✅ Updated todo: {todo.title}")
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def todo_toggle(sid, data):
    """Toggle todo completion status"""
    try:
        toggle_data = TodoToggleData(**data)
        if toggle_data.id not in todos_db:
            await sio.emit('error', {'message': 'Todo not found'}, room=sid)
            return
        
        todo = todos_db[toggle_data.id]
        todo.completed = not todo.completed
        todo.updated_at = datetime.now().isoformat()
        
        await sio.emit('todo:updated', todo.dict())
        print(f"✅ Toggled todo: {todo.title} -> {todo.completed}")
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def todo_delete(sid, data):
    """Delete a todo"""
    try:
        delete_data = TodoDeleteData(**data)
        if delete_data.id not in todos_db:
            await sio.emit('error', {'message': 'Todo not found'}, room=sid)
            return
        
        del todos_db[delete_data.id]
        await sio.emit('todo:deleted', {'id': delete_data.id})
        print(f"✅ Deleted todo: {delete_data.id}")
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def todo_set_all(sid, data):
    """Set all todos to completed/uncompleted"""
    try:
        set_all_data = TodoSetAllData(**data)
        for todo in todos_db.values():
            todo.completed = set_all_data.completed
            todo.updated_at = datetime.now().isoformat()
            await sio.emit('todo:updated', todo.dict())
        print(f"✅ Set all todos to completed: {set_all_data.completed}")
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def todo_remove_completed(sid, data):
    """Remove all completed todos"""
    try:
        completed_ids = [todo_id for todo_id, todo in todos_db.items() if todo.completed]
        for todo_id in completed_ids:
            del todos_db[todo_id]
            await sio.emit('todo:deleted', {'id': todo_id})
        print(f"✅ Removed {len(completed_ids)} completed todos")
    except Exception as e:
        await sio.emit('error', {'message': str(e)}, room=sid)

# REST API endpoints
@app.get("/")
async def root():
    return {"message": "Todo Management API with WebSocket support"}

@app.get("/api/todos", response_model=List[Todo])
async def get_todos(current_user: str = Depends(get_current_user)):
    """Get all todos"""
    return list(todos_db.values())

@app.get("/api/users")
async def get_users(current_user: str = Depends(get_current_user)):
    """Get available users"""
    return [{"username": "mom"}, {"username": "dad"}, {"username": "kid"}]

@app.get("/api/user-preferences", response_model=UserPreferences)
async def get_user_preferences(current_user: str = Depends(get_current_user)):
    """Get user preferences"""
    return user_preferences_db.get(current_user, UserPreferences())

@app.post("/api/user-preferences")
async def update_user_preferences(
    preferences: UserPreferences,
    current_user: str = Depends(get_current_user)
):
    """Update user preferences"""
    user_preferences_db[current_user] = preferences
    return {"message": "Preferences updated successfully"}

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
