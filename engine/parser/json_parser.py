"""
JSON Parser Module - Dedicated parsing logic for JSON conversation logs
"""

import os
import json
from typing import List, Dict

from .base_parser import BaseParser


class JSONParser(BaseParser):
    """Parser specifically designed for JSON-formatted conversation logs."""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.json']
        
    def parse(self, filepath: str) -> List[Dict[str, str]]:
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
                
                content = self._strip_thought_blocks_safely(content)
                content = self._clean_and_truncate_content(content, skip_truncation=False)
                
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
