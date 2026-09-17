import pytest, sys, json, tempfile, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from engine.streaming_processor import StreamingTokenProcessor, TokenBudgetManager
from engine.tokenizer import tracker
from engine.tfidf_matcher import match_category, TfidfMatcher
from engine.knowledge_conflicts import detect_conflicts, summarize_conflicts

class TestStreamingTokenProcessor:
    def test_initialization_default(self):
        p = StreamingTokenProcessor()
        assert p.max_target_tokens == 262144 and p.chunk_size_tokens == 8192
        assert p.overlap_tokens >= 500 and p.preserve_recent_tokens == 4096
    def test_initialization_custom(self):
        p = StreamingTokenProcessor(max_target_tokens=15000, chunk_size_tokens=10000, overlap_tokens=2500, preserve_recent_tokens=6000)
        assert p.max_target_tokens == 15000 and p.chunk_size_tokens == 10000
        assert p.overlap_tokens == 2500 and p.preserve_recent_tokens == 6000
    def test_estimate_file_tokens(self):
        p = StreamingTokenProcessor()
        est = p.estimate_file_tokens("This is a test sentence.")
        act = tracker.count_tokens("This is a test sentence.")
        assert abs(est - act) / max(act, 1) < 0.20
    def test_create_sliding_windows(self):
        p = StreamingTokenProcessor(chunk_size_tokens=100, overlap_tokens=25)
        wins = list(p.create_sliding_windows(list(range(250))))
        assert len(wins) >= 2
    def test_create_sliding_windows_overlap(self):
        p = StreamingTokenProcessor(chunk_size_tokens=100, overlap_tokens=50)
        wins = list(p.create_sliding_windows(list(range(300))))
        for i in range(1, len(wins)): assert wins[i-1][1] - wins[i][0] <= 50
    def test_calculate_compression_ratio(self):
        p = StreamingTokenProcessor()
        assert p.calculate_compression_ratio(10000, 3000) == 0.3
        assert p.calculate_compression_ratio(0, 0) == 0.0
    def test_update_stats(self):
        p = StreamingTokenProcessor(); p.reset_stats()
        p.update_stats(raw_tokens=10000, compressed_tokens=3000)
        assert p.stats['total_compressed_tokens'] == 3000
    def test_update_stats_with_raw(self):
        p = StreamingTokenProcessor(); p.reset_stats()
        p.stats['total_raw_tokens'] = 10000
        p.update_stats(raw_tokens=0, compressed_tokens=3000)
        assert p.stats['compression_ratio'] == 0.3
    def test_get_dashboard_data(self):
        p = StreamingTokenProcessor(); p.reset_stats()
        p.stats['total_raw_tokens'] = 10000; p.update_stats(raw_tokens=0, compressed_tokens=3000)
        d = p.get_dashboard_data()
        assert all(k in d for k in ('total_raw_tokens','compression_ratio','chunks_processed'))
    def test_reset_stats(self):
        p = StreamingTokenProcessor(); p.update_stats(raw_tokens=10000, compressed_tokens=3000)
        p.reset_stats()
        assert p.stats['total_raw_tokens'] == 0

class TestTokenBudgetManager:
    def test_initialization(self):
        s = TokenBudgetManager().get_current_settings()
        assert s['max_target_tokens'] == 262144 and s['chunk_size_tokens'] == 8192
        assert s['min_chunk_size'] == 512 and s['max_chunk_size'] == 8192
    def test_validate_valid_settings(self):
        ok, msg = TokenBudgetManager().validate_settings({'max_target_tokens': 15000, 'chunk_size_tokens': 8192, 'overlap_tokens': 2000, 'preserve_recent_tokens': 6000})
        assert ok and msg == ""
    def test_validate_invalid_max_tokens(self):
        ok, msg = TokenBudgetManager().validate_settings({'max_target_tokens': 500})
        assert not ok and "max_target_tokens" in msg.lower()
    def test_validate_invalid_chunk_size(self):
        assert not TokenBudgetManager().validate_settings({'chunk_size_tokens': 500})[0]
    def test_validate_invalid_overlap(self):
        assert not TokenBudgetManager().validate_settings({'overlap_tokens': 100})[0]
    def test_validate_overlap_too_high(self):
        assert not TokenBudgetManager().validate_settings({'chunk_size_tokens': 10000, 'overlap_tokens': 6000})[0]
    def test_apply_settings(self):
        a = TokenBudgetManager().apply_settings({'max_target_tokens': 20000, 'chunk_size_tokens': 8192, 'overlap_tokens': 2000})
        assert a['max_target_tokens'] == 20000
    def test_reset_to_defaults(self):
        m = TokenBudgetManager(); m.apply_settings({'max_target_tokens': 50000})
        assert m.reset_to_defaults()['max_target_tokens'] == 262144

class TestTfidfMatcher:
    def test_exact_match(self):
        ok, best, score = match_category('system_architecture', ['system_architecture', 'db_schema'])
        assert ok and best == 'system_architecture'
    def test_truncated_match(self):
        ok, best, score = match_category('sys_arch', ['system_architecture', 'database_schema'])
        assert ok and best == 'system_architecture'
    def test_no_match_unrelated(self):
        ok, _, _ = match_category('random_garbage_xyz', ['system_architecture', 'database_schema'])
        assert not ok
    def test_prefix_match(self):
        m = TfidfMatcher(['foo_bar'], sensitivity=0.1)
        assert m._prefix_match(['sys', 'arch'], ['system', 'architecture']) == 1.0

class TestKnowledgeConflicts:
    def test_no_conflicts(self): assert len(detect_conflicts({'a': 1}, {'a': 1}, 't')) == 0
    def test_detect_conflicts(self):
        c = detect_conflicts({'host': 'old'}, {'host': 'new'}, 'db')
        assert len(c) >= 1
    def test_severity_high_type_change(self):
        assert detect_conflicts({'val': 42}, {'val': 'str'}, 't')[0]['severity'] == 'high'
    def test_severity_low_same_type(self):
        assert detect_conflicts({'a': 1}, {'a': 2}, 't')[0]['severity'] == 'low'
    def test_summarize(self):
        s = summarize_conflicts(detect_conflicts({'a': 1}, {'a': 2}, 'x'), 'x')
        assert 'x' in s

class TestCredentialRedaction:
    def test_api_key(self):
        from engine.parser.json_parser import JSONParser
        out = JSONParser()._mask_credentials("api_key = 'sk-abc123def'")
        assert '[REDACTED_SECRET]' in out and 'abc123def' not in out
    def test_ip_redaction(self):
        from engine.parser.json_parser import JSONParser
        out = JSONParser()._mask_credentials("host 192.168.1.50 and 100.64.1.1")
        assert '[REDACTED_LOCAL_IP]' in out and '[REDACTED_TAILSCALE_IP]' in out

class TestKnowledgeMerge:
    def _e(self):
        from engine.compression import CompressionEngine
        e = CompressionEngine.__new__(CompressionEngine)
        e.logger = type('L', (), {'log': lambda s, x: None})()
        return e
    def test_deep_merge_basic(self):
        r = self._e()._deep_merge({'a': 1, 'nested': {'x': 10}}, {'b': 2, 'nested': {'y': 20}})
        assert r == {'a': 1, 'b': 2, 'nested': {'x': 10, 'y': 20}}
    def test_deep_merge_rejects_larger_delta(self):
        assert self._e()._deep_merge({'a': 1}, {'x': 1, 'y': 2, 'z': 3}) == {'a': 1}
    def test_deep_merge_empty_delta(self):
        assert self._e()._deep_merge({'a': 1}, {}) == {'a': 1}

class TestParserFormats:
    def test_parse_json_conversation(self):
        data = {"messages": [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]}
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(data, f); path = f.name
        try:
            from engine.parser import parse_lm_studio_file
            msgs = parse_lm_studio_file(path)
            assert len(msgs) == 2 and msgs[0]['role'] == 'user'
        finally: os.unlink(path)
    def test_parse_text_legacy(self):
        import importlib.util; spec = importlib.util.spec_from_file_location('legacy', 'A:/AI Stuff/lm-compressor/engine/parser.py'); legacy_mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(legacy_mod); legacy_parse = legacy_mod._parse_text_conversation
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("USER: hello\n\nASSISTANT: hi"); path = f.name
        try:
            assert len(legacy_parse(path)) == 2
        finally: os.unlink(path)

class TestMockLLM:
    def test_mock_response(self):
        class MC:
            def __init__(self): self.calls = []
            def chat(self, **kw):
                self.calls.append(kw)
                class C:
                    class M: message = type('M', (), {'content': '{"status":"ok"}'})()
                    choices = [M()]
                return C()
        mc = MC()
        r = mc.chat(messages=[{'role': 'user', 'content': 't'}])
        assert json.loads(r.choices[0].message.content)['status'] == 'ok'
        assert len(mc.calls) == 1

def run_tests():
    print("Running tests...")
    for t in [TestStreamingTokenProcessor, TestTokenBudgetManager, TestTfidfMatcher, TestKnowledgeConflicts, TestCredentialRedaction, TestKnowledgeMerge, TestMockLLM]:
        for name in [m for m in dir(t) if m.startswith('test_')]:
            getattr(t(), name)(); print(f"  OK {t.__name__}.{name}")
    print("All tests passed!")

if __name__ == "__main__":
    run_tests()
