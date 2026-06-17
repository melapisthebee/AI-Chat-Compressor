"""
Parser Module - File Type-Specific Parsing Factory

This module provides a factory pattern for parsing different file types.
Each file format (.json, .txt, .md, .pdf) has its own dedicated parser class
with specialized logic for handling that format's characteristics.

Features:
    - Format-specific parsers (JSON, TXT, Markdown, PDF)
    - Schema-guided recovery for malformed JSON files
    - File size validation (max 50MB or 200k tokens)
    - Performance benchmarking utilities
"""

import os
from typing import List, Dict, Callable

from .base_parser import BaseParser
from .json_parser import JSONParser
from .txt_parser import TXTParser
from .markdown_parser import MarkdownParser
from .pdf_parser import PDFParser
from .benchmark import ParserBenchmark, run_parser_benchmarks


def get_parser_for_file(filepath: str) -> BaseParser:
    """
    Get the appropriate parser for a given file based on its extension.
    
    Args:
        filepath: Path to the file to be parsed
        
    Returns:
        Instance of the appropriate BaseParser subclass
        
    Raises:
        ValueError: If file extension is not supported
    """
    ext = os.path.splitext(filepath)[1].lower()
    
    if ext == '.json':
        return JSONParser()
    elif ext == '.txt':
        return TXTParser()
    elif ext == '.md':
        return MarkdownParser()
    elif ext == '.pdf':
        return PDFParser()
    else:
        raise ValueError(f"Unsupported file format: {ext}")


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
    'ParserBenchmark',
    'run_parser_benchmarks',
]
