"""
JSON Parser Module - LM Studio raw JSON conversation logs with schema-guided recovery.
"""

import os
import json
import re
from typing import List, Dict, Union

try:
    from json_repair import repair_json
    JSON_REPAIR_AVAILABLE = True
except ImportError:
    JSON_REPAIR_AVAILABLE = False

from .base_parser import BaseParser
from engine.tokenizer import tracker


class JSONParser(BaseParser):
    """Parser for LM Studio raw JSON conversation logs."""

    def __init__(self):
        super().__init__()
        self.supported_extensions = ['.json']
        self.max_token_count = 200_000
        self.max_file_size_mb = 50

    def parse(self, filepath: str) -> List[Dict[str, str]]:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"JSON conversation log not found: {filepath}")

        file_size = os.path.getsize(filepath)
        if file_size > self.max_file_size_mb * 1024 * 1024:
            raise ValueError(
                f"File too large: {file_size / (1024*1024):.1f}MB exceeds {self.max_file_size_mb}MB"
            )

        data = self._load_json_with_recovery(filepath)

        if isinstance(data, dict):
            messages = data.get("messages", [])
            if not messages and len(data) > 0:
                messages = [data]
        elif isinstance(data, list):
            messages = data
        else:
            raise ValueError(f"JSON root must be object or array, got {type(data).__name__}")

        self._validate_token_count({"messages": messages}, filepath)

        normalized_messages = []
        parse_errors = []

        for idx, m in enumerate(messages):
            if not isinstance(m, dict):
                parse_errors.append(f"Message {idx}: Expected object, got {type(m).__name__}")
                continue

            try:
                role = str(m.get("role", "user")).lower()
                if role not in ("user", "assistant", "system"):
                    role = "user"

                content = str(m.get("content", "") or m.get("text", ""))
                if not content.strip():
                    continue

                content = self._strip_thought_blocks_safely(content)
                content = self._clean_and_truncate_content(content, skip_truncation=False)

                if content.strip():
                    normalized_messages.append({"role": role, "content": content.strip()})
            except Exception as e:
                parse_errors.append(f"Message {idx}: {str(e)}")

        if parse_errors:
            print(f"⚠️ JSON Parse Warnings ({os.path.basename(filepath)}): {len(parse_errors)} skipped")
            for w in parse_errors[:5]:
                print(f"   - {w}")

        return normalized_messages

    # ---- LM Studio raw-JSON event extraction ----

    def extract_lm_studio_events(self, filepath_or_data) -> List[Dict]:
        """Parse raw LM Studio JSON → list of typed event dicts."""
        if isinstance(filepath_or_data, str):
            with open(filepath_or_data, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = filepath_or_data

        events = []

        per_chat_config = data.get("perChatPredictionConfig", {}).get("fields", [])
        system_prompt = ""
        for field in per_chat_config:
            if field.get("key") == "llm.prediction.systemPrompt":
                system_prompt = field.get("value", "")
                break

        if system_prompt:
            events.append({"event_type": "system_prompt", "content": system_prompt})

        messages = data.get("messages", [])
        for msg in messages:
            selected_idx = msg.get("currentlySelected", 0)
            versions = msg.get("versions", [])
            if not versions or selected_idx >= len(versions):
                continue

            active_version = versions[selected_idx]
            role = active_version.get("role")
            v_type = active_version.get("type")

            if v_type == "singleStep":
                contents = active_version.get("content", [])
                text_pieces = [c.get("text", "") for c in contents if c.get("type") == "text"]
                full_text = "".join(text_pieces).strip()
                if full_text:
                    events.append({"event_type": f"{role}_message", "content": full_text})

            elif v_type == "multiStep":
                steps = active_version.get("steps", [])
                for step in steps:
                    s_type = step.get("type")
                    if s_type != "contentBlock":
                        continue

                    style = step.get("style", {})
                    is_thinking = style.get("type") == "thinking"

                    for item in step.get("content", []):
                        item_type = item.get("type")

                        if item_type == "text":
                            text_val = item.get("text", "").strip()
                            if text_val:
                                events.append({
                                    "event_type": "thinking" if is_thinking else f"{role}_message",
                                    "content": text_val,
                                })

                        elif item_type == "toolCallRequest":
                            events.append({
                                "event_type": "tool_call",
                                "call_id": item.get("callId"),
                                "tool_name": item.get("name"),
                                "parameters": item.get("parameters", {}),
                            })

                        elif item_type == "toolCallResult":
                            raw_content = item.get("content", "")
                            try:
                                parsed = json.loads(raw_content)
                                if isinstance(parsed, list) and len(parsed) > 0 and "text" in parsed[0]:
                                    inner_text = parsed[0]["text"]
                                    try:
                                        content_val = json.loads(inner_text)
                                    except (json.JSONDecodeError, TypeError):
                                        content_val = inner_text
                                else:
                                    content_val = parsed
                            except (json.JSONDecodeError, TypeError):
                                content_val = raw_content

                            events.append({
                                "event_type": "tool_result",
                                "call_id": item.get("callId"),
                                "tool_name": item.get("name"),
                                "content": content_val,
                            })

        return events

    # ---- recovery scaffolding ----

    def _load_json_with_recovery(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_content = f.read()

        recovery_attempts = []

        try:
            data = json.loads(raw_content)
            return data
        except json.JSONDecodeError as e:
            recovery_attempts.append(f"Attempt 1 (direct): {e.msg}")

        try:
            fixed = self._fix_common_json_errors(raw_content)
            data = json.loads(fixed)
            print(f"✓ JSON recovered after fixing common syntax errors")
            return data
        except Exception as e:
            recovery_attempts.append(f"Attempt 2 (fix): {str(e)}")

        if JSON_REPAIR_AVAILABLE:
            try:
                repaired = repair_json(raw_content, return_objects=False)
                data = json.loads(repaired)
                print(f"✓ JSON recovered using json-repair library")
                return data
            except Exception as e:
                recovery_attempts.append(f"Attempt 3 (repair): {str(e)}")

        try:
            m = re.search(r'\{[\s\S]*\}', raw_content)
            if m:
                data = json.loads(m.group(0))
                print(f"✓ JSON recovered by extraction")
                return data
        except Exception as e:
            recovery_attempts.append(f"Attempt 4 (extract): {str(e)}")

        raise ValueError(
            f"Failed to parse '{os.path.basename(filepath)}':\n" + "\n".join(recovery_attempts)
        )

    def _fix_common_json_errors(self, content: str) -> str:
        content = re.sub(r',\s*([\]}])', r'\1', content)
        content = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', content)
        content = re.sub(r"'([^'\\]*(\\.[^'\\]*)*)'", r'"\1"', content)
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        content = re.sub(r'/\*[^*]*\*+(?:[^/*][^*]*\*+)*/', '', content)
        return content

    def _validate_token_count(self, data: Dict, filepath: str):
        text = self._extract_text_from_data(data)
        tokens = tracker.count_tokens(text)
        if tokens > self.max_token_count:
            raise ValueError(
                f"Content exceeds token limit: {tokens} (max {self.max_token_count}). File '{os.path.basename(filepath)}'."
            )

    def _extract_text_from_data(self, data) -> str:
        if isinstance(data, dict):
            return " ".join(self._extract_text_from_data(v) for v in data.values())
        elif isinstance(data, list):
            return " ".join(self._extract_text_from_data(i) for i in data)
        elif isinstance(data, str):
            return data
        return str(data)
