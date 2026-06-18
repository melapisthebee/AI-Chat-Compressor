"""
Parser Performance Benchmark Module

This module provides benchmarking utilities to measure parser performance
across different file formats and sizes.

Usage:
    from engine.parser.benchmark import run_parser_benchmarks
    results = run_parser_benchmarks()
"""

import os
import time
import json
import statistics
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime

from engine.tokenizer import tracker

# Import parse_lm_studio_file lazily within functions to avoid circular imports


class ParserBenchmark:
    """Benchmark runner for parser performance testing."""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        
    def benchmark_single_file(self, filepath: str) -> Dict[str, Any]:
        """
        Benchmark parsing performance for a single file.
        
        Args:
            filepath: Path to the file to benchmark
            
        Returns:
            Dictionary containing benchmark results
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        
        file_size = os.path.getsize(filepath)
        file_ext = os.path.splitext(filepath)[1].lower()
        
        # Warm-up run (not counted)
        try:
            # Import locally to avoid circular import
            from . import parse_lm_studio_file
            parse_lm_studio_file(filepath)
        except Exception:
            pass  # Ignore errors during warm-up
        
        # Actual benchmark runs
        runtimes = []
        token_counts = []
        message_counts = []
        
        for i in range(3):  # Run 3 times and average
            start_time = time.perf_counter()
            try:
                # Import locally to avoid circular import
                from . import parse_lm_studio_file
                messages = parse_lm_studio_file(filepath)
                end_time = time.perf_counter()
                
                runtime = end_time - start_time
                runtimes.append(runtime)
                
                # Calculate token count
                text_content = " ".join([m.get("content", "") for m in messages])
                token_count = tracker.count_tokens(text_content)
                token_counts.append(token_count)
                
                message_counts.append(len(messages))
                
            except Exception as e:
                end_time = time.perf_counter()
                runtime = end_time - start_time
                runtimes.append(runtime)
                token_counts.append(0)
                message_counts.append(0)
                print(f"⚠️ Error during benchmark run {i+1}: {str(e)}")
        
        result = {
            "filepath": filepath,
            "filename": os.path.basename(filepath),
            "extension": file_ext,
            "file_size_bytes": file_size,
            "file_size_mb": file_size / (1024 * 1024),
            "avg_runtime_seconds": statistics.mean(runtimes),
            "min_runtime_seconds": min(runtimes),
            "max_runtime_seconds": max(runtimes),
            "std_runtime_seconds": statistics.stdev(runtimes) if len(runtimes) > 1 else 0,
            "avg_tokens": statistics.mean(token_counts) if token_counts else 0,
            "avg_messages": statistics.mean(message_counts) if message_counts else 0,
            "tokens_per_second": statistics.mean(token_counts) / statistics.mean(runtimes) if statistics.mean(runtimes) > 0 else 0,
            "messages_per_second": statistics.mean(message_counts) / statistics.mean(runtimes) if statistics.mean(runtimes) > 0 else 0,
            "timestamp": datetime.now().isoformat(),
            "success": all(token_counts)  # True if all runs succeeded
        }
        
        self.results.append(result)
        return result
    
    def benchmark_directory(self, directory: str, file_pattern: str = "*") -> List[Dict[str, Any]]:
        """
        Benchmark all matching files in a directory.
        
        Args:
            directory: Path to directory containing files
            file_pattern: Glob pattern to match files (default: all files)
            
        Returns:
            List of benchmark results for each file
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        files = list(dir_path.glob(file_pattern))
        print(f"Found {len(files)} files to benchmark in {directory}")
        
        results = []
        for i, filepath in enumerate(files):
            print(f"\n[{i+1}/{len(files)}] Benchmarking: {filepath.name}")
            try:
                result = self.benchmark_single_file(str(filepath))
                results.append(result)
                print(f"  ✓ Runtime: {result['avg_runtime_seconds']:.3f}s, "
                      f"Tokens: {result['avg_tokens']}, "
                      f"Messages: {result['avg_messages']}")
            except Exception as e:
                print(f"  ✗ Error: {str(e)}")
        
        return results
    
    def generate_report(self) -> str:
        """
        Generate a formatted benchmark report.
        
        Returns:
            Formatted string report of all benchmark results
        """
        if not self.results:
            return "No benchmark results available."
        
        report = []
        report.append("=" * 80)
        report.append("PARSER PERFORMANCE BENCHMARK REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 80)
        report.append("")
        
        # Summary statistics
        successful_runs = [r for r in self.results if r['success']]
        failed_runs = [r for r in self.results if not r['success']]
        
        report.append("SUMMARY")
        report.append("-" * 40)
        report.append(f"Total files benchmarked: {len(self.results)}")
        report.append(f"Successful runs: {len(successful_runs)}")
        report.append(f"Failed runs: {len(failed_runs)}")
        
        if successful_runs:
            avg_runtime = statistics.mean([r['avg_runtime_seconds'] for r in successful_runs])
            avg_tokens = statistics.mean([r['avg_tokens'] for r in successful_runs])
            avg_messages = statistics.mean([r['avg_messages'] for r in successful_runs])
            avg_tps = statistics.mean([r['tokens_per_second'] for r in successful_runs])
            avg_mps = statistics.mean([r['messages_per_second'] for r in successful_runs])
            
            report.append(f"Average runtime: {avg_runtime:.3f} seconds")
            report.append(f"Average tokens processed: {avg_tokens:,.0f}")
            report.append(f"Average messages parsed: {avg_messages:,.0f}")
            report.append(f"Average throughput: {avg_tps:,.0f} tokens/second")
            report.append(f"Average throughput: {avg_mps:,.0f} messages/second")
        
        report.append("")
        report.append("DETAILED RESULTS")
        report.append("-" * 40)
        
        for result in self.results:
            status = "✓" if result['success'] else "✗"
            report.append(f"\n{status} {result['filename']}")
            report.append(f"   Extension: {result['extension']}")
            report.append(f"   File size: {result['file_size_mb']:.2f} MB")
            report.append(f"   Runtime: {result['avg_runtime_seconds']:.3f}s "
                         f"(min: {result['min_runtime_seconds']:.3f}s, "
                         f"max: {result['max_runtime_seconds']:.3f}s)")
            if result['success']:
                report.append(f"   Tokens: {result['avg_tokens']:,}")
                report.append(f"   Messages: {result['avg_messages']:,}")
                report.append(f"   Throughput: {result['tokens_per_second']:,.0f} tokens/s")
            else:
                report.append(f"   Status: FAILED")
        
        report.append("")
        report.append("=" * 80)
        
        return "\n".join(report)
    
    def save_report(self, output_path: str = "benchmark_report.json"):
        """
        Save benchmark results to a JSON file.
        
        Args:
            output_path: Path to save the report
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2)
        print(f"Benchmark results saved to: {output_path}")


def run_parser_benchmarks(sample_dir: str = None) -> ParserBenchmark:
    """
    Convenience function to run parser benchmarks.
    
    Args:
        sample_dir: Directory containing sample files to benchmark.
                   If None, looks for 'samples' directory in project root.
                   
    Returns:
        ParserBenchmark instance with results
    """
    benchmark = ParserBenchmark()
    
    if sample_dir is None:
        # Default to samples directory in project root
        project_root = Path(__file__).parent.parent.parent
        sample_dir = project_root / "samples"
    
    if not os.path.exists(sample_dir):
        print(f"Sample directory not found: {sample_dir}")
        print("Creating sample directory and test files...")
        os.makedirs(sample_dir, exist_ok=True)
        _create_sample_files(sample_dir)
    
    print(f"\n🚀 Starting parser benchmarks in: {sample_dir}\n")
    results = benchmark.benchmark_directory(str(sample_dir))
    
    if results:
        print("\n" + benchmark.generate_report())
        benchmark.save_report()
    
    return benchmark


def _create_sample_files(directory: str):
    """Create sample files for benchmarking."""
    # Create sample JSON file
    sample_messages = {
        "messages": [
            {"role": "user", "content": f"Hello, this is a test message {i}"}
            for i in range(100)
        ]
    }
    
    sample_path = Path(directory) / "sample_conversation.json"
    with open(sample_path, 'w', encoding='utf-8') as f:
        json.dump(sample_messages, f, indent=2)
    
    print(f"Created sample file: {sample_path}")


if __name__ == "__main__":
    # Run benchmarks when executed directly
    benchmark = run_parser_benchmarks()
