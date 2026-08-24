"""
Parser Engine for LM Studio Conversations

Handles structured turn extraction from native LM Studio JSON exports as well
as raw plain-text (.txt) and Markdown (.md) conversation logs.
"""

import json
import os
from typing import List, Dict, Any


def parse_lm_studio_file(filepath: str) -> List[Dict[str, str]]:
    """
    Parses conversation files into a standard message turn list:
    [{"role": "user"|"assistant"|"system", "content": "..."}, ...]
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".json":
        return _parse_json_conversation(filepath)
    elif ext in (".txt", ".md"):
        return _parse_text_conversation(filepath)
    else:
        raise ValueError(f"Unsupported conversation file format: {ext}")


def _parse_json_conversation(filepath: str) -> List[Dict[str, str]]:
    """Extracts turn history from LM Studio JSON schema variants."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    messages = []
    # Handle schema variations (.conversation.json vs custom exports)
    raw_messages = data.get("messages") or data.get("history") or data.get("turns") or []

    for msg in raw_messages:
        role = (msg.get("role") or msg.get("type") or "user").lower()
        content = msg.get("content") or msg.get("text") or ""

        # Handle nested content structures (e.g. multi-part token arrays)
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(item.get("text", ""))
                elif isinstance(item, str):
                    parts.append(item)
            content = "".join(parts)

        if content.strip() and role in ("user", "assistant", "system"):
            messages.append({
                "role": role,
                "content": content.strip()
            })

    return messages


def _parse_text_conversation(filepath: str) -> List[Dict[str, str]]:
    """Fallback turn parser for plain text and markdown conversation exports."""
    with open(filepath, "r", encoding="utf-8") as f:
        raw_text = f.read()

    messages = []
    blocks = raw_text.split("\n\n")

    for block in blocks:
        block_clean = block.strip()
        if block_clean.startswith("USER:"):
            messages.append({"role": "user", "content": block_clean[5:].strip()})
        elif block_clean.startswith("ASSISTANT:"):
            messages.append({"role": "assistant", "content": block_clean[10:].strip()})
        elif block_clean.startswith("SYSTEM:"):
            messages.append({"role": "system", "content": block_clean[7:].strip()})

    return messages
