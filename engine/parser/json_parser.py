"""
JSON Parser Module - Dedicated parsing logic for JSON conversation logs
with schema-guided recovery for malformed files
"""

import os
import json
import re
from typing import List, Dict
from pathlib import Path

try:
    from json_repair import repair_json
    JSON_REPAIR_AVAILABLE = True
except ImportError:
    JSON_REPAIR_AVAILABLE = False

from .base_parser import BaseParser
from engine.tokenizer import tracker


class JSONParser(BaseParser):
    """Parser specifically designed for JSON-formatted conversation logs."""
    
    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.json']
        self.max_token_count = 200000  # 200k token limit
        self.max_file_size_mb = 50
        
    def parse(self, filepath: str) -> List[Dict[str, str]]:
        """
        Parses a JSON-formatted conversation log file with recovery strategies.
        
        Error Handling:
            - FileNotFoundError: File does not exist at specified path
            - ValueError: Invalid JSON syntax, encoding issues, or file too large
            - PermissionError: Cannot read file due to permissions
            
        Recovery Features:
            - Progressive JSON parsing with multiple recovery attempts
            - Schema-guided fallback for malformed files
            - Token count validation (max 200k tokens)
            - File size validation (max 50MB)
        
        Returns:
            List of normalized message dictionaries with 'role' and 'content' keys.
            Empty list if file is empty or contains no valid messages.
        """
        # Step 1: File existence check
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"JSON conversation log not found: {filepath}")
        
        # Step 2: File size validation (prevent processing massive files)
        file_size = os.path.getsize(filepath)
        if file_size > self.max_file_size_mb * 1024 * 1024:
            raise ValueError(
                f"File too large: {file_size / (1024*1024):.1f}MB exceeds maximum supported size of {self.max_file_size_mb}MB"
            )
        
        # Step 3: Safe JSON parsing with schema-guided recovery
        data = self._load_json_with_recovery(filepath)
        
        # Step 3b: Token count validation
        self._validate_token_count(data, filepath)
        
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
    
    def _load_json_with_recovery(self, filepath: str) -> Dict:
        """
        Attempts to parse JSON with progressive recovery strategies for malformed files.
        
        Recovery Strategy:
        1. Direct JSON parse
        2. Remove trailing commas and fix common syntax errors
        3. Apply json-repair library (if available)
        4. Extract valid JSON from malformed content using regex
        
        Args:
            filepath: Path to the JSON file
            
        Returns:
            Parsed JSON data
            
        Raises:
            ValueError: If all recovery strategies fail
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_content = f.read()
        
        recovery_attempts = []
        
        # Attempt 1: Direct parse
        try:
            data = json.loads(raw_content)
            recovery_attempts.append("Direct parse successful")
            return data
        except json.JSONDecodeError as e:
            recovery_attempts.append(f"Attempt 1 (direct): Line {e.lineno}, {e.msg}")
        
        # Attempt 2: Fix common syntax errors
        try:
            fixed_content = self._fix_common_json_errors(raw_content)
            data = json.loads(fixed_content)
            recovery_attempts.append("Attempt 2: Common error fixes successful")
            print(f"✓ JSON recovered after fixing common syntax errors")
            return data
        except Exception as e:
            recovery_attempts.append(f"Attempt 2 (fix errors): {str(e)}")
        
        # Attempt 3: Use json-repair library
        if JSON_REPAIR_AVAILABLE:
            try:
                repaired_content = repair_json(raw_content, return_objects=False)
                data = json.loads(repaired_content)
                recovery_attempts.append("Attempt 3: json-repair library successful")
                print(f"✓ JSON recovered using json-repair library")
                return data
            except Exception as e:
                recovery_attempts.append(f"Attempt 3 (json-repair): {str(e)}")
        else:
            recovery_attempts.append("Attempt 3: Skipped (json-repair not installed)")
        
        # Attempt 4: Extract JSON from malformed content
        try:
            # Try to find the main JSON object even if there's garbage around it
            json_match = re.search(r'\{[\s\S]*\}', raw_content)
            if json_match:
                extracted = json_match.group(0)
                data = json.loads(extracted)
                recovery_attempts.append("Attempt 4: Extracted valid JSON from malformed content")
                print(f"✓ JSON recovered by extracting valid portion")
                return data
        except Exception as e:
            recovery_attempts.append(f"Attempt 4 (extraction): {str(e)}")
        
        # All attempts failed
        error_summary = "\n".join(recovery_attempts)
        raise ValueError(
            f"Failed to parse JSON file '{os.path.basename(filepath)}' after all recovery attempts:\n{error_summary}"
        )
    
    def _fix_common_json_errors(self, content: str) -> str:
        """
        Fixes common JSON syntax errors.
        
        Args:
            content: Raw JSON string
            
        Returns:
            Fixed JSON string
        """
        # Remove trailing commas before closing brackets/braces
        content = re.sub(r',\s*([\]}])', r'\1', content)
        
        # Fix unquoted keys (common in JavaScript-style objects)
        content = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', content)
        
        # Remove single quotes and replace with double quotes for strings
        # This is a simplified approach and may not handle all edge cases
        content = re.sub(r"'([^'\\]*(\\.[^'\\]*)*)'", r'"\1"', content)
        
        # Remove comments (// and /* */)
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'/\*[^*]*\*+(?:[^/*][^*]*\*+)*/', '', content)
        
        return content
    
    def _validate_token_count(self, data: Dict, filepath: str):
        """
        Validates that the parsed content doesn't exceed token limits.
        
        Args:
            data: Parsed JSON data
            filepath: Path to the original file
            
        Raises:
            ValueError: If token count exceeds limit
        """
        # Extract all text content from the data
        text_content = self._extract_text_from_data(data)
        token_count = tracker.count_tokens(text_content)
        
        if token_count > self.max_token_count:
            raise ValueError(
                f"Content exceeds maximum token limit: {token_count} tokens (limit: {self.max_token_count}). "
                f"File '{os.path.basename(filepath)}' is too large for processing."
            )
    
    def _extract_text_from_data(self, data) -> str:
        """
        Recursively extracts all text content from parsed JSON data.
        
        Args:
            data: Parsed JSON data (dict, list, or primitive)
            
        Returns:
            Concatenated text content
        """
        if isinstance(data, dict):
            return " ".join(self._extract_text_from_data(v) for v in data.values())
        elif isinstance(data, list):
            return " ".join(self._extract_text_from_data(item) for item in data)
        elif isinstance(data, str):
            return data
        else:
            return str(data)
