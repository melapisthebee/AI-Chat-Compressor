import tiktoken
from config.settings import settings

class TokenTracker:
    def __init__(self):
        encoding_name = settings.TOKEN_ENCODING or "cl100k_base"
        try:
            self.encoder = tiktoken.get_encoding(encoding_name)
        except Exception:
            # Safe layout fallback if configuration breaks
            self.encoder = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Returns the absolute token count for a given string."""
        if not text:
            return 0
        return len(self.encoder.encode(text))

    def decode_tokens(self, tokens: list[int]) -> str:
        """Converts an array of token IDs back into readable text safely."""
        try:
            return self.encoder.decode(tokens)
        except Exception:
            # This is where the error parameter is actually valid and needed!
            # If a token sequence cuts off directly in the middle of a multi-byte character,
            # this prevents a UnicodeDecodeError crash.
            return self.encoder.decode(tokens, errors="replace")

    def split_into_tokens(self, text: str) -> list[int]:
        """Encodes text into raw token integer weights."""
        return self.encoder.encode(text)

# Single instance instantiation for application reuse
tracker = TokenTracker()