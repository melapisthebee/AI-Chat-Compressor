"""
Parser Module - File Type-Specific Parsing Factory

Supported formats: .txt, .md (LM Studio chat exports).
"""

import os
from typing import List, Dict

from .base_parser import BaseParser
from .json_parser import JSONParser
from .txt_parser import TXTParser
from .markdown_parser import MarkdownParser
from .benchmark import ParserBenchmark, run_parser_benchmarks


SUPPORTED_EXTENSIONS = {'.txt', '.md'}


def get_parser_for_file(filepath: str) -> BaseParser:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.json':
        return JSONParser()
    elif ext == '.txt':
        return TXTParser()
    elif ext == '.md':
        return MarkdownParser()
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported: .txt, .md")


def parse_lm_studio_file(filepath: str) -> List[Dict[str, str]]:
    """Parse an LM Studio chat export. Returns list of {role, content} dicts."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file format: {ext}. "
            f"LM Studio exports only accept .txt and .md files."
        )

    parser = get_parser_for_file(filepath)

    if isinstance(parser, JSONParser):
        return parser.parse(filepath)

    with open(filepath, 'r', encoding='utf-8') as f:
        raw_content = f.read()

    return parser.parse(raw_content)


__all__ = [
    'parse_lm_studio_file',
    'get_parser_for_file',
    'BaseParser',
    'JSONParser',
    'TXTParser',
    'MarkdownParser',
    'ParserBenchmark',
    'run_parser_benchmarks',
]
