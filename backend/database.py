"""
Database configuration and models
"""
import os
from sqlalchemy import create_engine, Column, String, Boolean, Integer, DateTime, Text, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/todo_db")

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()

# Database Models
class User(Base):
    __tablename__ = "users"
    
    username = Column(String, primary_key=True, index=True)
    passwordHash = Column("passwordHash", String, nullable=False)
    householdId = Column("householdId", String, nullable=False)
    isAdmin = Column("isAdmin", Boolean, default=False)
    createdAt = Column("createdAt", DateTime, default=datetime.utcnow)
    updatedAt = Column("updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Todo(Base):
    __tablename__ = "todos"
    
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    priority = Column(String, default="999")
    assignedTo = Column("assignedTo", String, nullable=True)
    createdBy = Column("createdBy", String, nullable=False)
    householdId = Column("householdId", String, nullable=False)
    createdAt = Column("createdAt", DateTime, default=datetime.utcnow)
    updatedAt = Column("updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Note: aiPriority and aiReason columns don't exist in your database
    # aiPriority = Column("aiPriority", Integer, nullable=True)
    # aiReason = Column("aiReason", Text, nullable=True)

class UserPreferences(Base):
    __tablename__ = "user_preferences"
    
    username = Column(String, primary_key=True, index=True)
    petCare = Column("petCare", Boolean, default=False)
    laundry = Column(Boolean, default=False)
    cooking = Column(Boolean, default=False)
    organization = Column(Boolean, default=False)
    plantCare = Column("plantCare", Boolean, default=False)
    houseWork = Column("houseWork", Boolean, default=False)
    yardWork = Column("yardWork", Boolean, default=False)
    familyCare = Column("familyCare", Boolean, default=False)
    updatedAt = Column("updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# New Transactions table to capture user actions on tasks
class Action(Base):
    __tablename__ = "actions"

    id = Column(String, primary_key=True, index=True)
    userId = Column("userId", String, nullable=False)
    householdId = Column("householdId", String, nullable=False)
    task = Column(String, nullable=False)
    dateTime = Column("dateTime", DateTime, default=datetime.utcnow)
    completed = Column(String, nullable=True)  # e.g., 'created', 'completed', 'deleted', 'incomplete'

# Household table to map human-friendly names to household IDs
class Household(Base):
    __tablename__ = "households"

    id = Column(String, primary_key=True, index=True)  # householdId used by users/todos
    name = Column(String, unique=True, nullable=False)  # human-friendly unique name
    createdAt = Column("createdAt", DateTime, default=datetime.utcnow)
    updatedAt = Column("updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Join requests for admin approval
class JoinRequest(Base):
    __tablename__ = "join_requests"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, nullable=False)
    householdId = Column(String, nullable=False)
    status = Column(String, default="pending")  # 'pending' | 'approved' | 'rejected'
    createdAt = Column("createdAt", DateTime, default=datetime.utcnow)
    updatedAt = Column("updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create all tables
def create_tables():
    Base.metadata.create_all(bind=engine)
    
    # Migration: Remove completed column from todos table
    _remove_completed_column()
    # Migration: Remove Completed status column from todos table
    _remove_completed_status_column()

def _remove_completed_column():
    """Remove the completed column from todos table if it exists"""
    try:
        with engine.connect() as conn:
            # Check if completed column exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'todos' AND column_name = 'completed'
            """))
            if result.fetchone():
                print("🗑️ Removing completed column from todos table...")
                conn.execute(text('ALTER TABLE todos DROP COLUMN IF EXISTS completed'))
                conn.commit()
                print("✅ Completed column removed successfully")
            else:
                print("ℹ️ Completed column does not exist, skipping removal")
    except Exception as e:
        print(f"⚠️ Error removing completed column: {e}")
        # Don't fail the application if migration fails

def _remove_completed_status_column():
    """Remove the Completed column from todos table if it exists"""
    try:
        with engine.connect() as conn:
            # Check if Completed column exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'todos' AND column_name = 'Completed'
            """))
            if result.fetchone():
                print("🗑️ Removing Completed column from todos table...")
                conn.execute(text('ALTER TABLE todos DROP COLUMN IF EXISTS "Completed"'))
                conn.commit()
                print("✅ Completed status column removed successfully")
            else:
                print("ℹ️ Completed status column does not exist, skipping removal")
    except Exception as e:
        print(f"⚠️ Error removing Completed column: {e}")
        # Don't fail the application if migration fails

# Attempt to add the Completed column if it doesn't exist (basic runtime migration)
def _ensure_completed_column():
    try:
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE todos ADD COLUMN IF NOT EXISTS "Completed" VARCHAR NULL'))
            conn.commit()
    except Exception:
        # Ignore if the column already exists or cannot be altered here
        pass

_ensure_completed_column()

# Attempt to add the isAdmin column if it doesn't exist (basic runtime migration)
def _ensure_is_admin_column():
    try:
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE users ADD COLUMN IF NOT EXISTS "isAdmin" BOOLEAN DEFAULT FALSE'))
            conn.commit()
    except Exception:
        # Ignore if the column already exists or cannot be altered here
        pass

_ensure_is_admin_column()

# Ensure tables (including new actions table) exist
try:
    create_tables()
except Exception:
    pass
