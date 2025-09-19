"""
Common event types for WebSocket communication between frontend and backend
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel


class ClientEvents:
    """Events sent from client to server"""
    
    # Todo events
    TODO_CREATE = "todo:create"
    TODO_UPDATE = "todo:update"
    TODO_DELETE = "todo:delete"
    TODO_TOGGLE = "todo:toggle"
    TODO_SET_ALL = "todo:set_all"
    TODO_REMOVE_COMPLETED = "todo:remove_completed"
    
    # User events
    USER_JOIN = "user:join"
    USER_LEAVE = "user:leave"


class ServerEvents:
    """Events sent from server to client"""
    
    # Todo events
    TODO_CREATED = "todo:created"
    TODO_UPDATED = "todo:updated"
    TODO_DELETED = "todo:deleted"
    
    # Connection events
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    ERROR = "error"


class TodoCreateData(BaseModel):
    title: str
    assigned_to: Optional[str] = None


class TodoUpdateData(BaseModel):
    id: str
    title: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None


class TodoToggleData(BaseModel):
    id: str


class TodoDeleteData(BaseModel):
    id: str


class TodoSetAllData(BaseModel):
    completed: bool


class UserPreferences(BaseModel):
    pet_care: bool = False
    laundry: bool = False
    cooking: bool = False
    organization: bool = False
    plant_care: bool = False
    house_work: bool = False
    yard_work: bool = False
    family_care: bool = False


class Todo(BaseModel):
    id: str
    title: str
    completed: bool = False
    priority: str = "999"
    assigned_to: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    ai_priority: Optional[int] = None
    ai_reason: Optional[str] = None
