import os
from sqlmodel import create_engine, SQLModel, Session
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get DATABASE_URL from environment or use default
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app/data/app.db")

# Create directory for SQLite file if it doesn't exist
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False  # Set to True to see SQL queries
)

# Function to create database tables
def create_db_and_tables():
    """Create database tables if they don't exist"""
    SQLModel.metadata.create_all(engine)

# Session dependency for FastAPI
def get_session():
    """Provides a database session as a dependency for routes"""
    with Session(engine) as session:
        yield session 