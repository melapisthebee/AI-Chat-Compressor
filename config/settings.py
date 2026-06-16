import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve absolute paths relative to the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    """
    Application settings managing paths, database connections, 
    and LM Studio API thresholds.
    """
    # --- Project Paths ---
    PROJECT_NAME: str = "LM_Studio_Compressor"
    DATABASE_PATH: Path = PROJECT_ROOT / "storage" / "archive.db"
    
    # --- LM Studio API Setup ---
    # Default local address for LM Studio
    LM_STUDIO_BASE_URL: str = "http://localhost:1234/v1"
    LM_STUDIO_API_KEY: str = "lm-studio"  # Placeholder token required by the client
    DEFAULT_COMPRESSION_MODEL: str = "meta-llama-3-8b-instruct"
    
    # --- Token Budgeting Engine Constraints ---
    TOKEN_ENCODING: str = "cl100k_base"       # Tokenizer matching Llama-3/GPT standard
    MAX_TARGET_TOKENS: int = 10000            # Hard ceiling for the compressed profile
    PRESERVE_RECENT_TOKENS: int = 5000        # Unmodified trailing context window budget
    CHUNK_SIZE_TOKENS: int = 8000             # Segment size for sliding-window compression
    
    # --- GUI Configurations ---
    WINDOW_WIDTH: int = 1000
    WINDOW_HEIGHT: int = 700
    
    # --- API Configuration ---
    REQUEST_TIMEOUT: int = 120  # Timeout in seconds for LLM API calls (increased for large conversations)
    MAX_RETRIES: int = 3  # Maximum retry attempts for transient failures
    RETRY_BASE_DELAY: int = 1  # Base delay in seconds between retries
    
    # Allow overriding configurations cleanly via a local .env file at project root
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def ensure_storage_exists(self):
        """Utility to guarantee the SQLite storage folder exists before DB connection."""
        self.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

# Instantiate a global settings object for export
settings = Settings()
settings.ensure_storage_exists()