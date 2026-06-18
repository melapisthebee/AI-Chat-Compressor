"""
Logging utilities for lm-compressor.
Creates per-runtime log files in the logs/ directory.
Captures console output, AI generation output, and structured run data.
"""

import datetime
import json
import os
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"

class RunLogger:
    """Per-runtime logger that writes to a timestamped file in logs/."""

    def __init__(self, run_id: Optional[str] = None):
        self.run_id = run_id or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        self.main_log_path = LOG_DIR / f"run_{self.run_id}.log"
        self.ai_output_path = LOG_DIR / f"run_{self.run_id}_ai_output.log"

        # Initialize files with header
        with open(self.main_log_path, "w", encoding="utf-8") as f:
            f.write(f"=== LM Compressor Run {self.run_id} ===\n")
            f.write(f"Started: {datetime.datetime.now().isoformat()}\n\n")

        with open(self.ai_output_path, "w", encoding="utf-8") as f:
            f.write(f"=== AI Output Log - Run {self.run_id} ===\n")
            f.write(f"Started: {datetime.datetime.now().isoformat()}\n\n")

    def log(self, msg: str):
        """Write to main log and print to console."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line)
        with open(self.main_log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def log_ai_output(self, label: str, content: str):
        """Write AI generation output to the dedicated AI log file."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] === {label} ==="
        with open(self.ai_output_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.write(content + "\n")
            f.write(f"[{ts}] END {label}\n\n")

    def log_ai_json(self, label: str, data: dict):
        """Write AI generation output (structured) to the dedicated AI log file."""
        self.log_ai_output(label, json.dumps(data, indent=2))

    def close(self):
        """Append completion timestamp."""
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        with open(self.main_log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[ {ts} ] Run completed.\n")
