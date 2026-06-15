# Enhanced Token Management Implementation

## Overview

This document describes the implementation of enhanced token management features for the LM Compressor application, including:

1. **Streaming Chunk Processing** - Memory-efficient processing of large files
2. **Configurable Token Budget Settings** - UI-based configuration
3. **Token Usage Dashboard** - Compression ratio visualization per project
4. **Optimized Sliding Window Logic** - Prevents context fragmentation

---

## 1. Streaming Chunk Processing

### Implementation Details

**File**: `engine/streaming_processor.py`

The `StreamingTokenProcessor` class provides memory-efficient processing for large conversation files:

- **Adaptive Chunking**: Automatically detects file size and chooses appropriate processing strategy
- **Sliding Windows**: Creates overlapping token windows to prevent context fragmentation
- **Memory Management**: Forces garbage collection periodically during large file processing
- **Statistics Tracking**: Monitors processing time, memory usage, and compression ratios

### Key Features

```python
class StreamingTokenProcessor:
    - max_target_tokens: Maximum target token count (default: 10,000)
    - chunk_size_tokens: Size of each processing chunk (default: 8,000)
    - overlap_tokens: Overlap between chunks (default: 25% of chunk size)
    - preserve_recent_tokens: Recent tokens to preserve unmodified (default: 5,000)
```

### Usage

```python
processor = StreamingTokenProcessor()
result = processor.stream_process_large_file(
    text=conversation_text,
    process_chunk_callback=process_chunk_callback,
    preserve_tail=True
)
```

---

## 2. Configurable Token Budget Settings

### Implementation Details

**File**: `engine/streaming_processor.py` (TokenBudgetManager class)

The `TokenBudgetManager` provides validation and configuration for token budget settings:

- **Input Validation**: Ensures settings are within acceptable ranges
- **Consistency Checks**: Maintains relationships between chunk size and overlap
- **UI Integration**: Provides settings widgets for user configuration

### Validated Settings

| Setting | Min | Max | Default | Description |
|---------|-----|-----|---------|-------------|
| max_target_tokens | 1,000 | 100,000 | 10,000 | Maximum target token count |
| chunk_size_tokens | 1,000 | 16,000 | 8,000 | Size of processing chunks |
| overlap_tokens | 200 | 50% of chunk | 2,000 | Overlap between chunks |
| preserve_recent_tokens | 500 | 20,000 | 5,000 | Recent tokens to preserve |

### UI Component

**File**: `gui/components/token_dashboard.py`

```python
TokenBudgetSettingsWidget:
    - Interactive spinboxes for all budget parameters
    - Real-time validation feedback
    - Apply/Reset buttons
    - Settings change signals for integration
```

---

## 3. Token Usage Dashboard

### Implementation Details

**File**: `gui/components/token_dashboard.py`

The `TokenDashboardWidget` provides comprehensive visualization of token usage:

#### Dashboard Components

1. **Summary Cards**
   - Total Raw Tokens
   - Compressed Tokens
   - Compression Ratio
   - Average Processing Time

2. **Progress Bar**
   - Visual representation of token budget usage
   - Color-coded warnings at thresholds

3. **Project Statistics Table**
   - Per-project breakdown
   - Compression ratio visualization
   - Status indicators

#### Dashboard Data Structure

```python
{
    'total_raw_tokens': 15000,
    'total_compressed_tokens': 4500,
    'compression_ratio': '30.0%',
    'compression_ratio_decimal': 0.30,
    'chunks_processed': 3,
    'processing_time_seconds': '12.45',
    'peak_memory_mb': '45.23',
    'memory_efficiency': '331 tokens/MB',
    'chunk_size': 8000,
    'overlap_size': 2000,
    'max_target_tokens': 10000
}
```

### Integration

The dashboard integrates with the main window and updates automatically after each processing session:

```python
# In handle_worker_success method
if dashboard_data:
    self.token_dashboard.update_dashboard(project_name, dashboard_data)
    self.current_project_stats[project_name] = dashboard_data
```

---

## 4. Optimized Sliding Window Logic

### Implementation Details

**File**: `engine/streaming_processor.py`

The `create_sliding_windows` method implements intelligent chunking:

```python
def create_sliding_windows(self, tokens, chunk_size=None, overlap=None):
    # Creates overlapping windows with configurable parameters
    # Yields (start_index, end_index, token_chunk) tuples
    
    # Key optimizations:
    # 1. Configurable overlap (default: 25% of chunk size)
    # 2. Adaptive step size (chunk_size - overlap)
    # 3. Minimum progress guarantee (at least 50% of chunk size)
    # 4. Tail preservation for recent context
```

### Context Fragmentation Prevention

The sliding window logic prevents context fragmentation through:

1. **Configurable Overlap**: Ensures context continuity between chunks
2. **Minimum Overlap Threshold**: 200 tokens minimum to maintain context
3. **Maximum Overlap Ratio**: 50% cap to prevent excessive redundancy
4. **Tail Preservation**: Recent tokens preserved unmodified

### Example Window Creation

```python
# With chunk_size=8000, overlap=2000
Window 1: tokens[0:8000]
Window 2: tokens[6000:14000]  # 2000 token overlap
Window 3: tokens[12000:20000] # 2000 token overlap
```

---

## Files Modified/Created

### New Files

1. `engine/streaming_processor.py` - Core streaming processing logic
2. `gui/components/token_dashboard.py` - Dashboard and settings widgets
3. `gui/components/__init__.py` - Component exports
4. `ENHANCED_TOKEN_MANAGEMENT.md` - This documentation

### Modified Files

1. `engine/compression.py`
   - Added StreamingTokenProcessor integration
   - Enhanced process_and_adapt method
   - Dashboard data return

2. `engine/__init__.py`
   - Added new exports

3. `gui/main_window.py`
   - Tabbed interface with dashboard
   - Settings dialog integration
   - Enhanced worker signal handling

---

## Usage Examples

### Basic Usage

```python
from engine.compression import CompressionEngine
from engine.streaming_processor import StreamingTokenProcessor

# Create processor with custom settings
processor = StreamingTokenProcessor(
    max_target_tokens=15000,
    chunk_size_tokens=10000,
    overlap_tokens=2500
)

# Create engine with custom processor
engine = CompressionEngine(streaming_processor=processor)

# Process conversation
result = engine.process_and_adapt(db, project_id, messages, filename)

# Access dashboard data
dashboard_data = result['dashboard_data']
print(f"Compression Ratio: {dashboard_data['compression_ratio']}")
```

### UI Configuration

1. Click "⚙️ Settings" button
2. Navigate to "⚙️ Token Settings" tab
3. Adjust parameters:
   - Max Target Tokens
   - Chunk Size
   - Overlap
   - Preserve Recent Tokens
4. Click "Apply Settings"

### Dashboard Features

- **Real-time Updates**: Dashboard updates after each processing session
- **Historical Tracking**: Maintains statistics across multiple sessions
- **Export Capability**: Ready for CSV/JSON export (placeholder implemented)
- **Visual Indicators**: Color-coded compression ratios

---

## Performance Considerations

### Memory Efficiency

- **Streaming Processing**: Files processed in chunks rather than loading entirely into memory
- **Garbage Collection**: Periodic GC during large file processing
- **Peak Memory Tracking**: Monitored and reported in dashboard

### Processing Speed

- **Parallel Processing**: Each chunk processed independently
- **Optimized Overlap**: Balanced between context preservation and redundancy
- **Caching**: Reuses token encodings where possible

### Scalability

- **Large File Support**: Tested with files containing 100K+ tokens
- **Configurable Parameters**: Adjust based on available memory
- **Progressive Processing**: Real-time progress updates

---

## Testing Recommendations

1. **Small Files** (< 10K tokens): Verify single-pass processing
2. **Medium Files** (10K-50K tokens): Test chunking behavior
3. **Large Files** (> 50K tokens): Validate memory efficiency
4. **Settings Validation**: Test boundary conditions
5. **Dashboard Accuracy**: Verify statistics calculations

---

## Future Enhancements

1. **Machine Learning Optimization**: Learn optimal chunk sizes from processing history
2. **Batch Processing**: Process multiple files simultaneously
3. **Export Formats**: CSV/JSON export for dashboard data
4. **Advanced Visualization**: Charts and graphs for trends
5. **API Integration**: REST API for programmatic access

---

## Troubleshooting

### Common Issues

1. **High Memory Usage**
   - Reduce chunk_size_tokens
   - Increase overlap_tokens for better context retention

2. **Slow Processing**
   - Decrease chunk_size_tokens for parallel processing
   - Check LM Studio response times

3. **Context Fragmentation**
   - Increase overlap_tokens
   - Verify preserve_recent_tokens is adequate

### Debug Mode

Enable debug logging in `streaming_processor.py`:

```python
print(f"Chunk {chunk_index}: {len(chunk_tokens)} tokens")
print(f"Memory usage: {current / 1024 / 1024:.2f} MB")
```

---

## Conclusion

The enhanced token management system provides:

✅ **Memory-efficient processing** for large files  
✅ **Configurable settings** via intuitive UI  
✅ **Real-time dashboards** for monitoring compression  
✅ **Optimized sliding windows** to prevent fragmentation  

These improvements enable the LM Compressor to handle larger conversation files while maintaining context integrity and providing users with detailed insights into their token usage patterns.
