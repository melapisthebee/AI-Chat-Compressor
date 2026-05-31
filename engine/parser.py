import os
import re
from typing import List, Dict
from pypdf import PdfReader

def _extract_text_from_pdf(filepath: str) -> str:
    """
    Extracts raw text strings across all pages of a PDF file.
    Reverted to safe line-by-line extraction to prevent skewed paragraph line-count ratios.
    """
    reader = PdfReader(filepath)
    text_content = []
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text_content.append(extracted)
    return "\n".join(text_content)

def _mask_credentials(text: str) -> str:
    """
    Detects and redacts sensitive API keys, authorization tokens, 
    and Tailscale/Local networking IP patterns from text contexts.
    """
    text = re.sub(
        r'((?:api[-_]?key|token|secret|password|pass|sk[-_]lm)\s*[:=]\s*["\']?)[a-zA-Z0-9_\-:]+(["\']?)', 
        r'\1[REDACTED_SECRET]\2', 
        text, flags=re.IGNORECASE
    )
    text = re.sub(r'\b100\.(?:6[4-9]|[7-9]\d|1[0-1]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b', '[REDACTED_TAILSCALE_IP]', text)
    text = re.sub(r'\b192\.168\.\d{1,3}\.\d{1,3}\b', '[REDACTED_LOCAL_IP]', text)
    text = re.sub(r'\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[REDACTED_INTRANET_IP]', text)
    return text

def _clean_and_truncate_content(content: str, max_lines: int = 15) -> str:
    """
    Detects massive automated tool results, terminal dumps, or file arrays 
    and truncates them to protect the model from context contamination.
    """
    content = _mask_credentials(content)
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
    """
    Removes <think> loops globally, BUT safely ignores them if they are 
    written inside Markdown ``` code block fences.
    """
    code_blocks = []
    
    # 1. Mask code blocks by replacing them with temporary placeholder tokens
    def preserve_code(match):
        code_blocks.append(match.group(0))
        return f"__CODE_BLOCK_PLACEHOLDER_{len(code_blocks)-1}__"

    temp_text = re.sub(r'```[\s\S]*?```', preserve_code, text)

    # 2. Execute the thought tag purge safely on the remaining open text
    temp_text = re.sub(r'<(think|thinking|thought)>[\s\S]*?</\1>', '', temp_text, flags=re.IGNORECASE)
    temp_text = re.sub(r'\[(think|thinking|thought)\][\s\S]*?\[/\1\]', '', temp_text, flags=re.IGNORECASE)

    # 3. Restore the intact code blocks back into their original positions
    for i, block in enumerate(code_blocks):
        temp_text = temp_text.replace(f"__CODE_BLOCK_PLACEHOLDER_{i}__", block)

    return temp_text

def _parse_json_pipeline(filepath: str) -> List[Dict[str, str]]:
    """Independent parsing handler for structured JSON chat logs."""
    import json
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    messages = data.get("messages", data if isinstance(data, list) else [])
    
    normalized_messages = []
    for m in messages:
        if m:
            role = str(m.get("role", "user")).lower()
            content = str(m.get("content", ""))
            
            content = _strip_thought_blocks_safely(content)
            content = _clean_and_truncate_content(content)
            
            if content.strip():
                normalized_messages.append({"role": role, "content": content.strip()})
    return normalized_messages

def _parse_plaintext_pipeline(raw_text: str) -> List[Dict[str, str]]:
    """Independent parsing handler for unstructured TXT, MD, and PDF payloads."""
    raw_text = _strip_thought_blocks_safely(raw_text)

    if not raw_text.strip():
        return [{"role": "user", "content": "Initial workspace handshake segment analyzed."}]

    # Find boundaries to prevent triggering "User:" roles inside of a code string
    code_block_spans = [m.span() for m in re.finditer(r'```[\s\S]*?```', raw_text)]

    pattern = re.compile(r'(?mi)^(###\s+)?(user|assistant|ai|system|human|bot):\s*')
    all_matches = list(pattern.finditer(raw_text))
    
    matches = []
    for m in all_matches:
        start = m.start()
        in_code = any(c_start <= start <= c_end for c_start, c_end in code_block_spans)
        if not in_code:
            matches.append(m)

    # If no explicit conversational tags are found, treat the whole file as a user dump
    if not matches:
        return [{"role": "user", "content": _clean_and_truncate_content(raw_text.strip())}]

    cleaned_messages = []
    for i in range(len(matches)):
        start_idx = matches[i].end()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(raw_text)
        
        role = matches[i].group(2).lower()
        if role in ('human', 'user'): role = 'user'
        elif role in ('ai', 'bot', 'assistant'): role = 'assistant'
            
        content = raw_text[start_idx:end_idx].strip()
        content = _clean_and_truncate_content(content)
        
        if content:
            cleaned_messages.append({"role": role, "content": content})

    if not cleaned_messages:
        raise ValueError("Could not parse structural content blocks out of the file layout.")

    return cleaned_messages

def parse_lm_studio_file(filepath: str) -> List[Dict[str, str]]:
    """
    Main Dispatcher: Routes files to their respective extension parsing pipelines.
    """
    ext = os.path.splitext(filepath)[1].lower()

    if ext == '.json':
        return _parse_json_pipeline(filepath)
        
    elif ext in ('.txt', '.md'):
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_text = f.read()
        return _parse_plaintext_pipeline(raw_text)

    elif ext == '.pdf':
        raw_text = _extract_text_from_pdf(filepath)
        return _parse_plaintext_pipeline(raw_text)
        
    else:
        raise ValueError(f"Unsupported file format: {ext}")