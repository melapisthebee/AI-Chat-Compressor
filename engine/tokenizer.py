import logging
import tiktoken
from config import settings

logger = logging.getLogger(__name__)

class TokenTracker:
    def __init__(self):
        encoding_name = settings.TOKEN_ENCODING or "cl100k_base"
        try:
            self.encoder = tiktoken.get_encoding(encoding_name)
        except KeyError:
            logger.warning(
                f"Token encoding '{encoding_name}' not found. Falling back to 'cl100k_base'."
            )
            self.encoder = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """Returns the absolute token count for a given string."""
        return len(self.split_into_tokens(text)) if text else 0

    def split_into_tokens(self, text: str) -> list[int]:
        """Encodes text into raw token integer IDs."""
        return self.encoder.encode(text)

    def decode_tokens(self, tokens: list[int]) -> str:
        """Converts token IDs back to text, safely replacing invalid byte sequences."""
        try:
            return self.encoder.decode(tokens)
        except UnicodeDecodeError:
            # Handles cases where token list ends mid‑byte sequence
            return self.encoder.decode(tokens, errors="replace")

tracker = TokenTracker()