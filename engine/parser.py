import os
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
    """
    Detects and redacts sensitive API keys, authorization tokens, 
    and Tailscale/Local networking IP patterns from text contexts.
    """
    # 1. Mask assignment patterns for keys/tokens/secrets (handles json, env, and plaintext styles)
    text = re.sub(
        r'((?:api[-_]?key|token|secret|password|pass|sk[-_]lm)\s*[:=]\s*["\']?)[a-zA-Z0-9_\-:]+(["\']?)', 
        r'\1[REDACTED_SECRET]\2', 
        text, 
        flags=re.IGNORECASE
    )
    
    # 2. Mask explicit Tailscale virtual networking IP configurations (100.64.0.0/10 range)
    text = re.sub(r'\b100\.(?:6[4-9]|[7-9]\d|1[0-1]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b', '[REDACTED_TAILSCALE_IP]', text)
    
    # 3. Mask classic local loopback and standard private intranet subnets (192.168.x.x, 10.x.x.x)
    text = re.sub(r'\b192\.168\.\d{1,3}\.\d{1,3}\b', '[REDACTED_LOCAL_IP]', text)
    text = re.sub(r'\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[REDACTED_INTRANET_IP]', text)
    
    return text

def _clean_and_truncate_content(content: str, max_lines: int = 15) -> str:
    """
    Detects massive automated tool results, terminal dumps, or file arrays 
    and truncates them to protect the model from context contamination.
    """
    # Run the credential mask over the content block first
    content = _mask_credentials(content)
    
    # Quick bypass for short, normal conversational messages
    lines = content.splitlines()
    if len(lines) <= max_lines:
        return content

    # Check if the content blocks match automated patterns (tool execution blocks, raw file listings)
    is_tool_block = any(tag in content for tag in ["<tool_call>", "<tool_response>", "<function=", "jsonrpc"])
    
    # Check for repetitive hex file hashes or file dumps (e.g., lines ending in hex names)
    # If more than 50% of the lines look like raw data, flag it as a dump
    hex_or_path_lines = [l for l in lines if re.search(r'(^[a-fA-F0-9_-]{12,})|(\\|\/)', l)]
    is_data_dump = len(hex_or_path_lines) / len(lines) > 0.5

    if is_tool_block or is_data_dump:
        header = "\n".join(lines[:5])
        footer = "\n".join(lines[-3:]) if len(lines) > 8 else ""
        return f"{header}\n\n[⚠️ SYSTEM PARSER NOTICE: Truncated {len(lines) - 8} lines of automated tool/cache file listings to prevent context contamination]\n\n{footer}"
    
    return content

def parse_lm_studio_file(filepath: str) -> List[Dict[str, str]]:
    """
    Parses conversation history from JSON, TXT, MD, or PDF files,
    purges historical thinking loops to optimize context density,
    and normalizes them into standard message dictionaries.
    """
    ext = os.path.splitext(filepath)[1].lower()
    raw_text = ""

    # Reuseable pattern to clean out thinking blocks across both parser branches
    thought_patterns = [
        r'<(think|thinking|thought)>[\s\S]*?</\1>',
        r'\[(think|thinking|thought)\][\s\S]*?\[/\1\]'
    ]

    if ext == '.json':
        import json
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        messages = data.get("messages", data if isinstance(data, list) else [])
        
        normalized_messages = []
        for m in messages:
            if m:
                role = str(m.get("role", "user")).lower()
                content = str(m.get("content", ""))
                
                for pattern in thought_patterns:
                    content = re.sub(pattern, '', content, flags=re.IGNORECASE)
                
                # RUN TRUNCATION AND MASKING FILTER HERE
                content = _clean_and_truncate_content(content)
                
                normalized_messages.append({"role": role, "content": content.strip()})
        return normalized_messages

    elif ext in ('.txt', '.md'):
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_text = f.read()

    elif ext == '.pdf':
        raw_text = _extract_text_from_pdf(filepath)
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    if not raw_text.strip():
        raise ValueError("The provided file appears to be completely empty.")

    # TOKEN SAVER PURGE: Strip historical thought text walls from Text/PDF strings 
    # right at ingestion. This saves immense prompt token overhead.
    for pattern in thought_patterns:
        raw_text = re.sub(pattern, '', raw_text, flags=re.IGNORECASE)

    # Re-validate that the file isn't empty after stripping out reasoning blocks
    if not raw_text.strip():
        return [{"role": "user", "content": "Initial workspace handshake segment analyzed."}]

    # Find code block boundaries to ignore false positives inside code fences
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
        return [{"role": "user", "content": _mask_credentials(raw_text.strip())}]

    cleaned_messages = []
    for i in range(len(matches)):
        start_idx = matches[i].end()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(raw_text)
        
        role = matches[i].group(2).lower()
        if role in ('human', 'user'):
            role = 'user'
        elif role in ('ai', 'bot', 'assistant'):
            role = 'assistant'
            
        content = raw_text[start_idx:end_idx].strip()
        
        # Executes sanitization and data truncation filters
        content = _clean_and_truncate_content(content)
        
        if content:
            cleaned_messages.append({"role": role, "content": content})

    if not cleaned_messages:
        raise ValueError("Could not parse structural content blocks out of the file layout.")

    return cleaned_messages