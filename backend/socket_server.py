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

# Helper function to create room name (handles household_id with or without prefix)
def get_room_name(household_id: str) -> str:
    """Get room name from household_id, handling existing prefix"""
    return household_id if household_id.startswith('household_') else f"household_{household_id}"

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
def db_todo_to_pydantic(db_todo: TodoModel, action_status=None) -> dict:
    """Convert database Todo model to Pydantic Todo model"""
    # Initialize default values
    is_deleted = False
    is_completed = False
    
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
    
    return {
        "id": db_todo.id,
        "title": db_todo.title,
        "completed": is_completed,
        "priority": db_todo.priority,
        "assigned_to": db_todo.assignedTo,
        "created_at": db_todo.createdAt.isoformat() if db_todo.createdAt else None,
        "updated_at": db_todo.updatedAt.isoformat() if db_todo.updatedAt else None,
        "ai_priority": None,
        "ai_reason": None,
        "Completed": 'deleted' if is_deleted else ('completed' if is_completed else None),
        "is_deleted": is_deleted  # Add explicit deleted flag for frontend
    }

async def send_current_state(sid, household_id):
    """Send current state (todos, users) to a newly joined user"""
    try:
        db = next(get_db())
        try:
            # Get all todos for this household
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
            todos_data = []
            for todo in todos:
                task_status = task_status_map.get(todo.title)
                if task_status != 'deleted':  # Only include non-deleted todos
                    todos_data.append(db_todo_to_pydantic(todo, task_status))
            
            # Get all users for this household
            from database import User
            users = db.query(User).filter(User.householdId == household_id).all()
            users_data = [{"username": user.username} for user in users]
            
            # Send state to the specific user
            await sio.emit('state_sync', {
                'todos': todos_data,
                'users': users_data,
                'household_id': household_id
            }, room=sid)
            
            print(f"📤 Sent current state to user: {len(todos_data)} todos, {len(users_data)} users")
            
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error sending current state: {e}")
        await sio.emit('error', {'message': f'Failed to load current state: {str(e)}'}, room=sid)

# Note: Removed broadcast_state_update function - using individual todo events instead

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
            print(f"=" * 80)
            print(f"✅✅✅ AUTHENTICATED USER: {username} from household: {household_id} for sid: {sid}")
            print(f"=" * 80)
            
            # Store user info in session (you can access this in other event handlers)
            session = {'username': username, 'household_id': household_id, 'authenticated': True}
            await sio.save_session(sid, session)
            print(f"💾 Session saved for {username}: {{'username': '{username}', 'household_id': '{household_id}', 'authenticated': True}}")

            # Automatically join the user's household room so they are always part of it
            room_name = get_room_name(household_id)
            await sio.enter_room(sid, room_name)
            session['current_room'] = room_name
            await sio.save_session(sid, session)
            print(f"🏠 Auto-joined user {username} to household room: {room_name}")

            # Notify room that user is online and send current state to this user
            await sio.emit('user:online', {'username': username}, room=room_name)
            await send_current_state(sid, household_id)

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
            username = session.get('username')
            await sio.leave_room(sid, current_room)
            print(f"👋 User {username} left room: {current_room}")
            
            # Broadcast to everyone in the room that a user went offline
            if username:
                await sio.emit('user:offline', {'username': username}, room=current_room)
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
        room_name = get_room_name(requested_household_id)
        await sio.enter_room(sid, room_name)
        
        # Update session with current room
        session['current_room'] = room_name
        await sio.save_session(sid, session)
        
        print(f"🏠 User {username} joined household room: {room_name}")
        await sio.emit('room_joined', {'room': room_name, 'household_id': requested_household_id}, room=sid)
        
        # Broadcast to everyone in the room that a user came online
        await sio.emit('user:online', {'username': username}, room=room_name)
        
        # Debug: Check room membership after joining
        room_clients = list(sio.manager.get_participants(namespace='/', room=room_name))
        print(f"🔍 After joining, room {room_name} has {len(room_clients)} clients: {room_clients}")
        
        # Send current state to the newly joined user
        print(f"📤 Sending current state to newly joined user {username}")
        await send_current_state(sid, requested_household_id)
        
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
            room_name = get_room_name(household_id)
            await sio.emit('todo:created', todo, room=room_name)
            print(f"✅ Created todo: {todo['title']} (broadcast to {room_name})")
            
            # Debug: Check who's in the room
            room_clients = list(sio.manager.get_participants(namespace='/', room=room_name))
            print(f"🔍 Room {room_name} has {len(room_clients)} clients: {room_clients}")
            
            # Note: Individual todo events handle the updates, no need for full state sync
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
                await sio.emit('todo:updated', todo, room=get_room_name(household_id))
                print(f"✅ Updated todo: {todo['title']} (broadcast to household_{household_id})")
                
                # Note: Individual todo events handle the updates, no need for full state sync
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
                todo_model.updatedAt = datetime.utcnow()
                # Log action based on new completion state
                db.add(ActionModel(
                    id=str(uuid.uuid4()),
                    userId=username,
                    householdId=household_id,
                    task=todo_model.title,
                    completed='completed' if toggle_data.completed else 'incomplete'
                ))
                db.commit()
                db.refresh(todo_model)
                
                todo = db_todo_to_pydantic(todo_model)
                # Broadcast to household room only
                await sio.emit('todo:toggled', todo, room=get_room_name(household_id))
                print(f"✅ Toggled todo: {todo['title']} -> {todo['completed']} (broadcast to household_{household_id})")
                
                # Note: Individual todo events handle the updates, no need for full state sync
            else:
                await sio.emit('error', {'message': 'Todo not found'}, room=sid)
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error in todo_toggle: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.on('todo:delete')
async def todo_delete(sid, data):
    """Soft delete a todo (log as 'deleted' in Action table)"""
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
                # Log the soft delete action in Action table
                db.add(ActionModel(
                    id=str(uuid.uuid4()),
                    userId=username,
                    householdId=household_id,
                    task=todo_model.title,
                    completed='deleted'
                ))
                db.commit()
                
                # Broadcast to household room only
                await sio.emit('todo:deleted', {'id': delete_data.id}, room=get_room_name(household_id))
                print(f"✅ Soft deleted todo: {delete_data.id} (logged in Action table, broadcast to household_{household_id})")
                
                # Note: Individual todo events handle the updates, no need for full state sync
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
                await sio.emit('todo:deleted', {'id': delete_data.id}, room=get_room_name(household_id))
                print(f"🗑️ Permanently deleted todo: {delete_data.id} (broadcast to household_{household_id})")
                
                # Note: Individual todo events handle the updates, no need for full state sync
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
                todo.updatedAt = datetime.utcnow()
                # Log action for each todo
                db.add(ActionModel(
                    id=str(uuid.uuid4()),
                    userId=username,
                    householdId=household_id,
                    task=todo.title,
                    completed='completed' if set_all_data.completed else 'incomplete'
                ))
            db.commit()
            
            # Emit updated todos to household room only
            updated_todos = [db_todo_to_pydantic(todo) for todo in todos]
            await sio.emit('todos:updated', updated_todos, room=get_room_name(household_id))
            print(f"✅ Set all todos to: {set_all_data.completed} (broadcast to household_{household_id})")
            
            # Note: Individual todo events handle the updates, no need for full state sync
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
                
            # Get completed todos for the household by checking Action table
            from database import Action
            completed_actions = db.query(Action).filter(
                Action.completed == 'completed',
                Action.householdId == household_id
            ).all()
            
            # Get unique task names that are completed
            completed_tasks = list(set([action.task for action in completed_actions]))
            
            # Find todos that match these completed tasks
            completed_todos = db.query(TodoModel).filter(
                TodoModel.title.in_(completed_tasks),
                TodoModel.householdId == household_id
            ).all()
            for todo in completed_todos:
                db.delete(todo)
            db.commit()
            
            # Broadcast to household room only
            await sio.emit('todos:completed_removed', {'count': len(completed_todos)}, room=get_room_name(household_id))
            print(f"✅ Removed {len(completed_todos)} completed todos (broadcast to household_{household_id})")
            
            # Note: Individual todo events handle the updates, no need for full state sync
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error in todo_remove_completed: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.on('restart_day')
async def restart_day(sid, data=None):
    """Restart the day - refresh all todos for the household"""
    try:
        print(f"🔍 Received restart_day from sid: {sid}")
        
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
            
            # Get all todos for the household directly from todos table
            todos = db.query(TodoModel).filter(
                TodoModel.householdId == household_id
            ).all()
            
            # Convert todos to simple format without Action table logic
            updated_todos = []
            for todo in todos:
                updated_todos.append({
                    "id": todo.id,
                    "title": todo.title,
                    "completed": False,  # Reset to not completed
                    "priority": todo.priority,
                    "assigned_to": todo.assignedTo,
                    "created_at": todo.createdAt.isoformat() if todo.createdAt else None,
                    "updated_at": todo.updatedAt.isoformat() if todo.updatedAt else None,
                    "ai_priority": None,
                    "ai_reason": None,
                    "Completed": None,
                    "is_deleted": False  # Default to not deleted
                })
            
            # Debug: Log the todos being sent
            print(f"🔍 Todos being sent to household {household_id}:")
            for i, todo in enumerate(updated_todos):
                print(f"  {i+1}. {todo.get('title', 'No title')} (completed: {todo.get('completed', 'N/A')})")
            
            # Debug: Check room membership
            room_name = get_room_name(household_id)
            room_clients = list(sio.manager.get_participants(namespace='/', room=room_name))
            print(f"🔍 Room {room_name} has {len(room_clients)} clients: {room_clients}")
            
            # Broadcast to household room only
            await sio.emit('todos:restarted', updated_todos, room=room_name)
            print(f"✅ Restarted day with {len(updated_todos)} todos (broadcast to {room_name})")
            
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error in restart_day: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    from starlette.responses import JSONResponse
    from starlette.routing import Mount
    
    # Create a minimal FastAPI app for Socket.IO
    app = FastAPI()
    
    # Add endpoint to get online users for a household (BEFORE mounting Socket.IO)
    @app.get("/online-users/{household_id}")
    async def get_online_users(household_id: str):
        """Get list of online users in a household"""
        try:
            room_name = get_room_name(household_id)
            print(f"🔍 Checking online users for room: {room_name}")
            
            # Get all session IDs in this room
            # get_participants returns tuples of (sid, eio_sid), we only need the first element
            room_participants = list(sio.manager.get_participants(namespace='/', room=room_name))
            room_sids = [p[0] if isinstance(p, tuple) else p for p in room_participants]
            print(f"🔍 Found {len(room_sids)} connections in room")
            print(f"🔍 Session IDs: {room_sids}")
            
            # Get usernames for each session
            online_users = []
            for sid in room_sids:
                try:
                    session = await sio.get_session(sid)
                    if session and session.get('username'):
                        username = session['username']
                        online_users.append(username)
                        print(f"🔍 Found online user: {username}")
                except Exception as e:
                    print(f"⚠️ Error getting session for {sid}: {e}")
            
            print(f"✅ Returning {len(online_users)} online users: {online_users}")
            return JSONResponse({"users": online_users, "count": len(online_users)})
        except Exception as e:
            print(f"❌ Error getting online users: {e}")
            import traceback
            traceback.print_exc()
            return JSONResponse({"users": [], "count": 0})
    
    # Create the Socket.IO ASGI app
    socketio_app = socketio.ASGIApp(sio, other_asgi_app=app)
    
    print("🚀 Starting Socket.IO server on port 3002...")
    uvicorn.run(socketio_app, host="0.0.0.0", port=3002)
