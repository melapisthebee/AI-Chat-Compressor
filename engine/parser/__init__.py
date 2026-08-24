"""
Parser Module - LM Studio raw JSON conversation logs only.
"""

import os

from .base_parser import BaseParser
from .json_parser import JSONParser
from .benchmark import ParserBenchmark, run_parser_benchmarks

SUPPORTED_EXTENSIONS = {'.json'}


def get_parser_for_file(filepath: str) -> BaseParser:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == '.json':
        return JSONParser()
    raise ValueError(f"Unsupported file format: {ext}. Only .json is accepted.")


def parse_lm_studio_file(filepath: str):
    """Parse an LM Studio raw JSON chat export. Returns list of {'role', 'content'} dicts."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file format: {ext}. Only .json files are accepted."
        )
    return JSONParser().parse(filepath)


__all__ = [
    'parse_lm_studio_file',
    'get_parser_for_file',
    'BaseParser',
    'JSONParser',
    'ParserBenchmark',
    'run_parser_benchmarks',
]


