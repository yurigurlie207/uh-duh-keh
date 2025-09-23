#!/usr/bin/env python3
"""
Socket.IO server for real-time todo management
"""
import os
import sys
import uuid
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the parent directory to the Python path to import common module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import socketio
from database import get_db, Todo as TodoModel
from common.events import TodoCreateData, TodoUpdateData, TodoToggleData, TodoDeleteData, TodoSetAllData
from auth import AuthService

# Initialize Socket.IO server with WebSocket-enabled configuration
sio = socketio.AsyncServer(
    cors_allowed_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    cors_credentials=True,
    async_mode='asgi',
    # Enable WebSocket upgrades
    allow_upgrades=True,
    ping_timeout=60,
    ping_interval=25,
    # Additional CORS settings for better compatibility
    cors_headers=["Content-Type", "Authorization", "Accept", "Origin", "User-Agent"]
)

# Initialize auth service
auth_service = AuthService()

# Helper function to get authenticated user from session
async def get_authenticated_user(sid):
    """Get the authenticated user from the session"""
    try:
        session = await sio.get_session(sid)
        if session and session.get('authenticated'):
            return session.get('username')
        return None
    except Exception as e:
        print(f"❌ Error getting session for sid {sid}: {e}")
        return None

# Helper function to convert database model to Pydantic model
def db_todo_to_pydantic(db_todo: TodoModel) -> dict:
    """Convert database Todo model to Pydantic Todo model"""
    return {
        "id": db_todo.id,
        "title": db_todo.title,
        "completed": db_todo.completed,
        "priority": db_todo.priority,
        "assigned_to": db_todo.assignedTo,
        "created_at": db_todo.createdAt.isoformat() if db_todo.createdAt else None,
        "updated_at": db_todo.updatedAt.isoformat() if db_todo.updatedAt else None,
        "ai_priority": None,
        "ai_reason": None
    }

@sio.event
async def connect(sid, environ, auth=None):
    """Handle WebSocket connection with JWT authentication"""
    try:
        print(f"🔌 Connection attempt from sid: {sid}")
        print(f"🔍 Auth data: {auth}")
        print(f"🔍 Environ: {environ.get('HTTP_ORIGIN', 'No origin')}")
        
        # Extract token from auth object
        token = None
        if auth and isinstance(auth, dict):
            token = auth.get('token')
        
        # Verify JWT token
        if not token:
            print(f"❌ No token provided for sid: {sid}")
            await sio.emit('auth_error', {'message': 'No authentication token provided'}, room=sid)
            return False  # Reject connection
        
        try:
            # Verify the JWT token
            username = auth_service.verify_token(token)
            print(f"✅ Authenticated user: {username} for sid: {sid}")
            
            # Store user info in session (you can access this in other event handlers)
            await sio.save_session(sid, {'username': username, 'authenticated': True})

            # Do not emit a 'connect' event here (reserved by protocol). If needed, emit a custom event.
            # await sio.emit('server:welcome', {'message': f'Connected as {username}!'}, room=sid)
            return True  # Accept connection
            
        except Exception as auth_error:
            print(f"❌ Authentication failed for sid {sid}: {auth_error}")
            await sio.emit('auth_error', {'message': 'Invalid authentication token'}, room=sid)
            return False  # Reject connection
        
    except Exception as e:
        print(f"❌ Connection error for sid {sid}: {e}")
        print(f"❌ Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        await sio.emit('error', {'message': 'Connection error'}, room=sid)
        return False  # Reject connection

@sio.event
async def disconnect(sid):
    """Handle WebSocket disconnection"""
    print(f"👋 Client {sid} disconnected")

@sio.on('todo:create')
async def todo_create(sid, data):
    """Create a new todo"""
    try:
        print(f"🔍 Received todo_create data: {data}")
        print(f"🔍 Data type: {type(data)}")
        
        todo_data = TodoCreateData(**data)
        print(f"✅ Parsed todo_data: {todo_data}")
        
        db = next(get_db())
        try:
            # Fetch authenticated user for createdBy
            username = await get_authenticated_user(sid)
            if not username:
                await sio.emit('auth_error', {'message': 'Not authenticated'}, room=sid)
                return

            todo_model = TodoModel(
                id=str(uuid.uuid4()),
                title=todo_data.title,
                assignedTo=todo_data.assigned_to,
                priority=todo_data.priority or "999",
                createdBy=username,
                completed=False,
                createdAt=datetime.utcnow(),
                updatedAt=datetime.utcnow()
            )
            db.add(todo_model)
            db.commit()
            db.refresh(todo_model)
            
            # Convert to Pydantic model for response
            todo = db_todo_to_pydantic(todo_model)
            
            await sio.emit('todo:created', todo)
            print(f"✅ Created todo: {todo['title']}")
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error in todo_create: {e}")
        print(f"❌ Error type: {type(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.on('todo:update')
async def todo_update(sid, data):
    """Update an existing todo"""
    try:
        print(f"🔍 Received todo_update data: {data}")
        todo_data = TodoUpdateData(**data)
        
        db = next(get_db())
        try:
            todo_model = db.query(TodoModel).filter(TodoModel.id == todo_data.id).first()
            if todo_model:
                if todo_data.title is not None:
                    todo_model.title = todo_data.title
                if todo_data.assigned_to is not None:
                    todo_model.assignedTo = todo_data.assigned_to
                if todo_data.priority is not None:
                    todo_model.priority = todo_data.priority
                
                todo_model.updatedAt = datetime.utcnow()
                db.commit()
                db.refresh(todo_model)
                
                todo = db_todo_to_pydantic(todo_model)
                await sio.emit('todo:updated', todo)
                print(f"✅ Updated todo: {todo['title']}")
            else:
                await sio.emit('error', {'message': 'Todo not found'}, room=sid)
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error in todo_update: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.on('todo:toggle')
async def todo_toggle(sid, data):
    """Toggle todo completion status"""
    try:
        print(f"🔍 Received todo_toggle data: {data}")
        toggle_data = TodoToggleData(**data)
        
        db = next(get_db())
        try:
            todo_model = db.query(TodoModel).filter(TodoModel.id == toggle_data.id).first()
            if todo_model:
                todo_model.completed = bool(toggle_data.completed)
                todo_model.updatedAt = datetime.utcnow()
                db.commit()
                db.refresh(todo_model)
                
                todo = db_todo_to_pydantic(todo_model)
                await sio.emit('todo:toggled', todo)
                print(f"✅ Toggled todo: {todo['title']} -> {todo['completed']}")
            else:
                await sio.emit('error', {'message': 'Todo not found'}, room=sid)
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error in todo_toggle: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.on('todo:delete')
async def todo_delete(sid, data):
    """Delete a todo"""
    try:
        print(f"🔍 Received todo_delete data: {data}")
        delete_data = TodoDeleteData(**data)
        
        db = next(get_db())
        try:
            todo_model = db.query(TodoModel).filter(TodoModel.id == delete_data.id).first()
            if todo_model:
                db.delete(todo_model)
                db.commit()
                await sio.emit('todo:deleted', {'id': delete_data.id})
                print(f"✅ Deleted todo: {delete_data.id}")
            else:
                await sio.emit('error', {'message': 'Todo not found'}, room=sid)
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error in todo_delete: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.on('todo:set_all')
async def todo_set_all(sid, data):
    """Set all todos completion status"""
    try:
        print(f"🔍 Received todo_set_all data: {data}")
        set_all_data = TodoSetAllData(**data)
        
        db = next(get_db())
        try:
            todos = db.query(TodoModel).all()
            for todo in todos:
                todo.completed = set_all_data.completed
                todo.updatedAt = datetime.utcnow()
            db.commit()
            
            # Emit updated todos
            updated_todos = [db_todo_to_pydantic(todo) for todo in todos]
            await sio.emit('todos:updated', updated_todos)
            print(f"✅ Set all todos to: {set_all_data.completed}")
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error in todo_set_all: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.on('todo:remove_completed')
async def todo_remove_completed(sid):
    """Remove all completed todos"""
    try:
        print(f"🔍 Received todo_remove_completed from sid: {sid}")
        
        db = next(get_db())
        try:
            completed_todos = db.query(TodoModel).filter(TodoModel.completed == True).all()
            for todo in completed_todos:
                db.delete(todo)
            db.commit()
            
            await sio.emit('todos:completed_removed', {'count': len(completed_todos)})
            print(f"✅ Removed {len(completed_todos)} completed todos")
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error in todo_remove_completed: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    
    # Create a minimal FastAPI app for Socket.IO
    app = FastAPI()
    app.mount("/", socketio.ASGIApp(sio, app))
    
    print("🚀 Starting Socket.IO server on port 3002...")
    uvicorn.run(app, host="0.0.0.0", port=3002)
