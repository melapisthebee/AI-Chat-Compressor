"""Mock LLM service for offline testing of compression pipeline."""
import json
from typing import Dict, Any


class MockLlmService:
    """Simulates LM Studio API responses for testing without network."""

    def __init__(self):
        self.request_count = 0
        self.responses = []
        self.default_response = {
            "choices": [{
                "message": {"content": "{}"},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        }

    def reset(self):
        self.request_count = 0
        self.responses = []

    def queue_response(self, content: str, prompt_tokens: int = 100, completion_tokens: int = 50):
        """Queue a specific response for the next request."""
        self.responses.append({
            "choices": [{
                "message": {"content": content},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                     "total_tokens": prompt_tokens + completion_tokens}
        })

    def get_response(self) -> Dict[str, Any]:
        """Get next response (queued or default)."""
        self.request_count += 1
        if self.responses:
            return self.responses.pop(0)
        return self.default_response

    def to_http_handler(self):
        """Return a callable that mimics requests.post for mocking."""
        mock_response = MockResponse()

        def handler(url, json_data=None, headers=None, timeout=None):
            llm_response = self.get_response()
            mock_response.json_data = llm_response
            return mock_response

        return handler


class MockResponse:
    """Mock HTTP response object."""
    status_code = 200

    def __init__(self):
        self.json_data = {}

    def json(self):
        return self.json_data

    @property
    def text(self):
        return json.dumps(self.json_data)
