"""
Enhanced Streaming Token Processor for Memory-Efficient Large File Processing

This module implements:
- Streaming chunk processing for memory efficiency on large files
- Configurable token budget settings
- Token usage tracking and dashboard data collection
- Optimized sliding window overlap logic to prevent context fragmentation
"""

import gc
from typing import List, Dict, Any, Generator, Optional, Tuple
from config.settings import settings
from engine.tokenizer import tracker


class StreamingTokenProcessor:
    """
    Memory-efficient streaming processor for large conversation files.
    Implements configurable chunking, sliding window overlap, and token budget management.
    """
    
    def __init__(
        self,
        max_target_tokens: Optional[int] = None,
        chunk_size_tokens: Optional[int] = None,
        overlap_tokens: Optional[int] = None,
        preserve_recent_tokens: Optional[int] = None
    ):
        """
        Initialize the streaming processor with configurable parameters.
        
        Args:
            max_target_tokens: Maximum target token count (default: settings.MAX_TARGET_TOKENS)
            chunk_size_tokens: Size of each processing chunk (default: settings.CHUNK_SIZE_TOKENS)
            overlap_tokens: Overlap between consecutive chunks to prevent context fragmentation
            preserve_recent_tokens: Number of recent tokens to preserve unmodified
        """
        self.max_target_tokens = max_target_tokens or settings.MAX_TARGET_TOKENS
        self.chunk_size_tokens = chunk_size_tokens or settings.CHUNK_SIZE_TOKENS
        self.overlap_tokens = overlap_tokens or max(500, self.chunk_size_tokens // 4)  # Default 25% overlap
        self.preserve_recent_tokens = preserve_recent_tokens or settings.PRESERVE_RECENT_TOKENS
        
        # Statistics tracking for dashboard
        self.stats = {
            'total_raw_tokens': 0,
            'total_chunks_processed': 0,
            'total_compressed_tokens': 0,
            'compression_ratio': 0.0,
            'processing_time_seconds': 0.0,
            'memory_efficiency': 0.0  # Peak memory vs total tokens processed
        }
    
    def estimate_file_tokens(self, text: str) -> int:
        """
        Quickly estimate token count for a text without full encoding.
        Uses character-based approximation for large files.
        
        Args:
            text: The text to estimate
            
        Returns:
            Estimated token count
        """
        # Rough approximation: ~4 characters per token for English text
        return len(text) // 4
    
    def create_sliding_windows(
        self,
        tokens: List[int],
        chunk_size: Optional[int] = None,
        overlap: Optional[int] = None
    ) -> Generator[Tuple[int, int, List[int]], None, None]:
        """
        Create overlapping sliding windows from token list.
        Yields (start_index, end_index, token_chunk) tuples.
        
        Args:
            tokens: Full token list
            chunk_size: Override default chunk size
            overlap: Override default overlap size
            
        Yields:
            Tuple of (start_position, end_position, token_chunk)
        """
        chunk_size = chunk_size or self.chunk_size_tokens
        overlap = overlap or self.overlap_tokens
        
        total_tokens = len(tokens)
        start = 0
        
        while start < total_tokens:
            end = min(start + chunk_size, total_tokens)
            chunk_tokens = tokens[start:end]
            
            # Yield the chunk with metadata
            yield (start, end, chunk_tokens)
            
            # Move forward by chunk size minus overlap
            # But ensure we make progress even if overlap >= chunk_size
            step = max(chunk_size - overlap, chunk_size // 2)
            start += step
            
            # On the last chunk, preserve recent context
            if end >= total_tokens:
                break
    
    def stream_process_large_file(
        self,
        text: str,
        process_chunk_callback,
        preserve_tail: bool = True
    ) -> Dict[str, Any]:
        """
        Process large files in streaming chunks to manage memory efficiently.
        
        Args:
            text: Full text content to process
            process_chunk_callback: Function to call for each chunk (receives chunk_data, chunk_index)
            preserve_tail: Whether to preserve recent tokens unmodified
            
        Returns:
            Dictionary with processing statistics and results
        """
        import time
        import tracemalloc
        
        # Start memory tracking
        tracemalloc.start()
        start_time = time.time()
        
        # Quick token estimation for very large files
        estimated_tokens = self.estimate_file_tokens(text)
        
        if estimated_tokens < self.chunk_size_tokens * 2:
            # File is small enough to process in one pass
            return self._process_small_file(text, process_chunk_callback)
        
        # Full tokenization for precise processing
        all_tokens = tracker.split_into_tokens(text)
        self.stats['total_raw_tokens'] = len(all_tokens)
        
        results = []
        chunk_index = 0
        
        # Create sliding windows and process each chunk
        for start_idx, end_idx, chunk_tokens in self.create_sliding_windows(all_tokens):
            chunk_text = tracker.decode_tokens(chunk_tokens)
            
            # Prepare chunk data with context metadata
            chunk_data = {
                'chunk_index': chunk_index,
                'start_token': start_idx,
                'end_token': end_idx,
                'token_count': len(chunk_tokens),
                'text': chunk_text,
                'is_tail_chunk': (end_idx >= len(all_tokens) - self.preserve_recent_tokens)
            }
            
            # Process the chunk via callback
            chunk_result = process_chunk_callback(chunk_data, chunk_index)
            results.append(chunk_result)
            
            # Force garbage collection periodically for very large files
            if chunk_index % 10 == 0:
                gc.collect()
            
            chunk_index += 1
            
            # Update stats
            self.stats['total_chunks_processed'] = chunk_index
        
        # Calculate final statistics
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        self.stats['processing_time_seconds'] = end_time - start_time
        self.stats['peak_memory_bytes'] = peak
        self.stats['memory_efficiency'] = self.stats['total_raw_tokens'] / (peak / 1024 / 1024) if peak > 0 else 0
        
        return {
            'results': results,
            'statistics': self.stats.copy(),
            'total_chunks': chunk_index
        }
    
    def _process_small_file(
        self,
        text: str,
        process_chunk_callback
    ) -> Dict[str, Any]:
        """
        Optimized processing for files that fit in memory.
        
        Args:
            text: Full text content
            process_chunk_callback: Function to process the chunk
            
        Returns:
            Processing results and statistics
        """
        import time
        import tracemalloc
        
        tracemalloc.start()
        start_time = time.time()
        
        tokens = tracker.split_into_tokens(text)
        self.stats['total_raw_tokens'] = len(tokens)
        
        # Single chunk processing
        chunk_data = {
            'chunk_index': 0,
            'start_token': 0,
            'end_token': len(tokens),
            'token_count': len(tokens),
            'text': text,
            'is_tail_chunk': True
        }
        
        result = process_chunk_callback(chunk_data, 0)
        
        end_time = time.time()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        self.stats['processing_time_seconds'] = end_time - start_time
        self.stats['peak_memory_bytes'] = peak
        self.stats['total_chunks_processed'] = 1
        
        return {
            'results': [result],
            'statistics': self.stats.copy(),
            'total_chunks': 1
        }
    
    def calculate_compression_ratio(self, raw_tokens: int, compressed_tokens: int) -> float:
        """
        Calculate the compression ratio between raw and compressed tokens.
        
        Args:
            raw_tokens: Original token count
            compressed_tokens: Compressed token count
            
        Returns:
            Compression ratio (compressed/raw)
        """
        if raw_tokens == 0:
            return 0.0
        return compressed_tokens / raw_tokens
    
    def update_stats(
        self,
        raw_tokens: int,
        compressed_tokens: int,
        processing_time: Optional[float] = None
    ):
        """
        Update processing statistics with new metrics.
        
        Args:
            raw_tokens: Raw token count for this operation
            compressed_tokens: Compressed token count
            processing_time: Optional processing time in seconds
        """
        self.stats['total_compressed_tokens'] += compressed_tokens
        
        if self.stats['total_raw_tokens'] > 0:
            self.stats['compression_ratio'] = self.calculate_compression_ratio(
                self.stats['total_raw_tokens'],
                self.stats['total_compressed_tokens']
            )
        
        if processing_time:
            self.stats['processing_time_seconds'] += processing_time
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get formatted statistics for the token usage dashboard.
        
        Returns:
            Dictionary with formatted dashboard metrics
        """
        return {
            'total_raw_tokens': self.stats['total_raw_tokens'],
            'total_compressed_tokens': self.stats['total_compressed_tokens'],
            'compression_ratio': f"{self.stats['compression_ratio']:.2%}",
            'compression_ratio_decimal': self.stats['compression_ratio'],
            'chunks_processed': self.stats['total_chunks_processed'],
            'processing_time_seconds': f"{self.stats['processing_time_seconds']:.2f}",
            'peak_memory_mb': f"{self.stats.get('peak_memory_bytes', 0) / 1024 / 1024:.2f}",
            'memory_efficiency': f"{self.stats['memory_efficiency']:.0f} tokens/MB" if self.stats['memory_efficiency'] > 0 else "N/A",
            'chunk_size': self.chunk_size_tokens,
            'overlap_size': self.overlap_tokens,
            'max_target_tokens': self.max_target_tokens
        }
    
    def reset_stats(self):
        """Reset all processing statistics."""
        self.stats = {
            'total_raw_tokens': 0,
            'total_chunks_processed': 0,
            'total_compressed_tokens': 0,
            'compression_ratio': 0.0,
            'processing_time_seconds': 0.0,
            'memory_efficiency': 0.0
        }


class TokenBudgetManager:
    """
    Manages token budget settings and validation.
    Provides configuration interface for UI controls.
    """
    
    def __init__(self):
        self.budget_settings = {
            'max_target_tokens': settings.MAX_TARGET_TOKENS,
            'chunk_size_tokens': settings.CHUNK_SIZE_TOKENS,
            'overlap_tokens': max(500, settings.CHUNK_SIZE_TOKENS // 4),
            'preserve_recent_tokens': settings.PRESERVE_RECENT_TOKENS,
            'min_chunk_size': 1000,
            'max_chunk_size': 16000,
            'min_overlap': 200,
            'max_overlap_ratio': 0.5  # 50% maximum overlap
        }
    
    def validate_settings(self, settings_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate token budget settings before applying.
        
        Args:
            settings_dict: Dictionary of settings to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        errors = []
        
        # Validate max_target_tokens
        if 'max_target_tokens' in settings_dict:
            value = settings_dict['max_target_tokens']
            if not isinstance(value, int) or value < 1000:
                errors.append("max_target_tokens must be an integer >= 1000")
            elif value > 100000:
                errors.append("max_target_tokens should not exceed 100,000")
        
        # Validate chunk_size_tokens
        if 'chunk_size_tokens' in settings_dict:
            value = settings_dict['chunk_size_tokens']
            if not isinstance(value, int) or value < self.budget_settings['min_chunk_size']:
                errors.append(f"chunk_size_tokens must be >= {self.budget_settings['min_chunk_size']}")
            elif value > self.budget_settings['max_chunk_size']:
                errors.append(f"chunk_size_tokens should not exceed {self.budget_settings['max_chunk_size']}")
        
        # Validate overlap_tokens
        if 'overlap_tokens' in settings_dict:
            value = settings_dict['overlap_tokens']
            if not isinstance(value, int) or value < self.budget_settings['min_overlap']:
                errors.append(f"overlap_tokens must be >= {self.budget_settings['min_overlap']}")
            
            # Check overlap ratio
            chunk_size = settings_dict.get('chunk_size_tokens', self.budget_settings['chunk_size_tokens'])
            if value > chunk_size * self.budget_settings['max_overlap_ratio']:
                errors.append(f"overlap_tokens should not exceed {self.budget_settings['max_overlap_ratio']*100:.0f}% of chunk_size")
        
        # Validate preserve_recent_tokens
        if 'preserve_recent_tokens' in settings_dict:
            value = settings_dict['preserve_recent_tokens']
            if not isinstance(value, int) or value < 500:
                errors.append("preserve_recent_tokens must be >= 500")
        
        is_valid = len(errors) == 0
        error_message = "; ".join(errors) if errors else ""
        
        return is_valid, error_message
    
    def apply_settings(self, settings_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply validated settings and return the updated configuration.
        
        Args:
            settings_dict: Dictionary of settings to apply
            
        Returns:
            Dictionary with applied settings
        """
        is_valid, error_msg = self.validate_settings(settings_dict)
        
        if not is_valid:
            raise ValueError(f"Invalid settings: {error_msg}")
        
        # Update budget settings
        for key, value in settings_dict.items():
            if key in self.budget_settings:
                self.budget_settings[key] = value
        
        # Ensure consistency
        if 'chunk_size_tokens' in settings_dict or 'overlap_tokens' in settings_dict:
            chunk_size = self.budget_settings['chunk_size_tokens']
            if self.budget_settings['overlap_tokens'] > chunk_size * self.budget_settings['max_overlap_ratio']:
                self.budget_settings['overlap_tokens'] = int(chunk_size * self.budget_settings['max_overlap_ratio'])
        
        return self.budget_settings.copy()
    
    def get_current_settings(self) -> Dict[str, Any]:
        """Get current budget settings."""
        return self.budget_settings.copy()
    
    def reset_to_defaults(self) -> Dict[str, Any]:
        """Reset settings to defaults."""
        self.budget_settings = {
            'max_target_tokens': settings.MAX_TARGET_TOKENS,
            'chunk_size_tokens': settings.CHUNK_SIZE_TOKENS,
            'overlap_tokens': max(500, settings.CHUNK_SIZE_TOKENS // 4),
            'preserve_recent_tokens': settings.PRESERVE_RECENT_TOKENS,
            'min_chunk_size': 1000,
            'max_chunk_size': 16000,
            'min_overlap': 200,
            'max_overlap_ratio': 0.5
        }
        return self.budget_settings.copy()


# Global instances
streaming_processor = StreamingTokenProcessor()
token_budget_manager = TokenBudgetManager()
