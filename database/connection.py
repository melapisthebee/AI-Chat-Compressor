from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from database.models import Base

# Format connection string for local SQLite file storage
DATABASE_URL = f"sqlite:///{settings.DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Crucial for multi-threaded GUI setups
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Creates the SQLite database structure if it doesn't exist yet."""
    Base.metadata.create_all(bind=engine)

def get_db_session():
    """Context utility for scoping transactional queries cleanly."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()