import os
import json
import re
from typing import List, Dict
from pypdf import PdfReader

def _extract_text_from_pdf(filepath: str) -> str:
    """Extracts raw text strings across all pages of a PDF file."""
    reader = PdfReader(filepath)
    text_content = []
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text_content.append(extracted)
    return "\n".join(text_content)

def _mask_credentials(text: str) -> str:
    """Detects and redacts sensitive API keys, tokens, and IP patterns."""
    text = re.sub(
        r'((?:api[-_]?key|token|secret|password|pass|sk[-_]lm)\s*[:=]\s*["\']?)[a-zA-Z0-9_\-:]+(["\']?)', 
        r'\1[REDACTED_SECRET]\2', 
        text, flags=re.IGNORECASE
    )
    text = re.sub(r'\b100\.(?:6[4-9]|[7-9]\d|1[0-1]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b', '[REDACTED_TAILSCALE_IP]', text)
    text = re.sub(r'\b192\.168\.\d{1,3}\.\d{1,3}\b', '[REDACTED_LOCAL_IP]', text)
    text = re.sub(r'\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[REDACTED_INTRANET_IP]', text)
    return text

def _clean_and_truncate_content(content: str, max_lines: int = 15, skip_truncation: bool = False) -> str:
    """
    Detects massive automated tool results and truncates them,
    unless skip_truncation is True (for full documents).
    """
    # Always mask credentials regardless of truncation setting
    content = _mask_credentials(content)
    
    # If this is a full file pipeline (PDF/TXT), skip truncation
    if skip_truncation:
        return content

    # Otherwise, apply existing truncation logic
    lines = content.splitlines()
    if len(lines) <= max_lines:
        return content

    is_tool_block = any(tag in content for tag in ["<tool_call>", "<tool_response>", "<function=", "jsonrpc"])
    path_regex = r'(^[a-fA-F0-9_-]{12,})|([A-Za-z]:\\[\w\.-]+\\[\w\.-]+)|(\/[\w\.-]+\/[\w\.-]+)'
    hex_or_path_lines = [l for l in lines if re.search(path_regex, l)]
    is_data_dump = len(hex_or_path_lines) / len(lines) > 0.5

    if is_tool_block or is_data_dump:
        header = "\n".join(lines[:5])
        footer = "\n".join(lines[-3:]) if len(lines) > 8 else ""
        return f"{header}\n\n[⚠️ SYSTEM PARSER NOTICE: Truncated {len(lines) - 8} lines of automated tool/cache file listings to prevent context contamination]\n\n{footer}"
    
    return content

def _strip_thought_blocks_safely(text: str) -> str:
    code_blocks = []
    def preserve_code(match):
        code_blocks.append(match.group(0))
        return f"__CODE_BLOCK_PLACEHOLDER_{len(code_blocks)-1}__"

    temp_text = re.sub(r'```[\s\S]*?```', preserve_code, text)
    temp_text = re.sub(r'<(think|thinking|thought)>[\s\S]*?</\1>', '', temp_text, flags=re.IGNORECASE)
    temp_text = re.sub(r'\[(think|thinking|thought)\][\s\S]*?\[/\1\]', '', temp_text, flags=re.IGNORECASE)

    for i, block in enumerate(code_blocks):
        temp_text = temp_text.replace(f"__CODE_BLOCK_PLACEHOLDER_{i}__", block)
    return temp_text

def _parse_json_pipeline(filepath: str) -> List[Dict[str, str]]:
    """
    Parses a JSON-formatted conversation log file.
    
    Error Handling:
        - FileNotFoundError: File does not exist at specified path
        - json.JSONDecodeError: Invalid JSON syntax or structure
        - UnicodeDecodeError: File encoding issues (non-UTF-8 content)
        - ValueError: Unexpected data structure in parsed JSON
    
    Returns:
        List of normalized message dictionaries with 'role' and 'content' keys.
        Empty list if file is empty or contains no valid messages.
    """
    # Step 1: File existence check
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"JSON conversation log not found: {filepath}")
    
    # Step 2: File size validation (prevent processing massive files)
    file_size = os.path.getsize(filepath)
    max_file_size_mb = 50
    if file_size > max_file_size_mb * 1024 * 1024:
        raise ValueError(
            f"File too large: {file_size / (1024*1024):.1f}MB exceeds maximum supported size of {max_file_size_mb}MB"
        )
    
    # Step 3: Safe JSON parsing with comprehensive error handling
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON syntax in {os.path.basename(filepath)} at line {e.lineno}, column {e.colno}: {e.msg}"
        )
    except UnicodeDecodeError as e:
        raise ValueError(
            f"Encoding error when reading {os.path.basename(filepath)}. "
            f"File must be UTF-8 encoded. Detail: {str(e)}"
        )
    except PermissionError as e:
        raise PermissionError(f"Cannot read file '{filepath}'. Check file permissions.")
    except Exception as e:
        raise RuntimeError(f"Unexpected error reading JSON file '{filepath}': {type(e).__name__}: {str(e)}")
    
    # Step 4: Validate data structure
    if not isinstance(data, (dict, list)):
        raise ValueError(
            f"JSON root must be an object or array, got {type(data).__name__}. "
            f"Expected format: {{'messages': [...]}} or direct message array"
        )
    
    # Step 5: Extract messages with schema-aware fallback
    try:
        if isinstance(data, dict):
            messages = data.get("messages", [])
            if not messages and len(data) > 0:
                # If 'messages' key doesn't exist but we have a dict, treat the whole thing as one message
                messages = [data]
        else:
            messages = data if isinstance(data, list) else []
    except Exception as e:
        raise ValueError(f"Failed to extract messages from JSON structure: {str(e)}")
    
    # Step 6: Normalize and sanitize message content
    normalized_messages = []
    parse_errors = []
    
    for idx, m in enumerate(messages):
        if not isinstance(m, dict):
            parse_errors.append(f"Message {idx}: Expected object, got {type(m).__name__}")
            continue
        
        try:
            role = str(m.get("role", "user")).lower()
            # Validate role is one of expected values
            if role not in ("user", "assistant", "system"):
                role = "user"  # Fallback to user for unknown roles
            
            content = str(m.get("content", "") or m.get("text", ""))
            if not content.strip():
                continue  # Skip empty messages
            
            content = _strip_thought_blocks_safely(content)
            content = _clean_and_truncate_content(content, skip_truncation=False)
            
            if content.strip():
                normalized_messages.append({"role": role, "content": content.strip()})
        except Exception as e:
            parse_errors.append(f"Message {idx}: Processing error - {str(e)}")
            continue
    
    # Log warnings for any parsing issues encountered (non-fatal)
    if parse_errors:
        print(f"⚠️ JSON Parse Warnings ({os.path.basename(filepath)}): {len(parse_errors)} messages skipped or partially processed")
        for warning in parse_errors[:5]:  # Show first 5 warnings
            print(f"   - {warning}")
        if len(parse_errors) > 5:
            print(f"   ... and {len(parse_errors) - 5} more issues not shown")
    
    return normalized_messages

def _parse_plaintext_pipeline(raw_text: str, skip_truncation: bool = False) -> List[Dict[str, str]]:
    raw_text = _strip_thought_blocks_safely(raw_text)

    if not raw_text.strip():
        return [{"role": "user", "content": "Initial workspace handshake segment analyzed."}]

    code_block_spans = [m.span() for m in re.finditer(r'```[\s\S]*?```', raw_text)]
    pattern = re.compile(r'(?mi)^(###\s+)?(user|assistant|ai|system|human|bot):\s*')
    all_matches = list(pattern.finditer(raw_text))
    
    matches = []
    for m in all_matches:
        start = m.start()
        in_code = any(c_start <= start <= c_end for c_start, c_end in code_block_spans)
        if not in_code:
            matches.append(m)

    if not matches:
        return [{"role": "user", "content": _clean_and_truncate_content(raw_text.strip(), skip_truncation=skip_truncation)}]

    cleaned_messages = []
    for i in range(len(matches)):
        start_idx = matches[i].end()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(raw_text)
        
        role = matches[i].group(2).lower()
        if role in ('human', 'user'): role = 'user'
        elif role in ('ai', 'bot', 'assistant'): role = 'assistant'
            
        content = raw_text[start_idx:end_idx].strip()
        # Pass the skip_truncation flag down
        content = _clean_and_truncate_content(content, skip_truncation=skip_truncation)
        
        if content:
            cleaned_messages.append({"role": role, "content": content})

    if not cleaned_messages:
        raise ValueError("Could not parse structural content blocks out of the file layout.")

    return cleaned_messages

def parse_lm_studio_file(filepath: str) -> List[Dict[str, str]]:
    ext = os.path.splitext(filepath)[1].lower()

    if ext == '.json':
        return _parse_json_pipeline(filepath)
        
    elif ext in ('.txt', '.md'):
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_text = f.read()
        return _parse_plaintext_pipeline(raw_text, skip_truncation=True)

    elif ext == '.pdf':
        raw_text = _extract_text_from_pdf(filepath)
        return _parse_plaintext_pipeline(raw_text, skip_truncation=True)
        
    else:
        raise ValueError(f"Unsupported file format: {ext}")