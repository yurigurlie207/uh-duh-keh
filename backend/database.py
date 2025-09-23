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
    createdAt = Column("createdAt", DateTime, default=datetime.utcnow)
    updatedAt = Column("updatedAt", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Todo(Base):
    __tablename__ = "todos"
    
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    completed = Column(Boolean, default=False)
    priority = Column(String, default="999")
    assignedTo = Column("assignedTo", String, nullable=True)
    createdBy = Column("createdBy", String, nullable=False)
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
