import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship, declarative_base  # FIXED: Explicitly import relationship here

Base = declarative_base()

class Project(Base):
    """
    Groups chat sessions together. Houses the adaptive 'KnowledgeCore'
    which represents the current, distilled truth of the project state.
    """
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sessions = relationship("Session", back_populates="project", cascade="all, delete-orphan")
    knowledge_entries = relationship("KnowledgeCore", back_populates="project", cascade="all, delete-orphan")


class Session(Base):
    """
    Tracks raw imported metadata and historical stats for every 
    80k+ token file dropped into the folder.
    """
    __tablename__ = 'sessions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    imported_at = Column(DateTime, default=datetime.utcnow)
    raw_token_count = Column(Integer, nullable=False)
    compressed_token_count = Column(Integer, nullable=False)
    knowledge_snapshot = Column(JSON, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="sessions")


class KnowledgeCore(Base):
    """
    The brain of the system. Instead of appending text, the LLM will map 
    condensed facts into 'keys'. When a new file contradicts or modifies 
    an old key, the record is overwritten or updated here.
    """
    __tablename__ = 'knowledge_core'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    
    # E.g., 'system_architecture', 'database_schema', 'todo_list', 'code_constraints'
    category = Column(String(50), nullable=False)
    
    # The actual context injection block string for this topic
    content = Column(JSON, nullable=False)
    
    # Tracks which session update touched this fact last
    last_updated_by_session_id = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="knowledge_entries")