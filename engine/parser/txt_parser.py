"""
TXT Parser Module - Dedicated parsing logic for plain text conversation logs
"""

import re
from typing import List, Dict

from .base_parser import BaseParser


class TXTParser(BaseParser):
    """Parser specifically designed for plain text (.txt) files."""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.txt']
        
    def parse(self, content: str) -> List[Dict[str, str]]:
        """
        Parse plain text file with role detection and truncation logic.
        
        Args:
            content: Raw text content from the file
            
        Returns:
            List of normalized message dictionaries with 'role' and 'content' keys
        """
        content = self._strip_thought_blocks_safely(content)

        if not content.strip():
            return [{"role": "user", "content": self._clean_and_truncate_content("Initial workspace handshake segment analyzed.", skip_truncation=True)}]

        # Extract code blocks to preserve them during parsing
        code_block_spans = [m.span() for m in re.finditer(r'```[\s\S]*?```', content)]
        
        # Pattern to detect role prefixes (handles various formats)
        pattern = re.compile(r'(?mi)^(###\s+)?(user|assistant|ai|system|human|bot):\s*')
        all_matches = list(pattern.finditer(content))
        
        matches = []
        for m in all_matches:
            start = m.start()
            # Skip matches inside code blocks
            in_code = any(c_start <= start <= c_end for c_start, c_end in code_block_spans)
            if not in_code:
                matches.append(m)

        # If no role markers found, treat entire content as a single user message
        if not matches:
            return [{"role": "user", "content": self._clean_and_truncate_content(content.strip(), skip_truncation=True)}]

        cleaned_messages = []
        for i in range(len(matches)):
            start_idx = matches[i].end()
            end_idx = matches[i+1].start() if i + 1 < len(matches) else len(content)
            
            role = matches[i].group(2).lower()
            # Normalize role names
            if role in ('human', 'user'): 
                role = 'user'
            elif role in ('ai', 'bot', 'assistant'): 
                role = 'assistant'
                
            msg_content = content[start_idx:end_idx].strip()
            # Apply truncation logic (txt files typically have truncation enabled)
            msg_content = self._clean_and_truncate_content(msg_content, skip_truncation=False)
            
            if msg_content:
                cleaned_messages.append({"role": role, "content": msg_content})

        if not cleaned_messages:
            raise ValueError("Could not parse structural content blocks out of the file layout.")

        return cleaned_messages
