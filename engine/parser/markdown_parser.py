"""
Markdown Parser Module - Dedicated parsing logic for Markdown files
"""

import re
from typing import List, Dict

from .base_parser import BaseParser


class MarkdownParser(BaseParser):
    """Parser specifically designed for Markdown (.md) files."""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.md']
        
    def parse(self, content: str) -> List[Dict[str, str]]:
        """
        Parse Markdown file with role detection and MD-specific processing.
        
        Args:
            content: Raw text content from the markdown file
            
        Returns:
            List of normalized message dictionaries with 'role' and 'content' keys
        """
        # First remove thought blocks while preserving code blocks
        content = self._strip_thought_blocks_safely(content)

        if not content.strip():
            return [{"role": "user", "content": self._clean_and_truncate_content("Initial workspace handshake segment analyzed.", skip_truncation=True)}]

        # In markdown, we need to be more careful about code blocks which use ``` syntax
        # Extract fenced code blocks first to avoid false role detection inside them
        code_block_pattern = r'```(?:\w+)?\n?([\s\S]*?)```'
        preserved_blocks = []
        
        def save_code_block(match):
            preserved_blocks.append(match.group(0))
            return f"__MD_CODE_BLOCK_{len(preserved_blocks)-1}__"
        
        temp_content = re.sub(code_block_pattern, save_code_block, content)
        
        # Pattern to detect role markers (can be headers or inline)
        pattern = re.compile(r'(?mi)^(#{1,6}\s*)?(###\s+)?(user|assistant|ai|system|human|bot):\s*', re.MULTILINE)
        all_matches = list(pattern.finditer(temp_content))

        cleaned_messages = []
        
        for i, match in enumerate(all_matches):
            start_idx = match.end()
            end_idx = all_matches[i+1].start() if i + 1 < len(all_matches) else len(temp_content)
            
            role = match.group(3).lower()
            # Normalize role names
            if role in ('human', 'user'): 
                role = 'user'
            elif role in ('ai', 'bot', 'assistant'): 
                role = 'assistant'
                
            msg_content = temp_content[start_idx:end_idx].strip()
            
            # Restore preserved code blocks
            for idx, block in enumerate(preserved_blocks):
                placeholder = f"__MD_CODE_BLOCK_{idx}__"
                if placeholder in msg_content:
                    msg_content = msg_content.replace(placeholder, block)
            
            # Apply truncation logic (md files typically preserve full content)
            msg_content = self._clean_and_truncate_content(msg_content, skip_truncation=True)
            
            if msg_content and msg_content != f"__MD_CODE_BLOCK_{len(preserved_blocks)-1}__":
                cleaned_messages.append({"role": role, "content": msg_content})

        # If no role markers found, treat entire content as a single user message
        if not cleaned_messages:
            # Restore code blocks in the full content
            for idx, block in enumerate(preserved_blocks):
                placeholder = f"__MD_CODE_BLOCK_{idx}__"
                temp_content = temp_content.replace(placeholder, block)
            
            return [{"role": "user", "content": self._clean_and_truncate_content(temp_content.strip(), skip_truncation=True)}]

        if not cleaned_messages:
            raise ValueError("Could not parse structural content blocks out of the file layout.")

        return cleaned_messages
