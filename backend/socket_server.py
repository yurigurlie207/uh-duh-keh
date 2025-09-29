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
from database import get_db, Todo as TodoModel, Action as ActionModel, Household
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
            return session.get('username'), session.get('household_id')
        return None, None
    except Exception as e:
        print(f"❌ Error getting session for sid {sid}: {e}")
        return None, None

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
        "ai_reason": None,
        "Completed": getattr(db_todo, 'Completed', None)
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
            username, household_id = auth_service.verify_token(token)
            print(f"✅ Authenticated user: {username} from household: {household_id} for sid: {sid}")
            
            # Store user info in session (you can access this in other event handlers)
            await sio.save_session(sid, {'username': username, 'household_id': household_id, 'authenticated': True})

            # Don't automatically join a room - let user choose
            print(f"🔐 User {username} authenticated but not in any room yet")

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
    try:
        session = await sio.get_session(sid)
        if session and session.get('current_room'):
            current_room = session.get('current_room')
            await sio.leave_room(sid, current_room)
            print(f"👋 User left room: {current_room}")
    except Exception as e:
        print(f"⚠️ Error during disconnect cleanup: {e}")
    print(f"👋 Client {sid} disconnected")

@sio.on('join_household')
async def join_household(sid, data):
    """Allow users to explicitly join a household room"""
    try:
        print(f"🔍 Received join_household request from sid: {sid}")
        print(f"🔍 Data: {data}")
        
        # Get user session
        session = await sio.get_session(sid)
        if not session or not session.get('authenticated'):
            await sio.emit('auth_error', {'message': 'Not authenticated'}, room=sid)
            return
        
        username = session.get('username')
        user_household_id = session.get('household_id')
        requested_household_id = data.get('household_id')
        requested_household_name = data.get('household_name')

        # If household_name provided, resolve to id
        if not requested_household_id and requested_household_name:
            db = next(get_db())
            try:
                h = db.query(Household).filter(Household.name == requested_household_name).first()
                if h:
                    requested_household_id = h.id
            finally:
                db.close()
        
        # Validate that user can only join their own household
        if requested_household_id != user_household_id:
            await sio.emit('error', {'message': 'You can only join your own household room'}, room=sid)
            return
        
        # Leave current room if any
        current_room = session.get('current_room')
        if current_room:
            await sio.leave_room(sid, current_room)
            print(f"👋 User {username} left room: {current_room}")
        
        # Join the requested household room
        room_name = f"household_{requested_household_id}"
        await sio.enter_room(sid, room_name)
        
        # Update session with current room
        session['current_room'] = room_name
        await sio.save_session(sid, session)
        
        print(f"🏠 User {username} joined household room: {room_name}")
        await sio.emit('room_joined', {'room': room_name, 'household_id': requested_household_id}, room=sid)
        
    except Exception as e:
        print(f"❌ Error in join_household: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

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
            username, household_id = await get_authenticated_user(sid)
            if not username or not household_id:
                await sio.emit('auth_error', {'message': 'Not authenticated'}, room=sid)
                return
            
            # Check if user is in a room
            session = await sio.get_session(sid)
            if not session.get('current_room'):
                await sio.emit('error', {'message': 'You must join a household room first'}, room=sid)
                return

            todo_model = TodoModel(
                id=str(uuid.uuid4()),
                title=todo_data.title,
                assignedTo=todo_data.assigned_to,
                priority=todo_data.priority or "999",
                createdBy=username,
                householdId=household_id,
                completed=False,
                createdAt=datetime.utcnow(),
                updatedAt=datetime.utcnow()
            )
            db.add(todo_model)
            # Log transaction
            db.add(ActionModel(
                id=str(uuid.uuid4()),
                userId=username,
                householdId=household_id,
                task=todo_model.title,
                completed='created'
            ))
            db.commit()
            db.refresh(todo_model)
            
            # Convert to Pydantic model for response
            todo = db_todo_to_pydantic(todo_model)
            
            # Broadcast to household room only
            await sio.emit('todo:created', todo, room=f"household_{household_id}")
            print(f"✅ Created todo: {todo['title']} (broadcast to household_{household_id})")
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
            username, household_id = await get_authenticated_user(sid)
            if not username or not household_id:
                await sio.emit('auth_error', {'message': 'Not authenticated'}, room=sid)
                return
            
            # Check if user is in a room
            session = await sio.get_session(sid)
            if not session.get('current_room'):
                await sio.emit('error', {'message': 'You must join a household room first'}, room=sid)
                return
                
            # Find todo (no household filtering needed - rooms handle isolation)
            todo_model = db.query(TodoModel).filter(TodoModel.id == todo_data.id).first()
            if todo_model:
                if todo_data.title is not None:
                    todo_model.title = todo_data.title
                if todo_data.assigned_to is not None:
                    todo_model.assignedTo = todo_data.assigned_to
                if todo_data.priority is not None:
                    todo_model.priority = todo_data.priority
                
                todo_model.updatedAt = datetime.utcnow()
                # Log transaction
                db.add(ActionModel(
                    id=str(uuid.uuid4()),
                    userId=username,
                    householdId=household_id,
                    task=todo_model.title,
                    completed='completed' if todo_model.completed else 'incomplete'
                ))
                db.commit()
                db.refresh(todo_model)
                
                todo = db_todo_to_pydantic(todo_model)
                # Broadcast to household room only
                await sio.emit('todo:updated', todo, room=f"household_{household_id}")
                print(f"✅ Updated todo: {todo['title']} (broadcast to household_{household_id})")
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
            username, household_id = await get_authenticated_user(sid)
            if not username or not household_id:
                await sio.emit('auth_error', {'message': 'Not authenticated'}, room=sid)
                return
            
            # Check if user is in a room
            session = await sio.get_session(sid)
            if not session.get('current_room'):
                await sio.emit('error', {'message': 'You must join a household room first'}, room=sid)
                return
                
            # Find todo (no household filtering needed - rooms handle isolation)
            todo_model = db.query(TodoModel).filter(TodoModel.id == toggle_data.id).first()
            if todo_model:
                todo_model.completed = bool(toggle_data.completed)
                setattr(todo_model, 'Completed', 'completed' if todo_model.completed else None)
                todo_model.updatedAt = datetime.utcnow()
                # Log action based on new completion state
                db.add(ActionModel(
                    id=str(uuid.uuid4()),
                    userId=username,
                    householdId=household_id,
                    task=todo_model.title,
                    completed='completed' if todo_model.completed else 'incomplete'
                ))
                db.commit()
                db.refresh(todo_model)
                
                todo = db_todo_to_pydantic(todo_model)
                # Broadcast to household room only
                await sio.emit('todo:toggled', todo, room=f"household_{household_id}")
                print(f"✅ Toggled todo: {todo['title']} -> {todo['completed']} (broadcast to household_{household_id})")
            else:
                await sio.emit('error', {'message': 'Todo not found'}, room=sid)
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error in todo_toggle: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.on('todo:delete')
async def todo_delete(sid, data):
    """Soft delete a todo (mark Completed='deleted')"""
    try:
        print(f"🔍 Received todo_delete data: {data}")
        delete_data = TodoDeleteData(**data)
        
        db = next(get_db())
        try:
            username, household_id = await get_authenticated_user(sid)
            if not username or not household_id:
                await sio.emit('auth_error', {'message': 'Not authenticated'}, room=sid)
                return
            
            # Check if user is in a room
            session = await sio.get_session(sid)
            if not session.get('current_room'):
                await sio.emit('error', {'message': 'You must join a household room first'}, room=sid)
                return
                
            # Find todo (no household filtering needed - rooms handle isolation)
            todo_model = db.query(TodoModel).filter(TodoModel.id == delete_data.id).first()
            if todo_model:
                setattr(todo_model, 'Completed', 'deleted')
                todo_model.updatedAt = datetime.utcnow()
                db.commit()
                db.refresh(todo_model)
                todo = db_todo_to_pydantic(todo_model)
                # Broadcast to household room only
                await sio.emit('todo:updated', todo, room=f"household_{household_id}")
                print(f"✅ Marked deleted todo: {delete_data.id} (broadcast to household_{household_id})")
            else:
                await sio.emit('error', {'message': 'Todo not found'}, room=sid)
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error in todo_delete: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.on('todo:hard_delete')
async def todo_hard_delete(sid, data):
    """Permanently delete a todo from the database"""
    try:
        print(f"🔍 Received todo_hard_delete data: {data}")
        delete_data = TodoDeleteData(**data)

        db = next(get_db())
        try:
            username, household_id = await get_authenticated_user(sid)
            if not username or not household_id:
                await sio.emit('auth_error', {'message': 'Not authenticated'}, room=sid)
                return
            
            # Check if user is in a room
            session = await sio.get_session(sid)
            if not session.get('current_room'):
                await sio.emit('error', {'message': 'You must join a household room first'}, room=sid)
                return
                
            # Find todo (no household filtering needed - rooms handle isolation)
            todo_model = db.query(TodoModel).filter(TodoModel.id == delete_data.id).first()
            if todo_model:
                # Log action
                db.add(ActionModel(
                    id=str(uuid.uuid4()),
                    userId=username,
                    householdId=household_id,
                    task=todo_model.title,
                    completed='deleted'
                ))
                db.delete(todo_model)
                db.commit()
                # Broadcast to household room only
                await sio.emit('todo:deleted', {'id': delete_data.id}, room=f"household_{household_id}")
                print(f"🗑️ Permanently deleted todo: {delete_data.id} (broadcast to household_{household_id})")
            else:
                await sio.emit('error', {'message': 'Todo not found'}, room=sid)
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error in todo_hard_delete: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.on('todo:set_all')
async def todo_set_all(sid, data):
    """Set all todos completion status"""
    try:
        print(f"🔍 Received todo_set_all data: {data}")
        set_all_data = TodoSetAllData(**data)
        
        db = next(get_db())
        try:
            username, household_id = await get_authenticated_user(sid)
            if not username or not household_id:
                await sio.emit('auth_error', {'message': 'Not authenticated'}, room=sid)
                return
            
            # Check if user is in a room
            session = await sio.get_session(sid)
            if not session.get('current_room'):
                await sio.emit('error', {'message': 'You must join a household room first'}, room=sid)
                return
                
            # Get all todos for the household (rooms handle isolation, but we still need householdId for data integrity)
            todos = db.query(TodoModel).filter(TodoModel.householdId == household_id).all()
            for todo in todos:
                todo.completed = set_all_data.completed
                todo.updatedAt = datetime.utcnow()
            db.commit()
            
            # Emit updated todos to household room only
            updated_todos = [db_todo_to_pydantic(todo) for todo in todos]
            await sio.emit('todos:updated', updated_todos, room=f"household_{household_id}")
            print(f"✅ Set all todos to: {set_all_data.completed} (broadcast to household_{household_id})")
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
            username, household_id = await get_authenticated_user(sid)
            if not username or not household_id:
                await sio.emit('auth_error', {'message': 'Not authenticated'}, room=sid)
                return
            
            # Check if user is in a room
            session = await sio.get_session(sid)
            if not session.get('current_room'):
                await sio.emit('error', {'message': 'You must join a household room first'}, room=sid)
                return
                
            # Get completed todos for the household (rooms handle isolation, but we still need householdId for data integrity)
            completed_todos = db.query(TodoModel).filter(
                TodoModel.completed == True,
                TodoModel.householdId == household_id
            ).all()
            for todo in completed_todos:
                db.delete(todo)
            db.commit()
            
            # Broadcast to household room only
            await sio.emit('todos:completed_removed', {'count': len(completed_todos)}, room=f"household_{household_id}")
            print(f"✅ Removed {len(completed_todos)} completed todos (broadcast to household_{household_id})")
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
