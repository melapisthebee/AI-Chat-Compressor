"""Integration tests for full compression pipeline with mock LLM."""
import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.compression import CompressionEngine


@pytest.mark.integration
class TestCompressionPipeline:
    """Test full compression pipeline with mocked OpenAI client."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    @pytest.fixture
    def sample_messages(self):
        return [
            {"role": "user", "content": "What is the weather in New York?"},
            {"role": "assistant", "content": "The weather in New York is currently sunny with a high of 75F."},
            {"role": "user", "content": "Will it rain tomorrow?"},
            {"role": "assistant", "content": "There is a 30 percent chance of rain tomorrow afternoon."}
        ]

    def _make_mock_client(self, responses):
        """Create mock OpenAI client with queued responses."""
        client = MagicMock()
        chat_mock = MagicMock()
        completions_mock = MagicMock()

        response_objects = []
        for content in responses:
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = content
            resp.choices[0].finish_reason = "stop"
            response_objects.append(resp)

        completions_mock.create.side_effect = response_objects
        chat_mock.completions = completions_mock
        client.chat = chat_mock
        client.models.list.return_value = MagicMock(data=[MagicMock(id="test-model")])
        return client, completions_mock

    def test_pipeline_with_mock_llm(self, mock_db, sample_messages):
        """Test full pipeline: parse -> extract -> compress -> audit."""
        extraction_response = json.dumps({
            "categories": [{"name": "weather", "summary": "NYC weather forecast discussion"}]
        })
        compression_response = json.dumps({
            "compressed_summary": "User asked about NYC weather. Assistant provided current conditions."
        })

        client, completions_mock = self._make_mock_client([extraction_response, compression_response])

        with patch("engine.compression.OpenAI", return_value=client):
            engine = CompressionEngine()
            engine.check_lm_studio_health = MagicMock(return_value=True)
            result = engine.process_and_adapt(mock_db, "test-project", sample_messages, "test.txt")
            assert completions_mock.create.call_count >= 2

    def test_empty_conversation(self, mock_db):
        """Test pipeline with empty message list."""
        client = MagicMock()
        client.models.list.return_value = MagicMock(data=[MagicMock(id="test-model")])

        with patch("engine.compression.OpenAI", return_value=client):
            engine = CompressionEngine()
            engine.check_lm_studio_health = MagicMock(return_value=True)
            result = engine.process_and_adapt(mock_db, "test-project", [], "empty.txt")
            assert result is not None

    def test_large_conversation_chunking(self, mock_db):
        """Test that large conversations are properly chunked."""
        messages = []
        for i in range(100):
            messages.append({"role": "user", "content": f"Question {i}: " + "x" * 500})
            messages.append({"role": "assistant", "content": f"Answer {i}: " + "y" * 500})

        # Queue many empty responses for multiple chunks
        responses = [json.dumps({})] * 20
        client, completions_mock = self._make_mock_client(responses)

        with patch("engine.compression.OpenAI", return_value=client):
            engine = CompressionEngine()
            engine.check_lm_studio_health = MagicMock(return_value=True)
            # Override chunk size via streaming processor
            engine.streaming_processor.chunk_size_tokens = 1000
            result = engine.process_and_adapt(mock_db, "test-project", messages, "large.txt")
            assert completions_mock.create.call_count > 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
