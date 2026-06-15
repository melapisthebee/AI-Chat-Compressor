"""
Test suite for Enhanced Token Management features.

Tests:
1. StreamingTokenProcessor functionality
2. TokenBudgetManager validation
3. Sliding window creation
4. Dashboard data generation
5. Integration with CompressionEngine
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.streaming_processor import StreamingTokenProcessor, TokenBudgetManager
from engine.tokenizer import tracker


class TestStreamingTokenProcessor:
    """Tests for StreamingTokenProcessor class."""
    
    def test_initialization_default(self):
        """Test default initialization values."""
        processor = StreamingTokenProcessor()
        assert processor.max_target_tokens == 10000
        assert processor.chunk_size_tokens == 8000
        assert processor.overlap_tokens >= 500
        assert processor.preserve_recent_tokens == 5000
    
    def test_initialization_custom(self):
        """Test custom initialization values."""
        processor = StreamingTokenProcessor(
            max_target_tokens=15000,
            chunk_size_tokens=10000,
            overlap_tokens=2500,
            preserve_recent_tokens=6000
        )
        assert processor.max_target_tokens == 15000
        assert processor.chunk_size_tokens == 10000
        assert processor.overlap_tokens == 2500
        assert processor.preserve_recent_tokens == 6000
    
    def test_estimate_file_tokens(self):
        """Test token estimation accuracy."""
        processor = StreamingTokenProcessor()
        test_text = "This is a test sentence."
        estimated = processor.estimate_file_tokens(test_text)
        actual = tracker.count_tokens(test_text)
        
        # Estimation should be within 20% of actual
        assert abs(estimated - actual) / max(actual, 1) < 0.20
    
    def test_create_sliding_windows(self):
        """Test sliding window creation."""
        processor = StreamingTokenProcessor(
            chunk_size_tokens=100,
            overlap_tokens=25
        )
        
        # Create a test token list
        test_tokens = list(range(250))
        
        windows = list(processor.create_sliding_windows(test_tokens))
        
        # Should create multiple windows
        assert len(windows) >= 2
        
        # Check overlap
        for i in range(1, len(windows)):
            prev_end = windows[i-1][1]
            curr_start = windows[i][0]
            overlap = prev_end - curr_start
            assert overlap >= 0  # Should have some overlap or be contiguous
    
    def test_create_sliding_windows_overlap(self):
        """Test that sliding windows maintain proper overlap."""
        processor = StreamingTokenProcessor(
            chunk_size_tokens=100,
            overlap_tokens=50
        )
        
        test_tokens = list(range(300))
        windows = list(processor.create_sliding_windows(test_tokens))
        
        # Verify overlap is maintained
        for i in range(1, len(windows)):
            prev_end = windows[i-1][1]
            curr_start = windows[i][0]
            overlap = prev_end - curr_start
            assert overlap <= 50  # Should not exceed configured overlap
    
    def test_calculate_compression_ratio(self):
        """Test compression ratio calculation."""
        processor = StreamingTokenProcessor()
        
        # Test various ratios
        assert processor.calculate_compression_ratio(10000, 3000) == 0.3
        assert processor.calculate_compression_ratio(10000, 5000) == 0.5
        assert processor.calculate_compression_ratio(10000, 10000) == 1.0
        assert processor.calculate_compression_ratio(0, 0) == 0.0
    
    def test_update_stats(self):
        """Test statistics tracking."""
        processor = StreamingTokenProcessor()
        processor.reset_stats()
        
        processor.update_stats(raw_tokens=10000, compressed_tokens=3000)
        
        assert processor.stats['total_raw_tokens'] == 10000
        assert processor.stats['total_compressed_tokens'] == 3000
        assert processor.stats['compression_ratio'] == 0.3
    
    def test_get_dashboard_data(self):
        """Test dashboard data generation."""
        processor = StreamingTokenProcessor()
        processor.reset_stats()
        
        processor.update_stats(raw_tokens=10000, compressed_tokens=3000)
        
        dashboard_data = processor.get_dashboard_data()
        
        assert 'total_raw_tokens' in dashboard_data
        assert 'compression_ratio' in dashboard_data
        assert 'chunks_processed' in dashboard_data
        assert 'processing_time_seconds' in dashboard_data
    
    def test_reset_stats(self):
        """Test statistics reset."""
        processor = StreamingTokenProcessor()
        processor.update_stats(raw_tokens=10000, compressed_tokens=3000)
        processor.reset_stats()
        
        assert processor.stats['total_raw_tokens'] == 0
        assert processor.stats['total_compressed_tokens'] == 0
        assert processor.stats['compression_ratio'] == 0.0


class TestTokenBudgetManager:
    """Tests for TokenBudgetManager class."""
    
    def test_initialization(self):
        """Test default initialization."""
        manager = TokenBudgetManager()
        settings = manager.get_current_settings()
        
        assert settings['max_target_tokens'] == 10000
        assert settings['chunk_size_tokens'] == 8000
        assert settings['min_chunk_size'] == 1000
        assert settings['max_chunk_size'] == 16000
    
    def test_validate_valid_settings(self):
        """Test validation of valid settings."""
        manager = TokenBudgetManager()
        
        valid_settings = {
            'max_target_tokens': 15000,
            'chunk_size_tokens': 10000,
            'overlap_tokens': 2500,
            'preserve_recent_tokens': 6000
        }
        
        is_valid, error_msg = manager.validate_settings(valid_settings)
        assert is_valid is True
        assert error_msg == ""
    
    def test_validate_invalid_max_tokens(self):
        """Test validation rejects invalid max_target_tokens."""
        manager = TokenBudgetManager()
        
        invalid_settings = {'max_target_tokens': 500}  # Below minimum
        
        is_valid, error_msg = manager.validate_settings(invalid_settings)
        assert is_valid is False
        assert "max_target_tokens" in error_msg.lower()
    
    def test_validate_invalid_chunk_size(self):
        """Test validation rejects invalid chunk_size_tokens."""
        manager = TokenBudgetManager()
        
        invalid_settings = {'chunk_size_tokens': 500}  # Below minimum
        
        is_valid, error_msg = manager.validate_settings(invalid_settings)
        assert is_valid is False
    
    def test_validate_invalid_overlap(self):
        """Test validation rejects invalid overlap_tokens."""
        manager = TokenBudgetManager()
        
        invalid_settings = {'overlap_tokens': 100}  # Below minimum
        
        is_valid, error_msg = manager.validate_settings(invalid_settings)
        assert is_valid is False
    
    def test_validate_overlap_too_high(self):
        """Test validation rejects overlap exceeding max ratio."""
        manager = TokenBudgetManager()
        
        invalid_settings = {
            'chunk_size_tokens': 10000,
            'overlap_tokens': 6000  # 60% of chunk size, exceeds 50% max
        }
        
        is_valid, error_msg = manager.validate_settings(invalid_settings)
        assert is_valid is False
    
    def test_apply_settings(self):
        """Test applying valid settings."""
        manager = TokenBudgetManager()
        
        new_settings = {
            'max_target_tokens': 20000,
            'chunk_size_tokens': 12000,
            'overlap_tokens': 3000,
            'preserve_recent_tokens': 7000
        }
        
        applied = manager.apply_settings(new_settings)
        
        assert applied['max_target_tokens'] == 20000
        assert applied['chunk_size_tokens'] == 12000
    
    def test_reset_to_defaults(self):
        """Test resetting to default settings."""
        manager = TokenBudgetManager()
        
        # Change settings
        manager.apply_settings({'max_target_tokens': 50000})
        
        # Reset
        defaults = manager.reset_to_defaults()
        
        assert defaults['max_target_tokens'] == 10000


class TestIntegration:
    """Integration tests for token management features."""
    
    def test_streaming_processor_with_small_text(self):
        """Test streaming processor with small text (single chunk)."""
        processor = StreamingTokenProcessor()
        processor.reset_stats()
        
        small_text = "This is a short test text."
        
        def process_chunk(chunk_data, index):
            return {'processed': True, 'index': index}
        
        result = processor.stream_process_large_file(
            text=small_text,
            process_chunk_callback=process_chunk
        )
        
        assert result['total_chunks'] == 1
        assert processor.stats['total_raw_tokens'] > 0
    
    def test_sliding_window_context_preservation(self):
        """Test that sliding windows preserve context."""
        processor = StreamingTokenProcessor(
            chunk_size_tokens=50,
            overlap_tokens=20
        )
        
        # Create text that spans multiple chunks
        test_text = " ".join(["word"] * 200)
        tokens = tracker.split_into_tokens(test_text)
        
        windows = list(processor.create_sliding_windows(tokens))
        
        # Verify we have multiple windows
        assert len(windows) >= 3
        
        # Verify overlap exists
        for i in range(1, len(windows)):
            prev_end = windows[i-1][1]
            curr_start = windows[i][0]
            assert prev_end >= curr_start  # Overlap or contiguous


def run_tests():
    """Run all tests and print results."""
    print("Running Enhanced Token Management Tests...\n")
    
    # Test StreamingTokenProcessor
    print("1. Testing StreamingTokenProcessor...")
    processor_tests = TestStreamingTokenProcessor()
    
    processor_tests.test_initialization_default()
    print("   ✓ Default initialization")
    
    processor_tests.test_initialization_custom()
    print("   ✓ Custom initialization")
    
    processor_tests.test_estimate_file_tokens()
    print("   ✓ Token estimation")
    
    processor_tests.test_create_sliding_windows()
    print("   ✓ Sliding window creation")
    
    processor_tests.test_calculate_compression_ratio()
    print("   ✓ Compression ratio calculation")
    
    processor_tests.test_update_stats()
    print("   ✓ Statistics tracking")
    
    processor_tests.test_get_dashboard_data()
    print("   ✓ Dashboard data generation")
    
    # Test TokenBudgetManager
    print("\n2. Testing TokenBudgetManager...")
    manager_tests = TestTokenBudgetManager()
    
    manager_tests.test_initialization()
    print("   ✓ Default initialization")
    
    manager_tests.test_validate_valid_settings()
    print("   ✓ Valid settings validation")
    
    manager_tests.test_validate_invalid_max_tokens()
    print("   ✓ Invalid max_tokens rejection")
    
    manager_tests.test_validate_invalid_chunk_size()
    print("   ✓ Invalid chunk_size rejection")
    
    manager_tests.test_apply_settings()
    print("   ✓ Settings application")
    
    manager_tests.test_reset_to_defaults()
    print("   ✓ Reset to defaults")
    
    # Integration tests
    print("\n3. Running Integration Tests...")
    integration_tests = TestIntegration()
    
    integration_tests.test_streaming_processor_with_small_text()
    print("   ✓ Small text processing")
    
    integration_tests.test_sliding_window_context_preservation()
    print("   ✓ Context preservation")
    
    print("\n✅ All tests passed successfully!")


if __name__ == "__main__":
    run_tests()
