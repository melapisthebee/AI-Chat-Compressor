from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from database.models import Project, Session as ChatSession, KnowledgeCore

def get_or_create_project(db: Session, project_name: str) -> Project:
    """
    Fetches a project by name, or creates it if it doesn't exist yet.
    """
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

def create_session_record(
    db: Session, 
    project_id: int, 
    filename: str, 
    raw_tokens: int, 
    compressed_tokens: int
) -> ChatSession:
    """
    Logs the metadata of an imported conversation file.
    """
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

def update_adaptive_knowledge(
    db: Session, 
    project_id: int, 
    session_id: int, 
    updated_knowledge: Dict[str, Any]
):
    """
    The core adaptive engine routine. 
    Takes a dictionary of fresh knowledge chunks (native dict/JSON from LLM engine) 
    and updates existing categories or creates new ones.
    
    CRITICAL GUARDRAIL: If the incoming update payload is completely empty, it is 
    treated as a model generation or truncation fault, and deletions are skipped 
    to preserve existing data states.
    """
    # 1. Fetch current stored knowledge records for this project
    existing_records = db.query(KnowledgeCore).filter(KnowledgeCore.project_id == project_id).all()
    existing_map = {record.category: record for record in existing_records}
    
    # 2. Process updates and additions
    for category, fresh_content in updated_knowledge.items():
        if category in existing_map:
            # Overwrite content if it changed (SQLAlchemy detects internal dict modifications)
            record = existing_map[category]
            record.content = fresh_content
            record.last_updated_by_session_id = session_id
            record.updated_at = datetime.utcnow()
        else:
            # Create a brand new knowledge segment storing native JSON/dict
            new_record = KnowledgeCore(
                project_id=project_id,
                category=category,
                content=fresh_content,
                last_updated_by_session_id=session_id
            )
            db.add(new_record)
            
    # 3. Handle deletions with structural truncation guardrail
    # If the LLM completely blanks out or fails parsing, updated_knowledge might be empty.
    # We only process deprecations if we actually received a valid, populated state tree.
    if updated_knowledge:
        for category, old_record in existing_map.items():
            if category not in updated_knowledge:
                db.delete(old_record)
                
    # 4. Touch the project timestamp to show it was modified
    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        project.updated_at = datetime.utcnow()
        
    db.commit()