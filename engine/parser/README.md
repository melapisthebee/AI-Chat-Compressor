# Parser Module

This module provides format-specific parsers for processing conversation logs and other file types.

## Features

### 1. Format-Specific Parsers
- **JSONParser**: Handles JSON conversation logs with schema-guided recovery
- **TXTParser**: Processes plain text conversation exports
- **MarkdownParser**: Parses Markdown-formatted conversation logs
- **PDFParser**: Extracts text from PDF conversation exports

### 2. Schema-Guided Recovery (JSON)
The JSON parser implements progressive recovery strategies for malformed files:

1. **Direct Parse**: Attempts standard JSON parsing
2. **Syntax Correction**: Fixes common errors (trailing commas, unquoted keys, comments)
3. **json-repair Library**: Uses character-level correction if available
4. **Content Extraction**: Extracts valid JSON from malformed content

### 3. File Size Validation
- **Maximum File Size**: 50MB
- **Maximum Token Count**: 200,000 tokens
- Automatic validation before processing
- Clear error messages if limits exceeded

### 4. Performance Benchmarking
Built-in benchmarking utilities to measure parser performance:

```python
from engine.parser import run_parser_benchmarks

# Run benchmarks on sample files
benchmark = run_parser_benchmarks()

# Generate report
print(benchmark.generate_report())
```

## Usage

### Basic Parsing

```python
from engine.parser import parse_lm_studio_file

messages = parse_lm_studio_file("conversation.json")
# Returns: List[Dict[str, str]] with 'role' and 'content' keys
```

### Using Specific Parsers

```python
from engine.parser import get_parser_for_file

parser = get_parser_for_file("conversation.json")
messages = parser.parse("conversation.json")
```

### Performance Benchmarking

```python
from engine.parser import ParserBenchmark

benchmark = ParserBenchmark()

# Single file benchmark
result = benchmark.benchmark_single_file("conversation.json")
print(f"Runtime: {result['avg_runtime_seconds']:.3f}s")
print(f"Tokens: {result['avg_tokens']}")

# Directory benchmark
results = benchmark.benchmark_directory("./samples")
print(benchmark.generate_report())
benchmark.save_report()
```

## Error Handling

All parsers provide comprehensive error handling:

- **FileNotFoundError**: File does not exist
- **ValueError**: Invalid format, file too large, or token limit exceeded
- **PermissionError**: Cannot read file due to permissions
- **JSONDecodeError**: Invalid JSON syntax (with recovery attempts)

## Configuration

Parsers support the following configuration:

```python
parser = JSONParser()
parser.max_file_size_mb = 50  # Maximum file size in MB
parser.max_token_count = 200000  # Maximum token count
```

## Token Counting

All parsers integrate with the project's tokenizer for accurate token counting:

- Uses `cl100k_base` encoding (matching Llama-3/GPT standard)
- Validates token count before processing
- Provides token metrics in benchmark results

## Performance Metrics

Benchmark results include:

- **Runtime**: Average, min, max, and standard deviation
- **Throughput**: Tokens per second, messages per second
- **File Statistics**: Size, token count, message count
- **Success Rate**: Percentage of successful parses

## Example Output

```
================================================================================
PARSER PERFORMANCE BENCHMARK REPORT
Generated: 2024-01-15 14:30:00
================================================================================

SUMMARY
----------------------------------------
Total files benchmarked: 5
Successful runs: 5
Failed runs: 0
Average runtime: 0.523 seconds
Average tokens processed: 12,450
Average messages parsed: 85
Average throughput: 23,800 tokens/second

DETAILED RESULTS
----------------------------------------

✓ conversation_001.json
   Extension: .json
   File size: 2.35 MB
   Runtime: 0.456s (min: 0.445s, max: 0.467s)
   Tokens: 10,234
   Messages: 72
   Throughput: 22,400 tokens/s

✓ conversation_002.json
   Extension: .json
   File size: 3.12 MB
   Runtime: 0.589s (min: 0.578s, max: 0.601s)
   Tokens: 14,567
   Messages: 98
   Throughput: 24,700 tokens/s
```

## Dependencies

- `json_repair` (optional): For enhanced JSON recovery
- `tqdm` (recommended): For progress bars in benchmarks
- Project's tokenizer module for token counting
