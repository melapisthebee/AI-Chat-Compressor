"""
Base Parser Module - Abstract Base Class for File Type-Specific Parsing
"""

from abc import ABC, abstractmethod
from typing import List, Dict
import re


class BaseParser(ABC):
    """Abstract base class for file-type-specific parsers."""
    
    def __init__(self):
        self.supported_extensions: List[str] = []
        
    @abstractmethod
    def parse(self, content: str) -> List[Dict[str, str]]:
        """Parse content and return normalized messages with role/content structure."""
        pass
    
    def _strip_thought_blocks_safely(self, text: str) -> str:
        """Preserve code blocks while removing thought tags."""
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
    
    def _mask_credentials(self, text: str) -> str:
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
    
    def _clean_and_truncate_content(self, content: str, max_lines: int = 15, skip_truncation: bool = False) -> str:
        """Detects massive automated tool results and truncates them unless skip_truncation is True."""
        # Always mask credentials regardless of truncation setting
        content = self._mask_credentials(content)
        
        if skip_truncation:
            return content

        lines = content.splitlines()
        if len(lines) <= max_lines:
            return content

        is_tool_block = any(tag in content for tag in ["", "","<function=", "jsonrpc"])
        path_regex = r'(^[a-fA-F0-9_-]{12,})|([A-Za-z]:\\[\w\.-]+\\[\w\.-]+)|(/[\w\.-]+/[\w\.-]+)'
        hex_or_path_lines = [l for l in lines if re.search(path_regex, l)]
        is_data_dump = len(hex_or_path_lines) / len(lines) > 0.5

        if is_tool_block or is_data_dump:
            header = "\n".join(lines[:5])
            footer = "\n".join(lines[-3:]) if len(lines) > 8 else ""
            return f"{header}\n\n[⚠️ SYSTEM PARSER NOTICE: Truncated {len(lines) - 8} lines of automated tool/cache file listings to prevent context contamination]\n\n{footer}"
        
        return content
