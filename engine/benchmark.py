"""cProfile-based profiling entry point for tokenization/compression bottlenecks."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cProfile
import pstats
import sys
from pathlib import Path

def profile_tokenization():
    """Profile tokenizer.split_into_tokens on sample text."""
    from engine.tokenizer import tracker
    text = " ".join(["word"] * 50000)
    pr = cProfile.Profile()
    pr.enable()
    for _ in range(100):
        tracker.split_into_tokens(text)
    pr.disable()
    s = pstats.Stats(pr, stream=sys.stdout)
    s.sort_stats('cumulative')
    s.print_stats(20)

def profile_compression(engine, project_id, messages, filename):
    """Profile the full compression pipeline on a dataset."""
    import time
    from database.connection import get_thread_session
    pr = cProfile.Profile()
    pr.enable()
    t0 = time.time()
    with get_thread_session() as db:
        engine.process_and_adapt(db, project_id, messages, filename)
    elapsed = time.time() - t0
    pr.disable()
    s = pstats.Stats(pr, stream=sys.stdout)
    s.sort_stats('cumulative')
    s.print_stats(30)
    print(f"\nWall time: {elapsed:.2f}s")

if __name__ == "__main__":
    profile_tokenization()
