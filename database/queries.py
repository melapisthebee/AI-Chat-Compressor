import re
import time
import sqlite3
from datetime import datetime
from functools import wraps
from typing import Dict, List, Optional, Any, Callable
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from database.models import Project, Session as ChatSession, KnowledgeCore
from database.connection import db_write_lock

def retry_on_locked(max_retries: int = 3, base_delay: float = 0.5):
    """
    Decorator to retry database operations with exponential backoff
    when encountering 'database is locked' errors.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds before first retry (default: 0.5s)
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    error_msg = str(e).lower()
                    if 'database is locked' in error_msg and attempt < max_retries:
                        last_exception = e
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        print(f"⚠️ Database locked, retrying in {delay:.1f}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                    else:
                        raise
            raise last_exception
        return wrapper
    return decorator

@retry_on_locked(max_retries=3, base_delay=0.5)
def get_or_create_project(db: Session, project_name: str) -> Project:
    """
    Fetches a project by name, or creates it if it doesn't exist yet.
    Thread-safe: Uses mutex lock around write operations.
    """
    with db_write_lock:
        project = db.query(Project).filter(Project.name == project_name).first()
        if not project:
            project = Project(name=project_name)
            db.add(project)
            db.commit()
            db.refresh(project)
        return project

def list_all_projects(db: Session) -> List[Project]:
    """
    Returns all projects ordered by the most recently updated.
    """
    return db.query(Project).order_by(Project.updated_at.desc()).all()

def get_project_knowledge(db: Session, project_id: int) -> Dict[str, Any]:
    """
    Gathers all current knowledge entries for a project.
    Returns a dictionary mapping categories to their native JSON structures/dicts.
    """
    entries = db.query(KnowledgeCore).filter(KnowledgeCore.project_id == project_id).all()
    return {entry.category: entry.content for entry in entries}

@retry_on_locked(max_retries=3, base_delay=0.5)
def create_session_record(
    db: Session, 
    project_id: int, 
    filename: str, 
    raw_tokens: int, 
    compressed_tokens: int
) -> ChatSession:
    """
    Logs the metadata of an imported conversation file.
    Thread-safe: Uses mutex lock around write operations.
    """
    with db_write_lock:
        session_record = ChatSession(
            project_id=project_id,
            filename=filename,
            raw_token_count=raw_tokens,
            compressed_token_count=compressed_tokens
        )
        db.add(session_record)
        db.commit()
        db.refresh(session_record)
        return session_record

@retry_on_locked(max_retries=3, base_delay=1.0)
def update_adaptive_knowledge(
    db: Session, 
    project_id: int, 
    session_id: int, 
    updated_knowledge: Dict[str, Any],
    raw_context_stream: Optional[str] = None
):
    """
    The core adaptive engine routine. 
    Takes a dictionary of fresh knowledge chunks (native dict/JSON from LLM engine) 
    and updates existing categories or creates new ones.
    Thread-safe: Uses mutex lock around all write operations to prevent race conditions.
    
    CRITICAL GUARDRAIL: If the incoming update payload is completely empty, it is 
    treated as a model generation or truncation fault, and deletions are skipped 
    to preserve existing data states.
    
    SEMANTIC OMISSION CHECK: If an existing category is missing from the update, 
    the system checks if keywords from that category were even mentioned in the 
    raw text stream. If not, the omission is treated as context exclusion rather 
    than a true deletion request, preserving the historical record.
    """
    try:
        # Validate input
        if not isinstance(updated_knowledge, dict):
            print(f"⚠️ Invalid knowledge format: expected dict, got {type(updated_knowledge)}")
            return False
        
        # Early exit if empty delta - no need to do database work
        if not updated_knowledge:
            print("⏭️ Skipping database update (empty knowledge delta)")
            return True
            
        # 1. Fetch current stored knowledge records for this project
        with db_write_lock:
            existing_records = db.query(KnowledgeCore).filter(KnowledgeCore.project_id == project_id).all()
            existing_map = {record.category: record for record in existing_records}
            
            print(f"💾 Database update: Found {len(existing_map)} existing categories")
            print(f"   Incoming update has {len(updated_knowledge)} categories")
        
            # 2. Process updates and additions
            added_count = 0
            updated_count = 0
            for category, fresh_content in updated_knowledge.items():
                if category in existing_map:
                    # Overwrite content if it changed (SQLAlchemy detects internal dict modifications)
                    record = existing_map[category]
                    record.content = fresh_content
                    record.last_updated_by_session_id = session_id
                    record.updated_at = datetime.utcnow()
                    updated_count += 1
                else:
                    # Create a brand new knowledge segment storing native JSON/dict
                    new_record = KnowledgeCore(
                        project_id=project_id,
                        category=category,
                        content=fresh_content,
                        last_updated_by_session_id=session_id
                    )
                    db.add(new_record)
                    added_count += 1
            
            print(f"   ✓ Processed: {updated_count} updated, {added_count} added")
            
            # 3. Handle deletions with structural truncation and semantic omission guardrails
            deleted_count = 0
            if updated_knowledge:
                for category, old_record in existing_map.items():
                    if category not in updated_knowledge:
                        
                        # Semantic validation check
                        should_delete = True
                        if raw_context_stream:
                            normalized_stream = raw_context_stream.lower()
                            # Extract alphanumeric keyword parts (e.g., "database_layer" -> ["database", "layer"])
                            keywords = re.findall(r'\w+', category.lower())
                            
                            # If descriptive category keys were completely absent from the processed text chunk,
                            # the file simply didn't contain info on this domain. Skip deletion to protect state.
                            if keywords and not any(kw in normalized_stream for kw in keywords):
                                should_delete = False
                        
                        if should_delete:
                            db.delete(old_record)
                            deleted_count += 1
            
            print(f"   ✓ Deleted {deleted_count} obsolete categories")
            
            # 4. Touch the project timestamp to show it was modified
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.updated_at = datetime.utcnow()
        
        # Commit outside the lock but within the transaction
        db.commit()
        print(f"✅ Knowledge base updated successfully")
        return True
            
    except Exception as e:
        db.rollback()
        print(f"❌ Database update failed: {str(e)}")
        raise