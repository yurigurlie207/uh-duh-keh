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

from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

from auth import AuthService
from database import get_db, create_tables, Todo as TodoModel, UserPreferences as UserPreferencesModel, User, Household, JoinRequest
from common.events import (
    Todo, UserPreferences, TodoCreateData, TodoUpdateData, 
    TodoToggleData, TodoDeleteData, TodoSetAllData
)

# Database will be used instead of in-memory storage

# Initialize services
auth_service = AuthService()

# Helper function to convert database model to Pydantic model
def db_todo_to_pydantic(db_todo: TodoModel, action_status=None) -> Todo:
    """Convert database Todo model to Pydantic Todo model"""
    # If action_status is provided, use it; otherwise query the database
    if action_status is not None:
        is_deleted = action_status == 'deleted'
        is_completed = action_status == 'completed'
    else:
        # Check if todo is soft-deleted by looking at Action table
        from database import Action
        db = next(get_db())
        try:
            # Get the latest action for this todo to determine if it's deleted
            latest_action = db.query(Action).filter(
                Action.task == db_todo.title,
                Action.householdId == db_todo.householdId
            ).order_by(Action.dateTime.desc()).first()
            
            is_deleted = latest_action and latest_action.completed == 'deleted'
            is_completed = latest_action and latest_action.completed == 'completed'
        finally:
            db.close()
    
    return Todo(
        id=db_todo.id,
        title=db_todo.title,
        completed=is_completed,
        priority=db_todo.priority,
        assigned_to=db_todo.assignedTo,
        created_at=db_todo.createdAt.isoformat() if db_todo.createdAt else None,
        updated_at=db_todo.updatedAt.isoformat() if db_todo.updatedAt else None,
        ai_priority=None,  # Column doesn't exist in your database
        ai_reason=None,    # Column doesn't exist in your database
        Completed='deleted' if is_deleted else ('completed' if is_completed else None),
        is_deleted=is_deleted  # Add explicit deleted flag for frontend
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
        username, household_id = auth_service.verify_token(credentials.credentials)
        return username, household_id
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

# WebSocket handling is now done by the separate socket_server.py on port 3002

# REST API endpoints
@app.get("/")
async def root():
    return {"message": "Todo Management API with WebSocket support"}

@app.get("/api/todos", response_model=List[Todo])
async def get_todos(current_user: tuple = Depends(get_current_user)):
    """Get all todos for the user's household"""
    username, household_id = current_user
    db = next(get_db())
    try:
        # Get all todos for the household
        todos = db.query(TodoModel).filter(
            TodoModel.householdId == household_id
        ).all()
        
        # Get all actions for the household to determine status
        from database import Action
        all_actions = db.query(Action).filter(
            Action.householdId == household_id
        ).order_by(Action.dateTime.desc()).all()
        
        # Create a map of task -> latest action status
        task_status_map = {}
        for action in all_actions:
            if action.task not in task_status_map:
                task_status_map[action.task] = action.completed
        
        # Filter out soft-deleted todos and convert to Pydantic models
        result_todos = []
        for todo in todos:
            task_status = task_status_map.get(todo.title)
            if task_status != 'deleted':  # Only include non-deleted todos
                result_todos.append(db_todo_to_pydantic(todo, task_status))
        
        return result_todos
    finally:
        db.close()

@app.post("/api/todos", response_model=Todo)
async def create_todo(todo_data: TodoCreateData, current_user: tuple = Depends(get_current_user)):
    """Create a new todo via HTTP API"""
    username, household_id = current_user
    db = next(get_db())
    try:
        # Create todo with household_id for data integrity
        todo_model = TodoModel(
            id=str(uuid.uuid4()),
            title=todo_data.title,
            assignedTo=todo_data.assigned_to,
            priority=todo_data.priority or "999",
            createdBy=username,
            householdId=household_id
        )
        db.add(todo_model)
        db.commit()
        db.refresh(todo_model)
        
        todo = db_todo_to_pydantic(todo_model)
        print(f"✅ Created todo via HTTP API: {todo.title} (household: {household_id})")
        return todo
    finally:
        db.close()

@app.get("/api/users")
async def get_users(current_user: tuple = Depends(get_current_user)):
    """Get available users from the user's household with online status"""
    username, household_id = current_user
    print(f"🔍 GET /api/users called by {username} for household {household_id}")
    db = next(get_db())
    try:
        # Filter by household_id for REST API (rooms handle Socket.IO isolation)
        users = db.query(User).filter(User.householdId == household_id).all()
        print(f"🔍 Found {len(users)} users in household")
        
        # Check online status by querying the socket server
        # We'll use a simple file-based approach or in-memory store
        # For now, we'll return a placeholder and implement socket tracking
        print(f"🔍 About to call get_online_users_in_household...")
        online_users = await get_online_users_in_household(household_id)
        print(f"🔍 Got online users: {online_users}")
        
        return [
            {
                "username": user.username, 
                "is_admin": user.isAdmin or False,
                "is_online": user.username in online_users
            } 
            for user in users
        ]
    finally:
        db.close()

async def get_online_users_in_household(household_id: str) -> set:
    """Get list of online users in a household by checking socket connections"""
    try:
        import httpx
        # Query the socket server's status endpoint
        print(f"🔍 Querying online users for household: {household_id}")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:3002/online-users/{household_id}",
                timeout=2.0
            )
            print(f"🔍 Response status: {response.status_code}")
            print(f"🔍 Response body: {response.text}")
            if response.status_code == 200:
                data = response.json()
                users = set(data.get('users', []))
                print(f"✅ Online users: {users}")
                return users
    except Exception as e:
        print(f"❌ Failed to get online users: {e}")
        import traceback
        traceback.print_exc()
    return set()

@app.get("/api/user-preferences", response_model=UserPreferences)
async def get_user_preferences(current_user: tuple = Depends(get_current_user)):
    """Get user preferences"""
    username, household_id = current_user
    db = next(get_db())
    try:
        user_prefs = db.query(UserPreferencesModel).filter(UserPreferencesModel.username == username).first()
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
    current_user: tuple = Depends(get_current_user)
):
    """Update user preferences"""
    username, household_id = current_user
    db = next(get_db())
    try:
        user_prefs = db.query(UserPreferencesModel).filter(UserPreferencesModel.username == username).first()
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
                username=username,
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
        # Get user info to include household_id in response
        user_info = auth_service.get_user(username)
        return {
            "token": token, 
            "username": username,
            "household_id": user_info.get('household_id') if user_info else None
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/api/me")
async def me(current_user: tuple = Depends(get_current_user)):
    """Get current user info including household and admin flag."""
    username, household_id = current_user
    db = next(get_db())
    try:
        u = db.query(User).filter(User.username == username).first()
        h = db.query(Household).filter(Household.id == household_id).first() if household_id else None
        return {
            "username": username,
            "household_id": household_id,
            "household_name": h.name if h else None,
            "is_admin": bool(getattr(u, 'isAdmin', False)) if u else False
        }
    finally:
        db.close()

@app.post("/api/auth/register")
async def register(request: Dict[str, str]):
    """User registration"""
    username = request.get('username')
    password = request.get('password')
    household_id = request.get('household_id')
    household_name = request.get('household_name')
    
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
    
    db = next(get_db())
    try:
        # Resolve household by name if provided
        if household_name:
            existing = db.query(Household).filter(Household.name == household_name).first()
            if existing:
                household_id = existing.id
            else:
                # Create new household with provided name
                import uuid as _uuid
                household_id = household_id or f"household_{_uuid.uuid4().hex[:8]}"
                db.add(Household(id=household_id, name=household_name))
                db.commit()
        
        # If still no household_id, generate one and create a unique default name
        if not household_id:
            import uuid as _uuid
            household_id = f"household_{_uuid.uuid4().hex[:8]}"
            # Create a unique friendly name like "{username}'s household", add suffix if needed
            base_name = f"{username}'s household"
            candidate = base_name
            suffix = 2
            while db.query(Household).filter(Household.name == candidate).first() is not None:
                candidate = f"{base_name} ({suffix})"
                suffix += 1
            db.add(Household(id=household_id, name=candidate))
            db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to prepare household: {e}")
    finally:
        db.close()
    
    try:
        # Determine if this user should be admin (only if no admin exists in household)
        # This ensures only one admin per household
        db2 = next(get_db())
        try:
            existing_admin = db2.query(User).filter(User.householdId == household_id, User.isAdmin == True).first()
            is_admin = existing_admin is None
        finally:
            db2.close()
        auth_service.register(username, password, household_id, is_admin)
        return {"message": "User registered successfully", "household_id": household_id, "is_admin": is_admin}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/households")
async def list_households(q: str | None = Query(default=None, description="Search by household name (case-insensitive)")):
    """List available households (id and name). Supports optional name search."""
    db = next(get_db())
    try:
        query = db.query(Household)
        if q:
            like = f"%{q.lower()}%"
            query = query.filter(Household.name.ilike(like))
        rows = query.all()
        return [{"id": h.id, "name": h.name} for h in rows]
    finally:
        db.close()

@app.post("/api/households/{household_id}/join-requests")
async def request_join_household(household_id: str, current_user: tuple = Depends(get_current_user)):
    """Create a join request for the current user to be approved by a household admin."""
    username, _ = current_user
    db = next(get_db())
    try:
        h = db.query(Household).filter(Household.id == household_id).first()
        if not h:
            raise HTTPException(status_code=404, detail="household not found")
        import uuid as _uuid
        jr = JoinRequest(id=_uuid.uuid4().hex, username=username, householdId=household_id, status="pending")
        db.add(jr)
        db.commit()
        return {"message": "Join request created", "request_id": jr.id}
    finally:
        db.close()

@app.get("/api/households/{household_id}/join-requests")
async def list_join_requests(household_id: str, current_user: tuple = Depends(get_current_user)):
    """List pending join requests for admins of the household."""
    username, _ = current_user
    db = next(get_db())
    try:
        # Check admin
        u = db.query(User).filter(User.username == username).first()
        if not u or u.householdId != household_id or not getattr(u, 'isAdmin', False):
            raise HTTPException(status_code=403, detail="admin access required")
        rows = db.query(JoinRequest).filter(JoinRequest.householdId == household_id, JoinRequest.status == "pending").all()
        return [{"id": r.id, "username": r.username, "status": r.status, "created_at": r.createdAt.isoformat()} for r in rows]
    finally:
        db.close()

@app.post("/api/households/{household_id}/join-requests/{request_id}/approve")
async def approve_join_request(household_id: str, request_id: str, current_user: tuple = Depends(get_current_user)):
    """Approve a join request and add the user to the household."""
    username, _ = current_user
    db = next(get_db())
    try:
        # Check admin
        admin = db.query(User).filter(User.username == username).first()
        if not admin or admin.householdId != household_id or not getattr(admin, 'isAdmin', False):
            raise HTTPException(status_code=403, detail="admin access required")
        jr = db.query(JoinRequest).filter(JoinRequest.id == request_id, JoinRequest.householdId == household_id).first()
        if not jr or jr.status != "pending":
            raise HTTPException(status_code=404, detail="request not found or not pending")
        # Update target user
        target = db.query(User).filter(User.username == jr.username).first()
        if not target:
            raise HTTPException(status_code=404, detail="target user not found")
        target.householdId = household_id
        target.updatedAt = datetime.utcnow()
        jr.status = "approved"
        jr.updatedAt = datetime.utcnow()
        db.commit()
        h = db.query(Household).filter(Household.id == household_id).first()
        return {"message": "Request approved", "username": target.username, "household_id": household_id, "household_name": h.name if h else None}
    finally:
        db.close()

@app.post("/api/households/{household_id}/join-requests/{request_id}/reject")
async def reject_join_request(household_id: str, request_id: str, current_user: tuple = Depends(get_current_user)):
    """Reject a join request."""
    username, _ = current_user
    db = next(get_db())
    try:
        # Check admin
        admin = db.query(User).filter(User.username == username).first()
        if not admin or admin.householdId != household_id or not getattr(admin, 'isAdmin', False):
            raise HTTPException(status_code=403, detail="admin access required")
        jr = db.query(JoinRequest).filter(JoinRequest.id == request_id, JoinRequest.householdId == household_id).first()
        if not jr or jr.status != "pending":
            raise HTTPException(status_code=404, detail="request not found or not pending")
        jr.status = "rejected"
        jr.updatedAt = datetime.utcnow()
        db.commit()
        return {"message": "Request rejected"}
    finally:
        db.close()

@app.post("/api/households")
async def create_household(request: Dict[str, str]):
    """Create a new household with a given name (unique)."""
    name = request.get('name')
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    db = next(get_db())
    try:
        exists = db.query(Household).filter(Household.name == name).first()
        if exists:
            return {"id": exists.id, "name": exists.name}
        import uuid as _uuid
        hid = f"household_{_uuid.uuid4().hex[:8]}"
        row = Household(id=hid, name=name)
        db.add(row)
        db.commit()
        return {"id": hid, "name": name}
    finally:
        db.close()

@app.put("/api/households/{household_id}")
async def rename_household(household_id: str, request: Dict[str, str]):
    """Rename an existing household (name must be unique)."""
    new_name = request.get('name')
    if not new_name:
        raise HTTPException(status_code=400, detail="name is required")
    db = next(get_db())
    try:
        # Ensure unique name
        existing = db.query(Household).filter(Household.name == new_name).first()
        if existing and existing.id != household_id:
            raise HTTPException(status_code=400, detail="household name already exists")
        row = db.query(Household).filter(Household.id == household_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="household not found")
        row.name = new_name
        row.updatedAt = datetime.utcnow()
        db.commit()
        return {"id": row.id, "name": row.name}
    finally:
        db.close()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=3001,
        reload=True,
        log_level="info"
    )
