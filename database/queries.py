import re
import time
from datetime import datetime
from functools import wraps
from typing import Dict, List, Optional, Any, Callable
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from database.models import Project, Session as ChatSession, KnowledgeCore
from engine.tfidf_matcher import match_category, TfidfMatcher
from engine.knowledge_conflicts import detect_conflicts, summarize_conflicts


def retry_on_locked(max_retries=3, base_delay=0.5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except OperationalError as e:
                    if 'database is locked' in str(e).lower() and attempt < max_retries:
                        last_exception = e
                        delay = base_delay * (2 ** attempt)
                        print(f"\u26a0\ufe0f DB locked, retry {delay:.1f}s...")
                        time.sleep(delay)
                    else:
                        raise
            raise last_exception
        return wrapper
    return decorator


def get_or_create_project(db, project_name):
    p = db.query(Project).filter(Project.name == project_name).first()
    if not p:
        p = Project(name=project_name)
        db.add(p); db.commit(); db.refresh(p)
    return p


def list_all_projects(db):
    return db.query(Project).order_by(Project.updated_at.desc()).all()


def get_project_knowledge(db, project_id):
    return {e.category: e.content for e in db.query(KnowledgeCore).filter(KnowledgeCore.project_id == project_id).all()}


def create_session_record(db, project_id, filename, raw_tokens, compressed_tokens, knowledge_snapshot=None):
    s = ChatSession(project_id=project_id, filename=filename, raw_token_count=raw_tokens,
                    compressed_token_count=compressed_tokens, knowledge_snapshot=knowledge_snapshot)
    db.add(s); db.commit(); db.refresh(s); return s


def edit_knowledge_entry(db, project_id, category, content):
    r = db.query(KnowledgeCore).filter(KnowledgeCore.project_id == project_id, KnowledgeCore.category == category).first()
    if not r:
        r = KnowledgeCore(project_id=project_id, category=category, content=content); db.add(r)
    else:
        r.content = content; r.updated_at = datetime.utcnow()
    db.commit(); db.refresh(r); return r


def delete_knowledge_entry(db, project_id, category):
    r = db.query(KnowledgeCore).filter(KnowledgeCore.project_id == project_id, KnowledgeCore.category == category).first()
    if r:
        db.delete(r); db.commit()


def update_adaptive_knowledge(db, project_id, session_id, updated_knowledge, raw_context_stream=None):
    """Core adaptive engine with TF-IDF matching and conflict detection."""
    try:
        if not isinstance(updated_knowledge, dict):
            print(f"\u26a0\ufe0f Invalid knowledge format: {type(updated_knowledge)}")
            return False
        if not updated_knowledge:
            print("\u23ed\ufe0f Skipping update (empty delta)")
            return True

        existing = db.query(KnowledgeCore).filter(KnowledgeCore.project_id == project_id).all()
        existing_map = {r.category: r for r in existing}
        matcher = TfidfMatcher(list(existing_map.keys()), sensitivity=0.6)

        print(f"\ud83d\udcbe DB: {len(existing_map)} existing, {len(updated_knowledge)} incoming")
        added = updated = conflicts = 0

        for cat, content in updated_knowledge.items():
            if cat in existing_map:
                old = existing_map[cat].content if isinstance(existing_map[cat].content, dict) else {}
                c = detect_conflicts(old, content, cat)
                if c:
                    print(f"   {summarize_conflicts(c, cat)}"); conflicts += len(c)
                existing_map[cat].content = content
                existing_map[cat].last_updated_by_session_id = session_id
                existing_map[cat].updated_at = datetime.utcnow()
                updated += 1
            elif existing_map:
                ok, best, score = matcher.is_match(cat, list(existing_map.keys()))
                if ok and best in existing_map:
                    old = existing_map[best].content if isinstance(existing_map[best].content, dict) else {}
                    c = detect_conflicts(old, content, best)
                    if c:
                        print(f"   {summarize_conflicts(c, best)}"); conflicts += len(c)
                    existing_map[best].content = content
                    existing_map[best].last_updated_by_session_id = session_id
                    existing_map[best].updated_at = datetime.utcnow()
                    updated += 1
                    print(f"   Mapped '{cat}' -> '{best}' (score={score:.2f})")
                    continue
            rec = KnowledgeCore(project_id=project_id, category=cat, content=content, last_updated_by_session_id=session_id)
            db.add(rec); added += 1

        print(f"   {updated} updated, {added} added, {conflicts} conflicts")

        # Deletion: TF-IDF guard replaces bare keyword check
        del_count = 0
        if updated_knowledge:
            for cat, rec in existing_map.items():
                if cat not in updated_knowledge:
                    if raw_context_stream:
                        ok, _, _ = matcher.is_match(cat, list(updated_knowledge.keys()))
                        if ok:
                            continue
                    db.delete(rec); del_count += 1
        print(f"   Deleted {del_count}")

        proj = db.query(Project).filter(Project.id == project_id).first()
        if proj:
            proj.updated_at = datetime.utcnow()
        db.commit()
        print(f"\u2705 Knowledge base updated")
        return True
    except Exception as e:
        db.rollback()
        print(f"\u274c DB update failed: {e}"); raise
