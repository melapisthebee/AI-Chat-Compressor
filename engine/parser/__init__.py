"""
Parser Module - File Type-Specific Parsing Factory

This module provides a factory pattern for parsing different file types.
Each file format (.json, .txt, .md, .pdf) has its own dedicated parser class
with specialized logic for handling that format's characteristics.
"""

import os
from typing import List, Dict, Callable

from .base_parser import BaseParser
from .json_parser import JSONParser
from .txt_parser import TXTParser
from .markdown_parser import MarkdownParser
from .pdf_parser import PDFParser


# Registry of available parsers by file extension
PARSER_REGISTRY: Dict[str, type] = {
    '.json': JSONParser,
    '.txt': TXTParser,
    '.md': MarkdownParser,
    '.pdf': PDFParser,
}


def get_parser_for_file(filepath: str) -> BaseParser:
    """
    Factory function to retrieve the appropriate parser for a given file.
    
    Args:
        filepath: Path to the file to be parsed
        
    Returns:
        Instance of the appropriate BaseParser subclass
        
    Raises:
        ValueError: If file extension is not supported
    """
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext not in PARSER_REGISTRY:
        raise ValueError(f"Unsupported file format: {ext}. Supported formats: {list(PARSER_REGISTRY.keys())}")
    
    parser_class = PARSER_REGISTRY[ext]
    return parser_class()


def parse_lm_studio_file(filepath: str) -> List[Dict[str, str]]:
    """
    Main entry point for parsing LM Studio conversation files.
    Routes to the appropriate format-specific parser based on file extension.
    
    Args:
        filepath: Path to the file to be parsed
        
    Returns:
        List of normalized message dictionaries with 'role' and 'content' keys
        
    Raises:
        ValueError: If file extension is not supported
        FileNotFoundError: If file does not exist
        Various parsing exceptions from specific parser implementations
    """
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext not in PARSER_REGISTRY:
        raise ValueError(f"Unsupported file format: {ext}. Supported formats: {list(PARSER_REGISTRY.keys())}")
    
    # Use factory to get the appropriate parser instance
    parser = get_parser_for_file(filepath)
    
    # Each parser has its own parse method with different signatures
    if isinstance(parser, (JSONParser, PDFParser)):
        # These parsers take a filepath and handle file reading internally
        return parser.parse(filepath)
    else:
        # Text-based parsers need content loaded first
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_content = f.read()
        
        return parser.parse(raw_content)


# Backward compatibility - expose the old function name directly
__all__ = [
    'parse_lm_studio_file',
    'get_parser_for_file', 
    'BaseParser',
    'JSONParser',
    'TXTParser',
    'MarkdownParser',
    'PDFParser',
]
