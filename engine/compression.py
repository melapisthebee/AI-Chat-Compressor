import json
import re
import time
from typing import List, Dict, Any, Optional
from openai import OpenAI, APIConnectionError, APITimeoutError, RateLimitError
from sqlalchemy.orm import Session as DBSession

try:
    from json_repair import repair_json
    JSON_REPAIR_AVAILABLE = True
except ImportError:
    JSON_REPAIR_AVAILABLE = False

from config.settings import settings
from engine.tokenizer import tracker
from engine.streaming_processor import streaming_processor, token_budget_manager
from engine.logger import RunLogger
from database.queries import get_project_knowledge, create_session_record, update_adaptive_knowledge


class CompressionEngine:
    def __init__(self, stats_callback=None):
        self.client = OpenAI(
            base_url=settings.LM_STUDIO_BASE_URL,
            api_key=settings.LM_STUDIO_API_KEY,
            timeout=settings.REQUEST_TIMEOUT
        )
        self.streaming_processor = streaming_processor
        self.token_budget_manager = token_budget_manager
        self.stats_callback = stats_callback
        self._http_request_count = 0
        self.logger = RunLogger()  # Available for health checks and all LLM calls

    def check_lm_studio_health(self) -> bool:
        try:
            self._http_request_count += 1
            response = self.client.models.list()
            models = list(response)
            if models:
                self.logger.log(f"LM Studio is healthy. Available models: {len(models)}")
                return True
            else:
                self.logger.log("LM Studio is running but returned no models")
                return False
        except Exception as e:
            self.logger.log(f"LM Studio health check failed: {str(e)}")
            self.logger.log("   Please ensure LM Studio is running and the server is enabled.")
            return False

    def _call_llm_with_retry(self, call_func, *args, **kwargs):
        max_retries = settings.MAX_RETRIES
        base_delay = settings.RETRY_BASE_DELAY
        last_exception = None

        for attempt in range(max_retries + 1):
            self._http_request_count += 1
            try:
                return call_func(*args, **kwargs)
            except (APIConnectionError, APITimeoutError, RateLimitError) as e:
                last_exception = e
                error_str = str(e).lower()

                if "model is unloaded" in error_str or "terminated" in error_str:
                    self.logger.log(f"Non-retryable error: {str(e)}")
                    raise RuntimeError(f"Model unavailable: {str(e)}. Please reload the model in LM Studio and retry.")

                if "timeout" in error_str:
                    if attempt == 0:
                        self.logger.log("First timeout detected. This can happen with large conversations or slow models.")
                        self.logger.log("   LM Studio may still be processing. Retrying with exponential backoff...")
                    else:
                        self.logger.log(f"Retry timeout on attempt {attempt + 1}. LM Studio may still be processing from a previous attempt.")

                if "timeout" in error_str and attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    self.logger.log(f"Transient failure (attempt {attempt + 1}/{max_retries + 1}): {str(e)}")
                    self.logger.log(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                elif "timeout" in error_str and attempt == max_retries:
                    self.logger.log(f"Timeout after {max_retries + 1} attempts. LM Studio may still be processing.")
                    self.logger.log(f"Last error: {str(e)}")
                    raise RuntimeError(f"LM Studio API timed out after {max_retries + 1} attempts. {str(e)}")
                elif attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    self.logger.log(f"Transient failure (attempt {attempt + 1}/{max_retries + 1}): {str(e)}")
                    self.logger.log(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    self.logger.log(f"All {max_retries + 1} attempts failed. Last error: {str(e)}")
                    raise RuntimeError(f"LM Studio API failed after {max_retries + 1} attempts. {str(e)}")
            except Exception as e:
                error_str = str(e).lower()
                if "model is unloaded" in error_str or "terminated" in error_str:
                    self.logger.log(f"Non-retryable error: {str(e)}")
                    raise RuntimeError(f"Model unavailable: {str(e)}. Please reload the model in LM Studio and retry.")
                self.logger.log(f"Non-retryable error: {str(e)}")
                raise

        raise last_exception

    def _reconstruct_json(self, raw_content: str, context: str = "") -> Dict[str, Any]:
        """Unified JSON extraction with 4-stage recovery. Returns parsed dict or {}."""
        clean = re.sub(r'<(think|thinking|thought)>[\s\S]*?</\1>', '', raw_content, flags=re.IGNORECASE).strip()
        clean = re.sub(r'\[(think|thinking|thought)\][\s\S]*?\[/\1\]', '', clean, flags=re.IGNORECASE).strip()
        json_match = re.search(r'(\{[\s\S]*\})', clean)
        if not json_match:
            self.logger.log(f"JSON extraction failed ({context}): no JSON structure found")
            return {}

        json_str = json_match.group(1).strip()
        attempts: list[str] = []

        # Stage 1: direct parse
        try:
            result = json.loads(json_str)
            if attempts:
                self.logger.log(f"JSON recovered {context}: attempt {len(attempts)+1} ({attempts[0].split(':')[0]})")
            return result
        except json.JSONDecodeError as e:
            attempts.append(f"direct: {e}")

        # Stage 2: quote normalization
        try:
            result = json.loads(json_str.replace("'", '"'))
            attempts.append("quotes")
            self.logger.log(f"JSON recovered {context}: attempt {len(attempts)} (quote normalization)")
            return result
        except Exception as e:
            attempts.append(f"quotes: {e}")

        # Stage 3: json-repair library
        if JSON_REPAIR_AVAILABLE:
            try:
                repaired = repair_json(json_str, return_objects=False)
                result = json.loads(repaired)
                attempts.append("json-repair")
                self.logger.log(f"JSON recovered {context}: attempt {len(attempts)} (json-repair)")
                return result
            except Exception as e:
                attempts.append(f"json-repair: {e}")
        else:
            attempts.append("json-repair: not installed")

        # Stage 4: trailing content removal
        try:
            cleaned = re.sub(r'[,}\]\s]*$', '', json_str)
            result = json.loads(cleaned)
            attempts.append("trailing cleanup")
            self.logger.log(f"JSON recovered {context}: attempt {len(attempts)} (trailing removal)")
            return result
        except Exception as e:
            attempts.append(f"trailing: {e}")

        self.logger.log(f"JSON Recovery Failed {context} after {len(attempts)} attempts")
        for a in attempts:
            self.logger.log(f"   - {a}")
        if len(json_str) > 200:
            self.logger.log(f"   Content preview: {json_str[:200]}...")
        return {}

    def _deep_merge(self, base: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
        # Guard: reject deltas that replicate the full state (model regurgitation).
        if len(delta) > len(base) and len(base) > 0:
            self.logger.log(f"[WARN] Delta ({len(delta)} keys) larger than current knowledge ({len(base)} keys) - likely model regurgitation, rejecting")
            return dict(base)  # return copy so caller never mutates

        if not delta:
            return dict(base)

        merged = dict(base)
        for key, value in delta.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _call_llm_for_knowledge_merge(self, current_knowledge: Dict[str, Any], raw_chunk: str, chunk_index: int) -> Dict[str, Any]:
        system_prompt = (
            "You are a sharp, high-fidelity technical extraction engine. You never run code or write conversational fluff.\n"
            "Your task is to analyze a new conversation transcript chunk and extract workspace updates, architecture constraints, dependencies, or workflow states.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. Output ONLY a raw JSON object containing the NEW, UPDATED, or CHANGED components. Do NOT replicate unchanged categories or historical records.\n"
            "2. Structure extractions dynamically by grouping related files or tools under abstract, high-level structural layer keys that describe their architectural domain.\n"
            "3. Never output introductory conversational text, explanations, markdown fences, or thinking tags. Output exactly one valid JSON object.\n\n"
            "Format structure example for deltas:\n"
            "{\n"
            '  "<insert_architectural_layer_key>": {\n'
            '    "<insert_file_or_component_name>": {\n'
            '      "command": "...",\n'
            '      "args": [...],\n'
            '      "workingDirectory": "...",\n'
            '      "dependencies": [...],\n'
            '      "technical_notes": "Detailed engineering modifications or additions go here..."'
            "    }\n"
            "  },\n"
            '  "current_active_track": {\n'
            '    "status": "Updated workflow state",\n'
            '    "active_issue_or_bug": "Description of errors or stack traces if identified...",\n'
            '    "next_immediate_steps": "Updated scannable steps to resume work..."\n'
            "  }\n"
            "}"
        )

        user_payload = {
            "Existing Context Reference": current_knowledge,
            "New Conversation Transcript Chunk": raw_chunk
        }

        try:
            response = self._call_llm_with_retry(
                self.client.chat.completions.create,
                model=settings.DEFAULT_COMPRESSION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, indent=2)}
                ],
                temperature=0.0,
                response_format={"type": "text"},
                max_tokens=4096,
                extra_body={"prompt_quantization": "Q8_0"}
            )

            raw_content = response.choices[0].message.content.strip()

            # Log the raw AI output for debugging
            self.logger.log_ai_output(f"EXTRACTION chunk {chunk_index}", raw_content)

            if not raw_content or raw_content.endswith("</think>"):
                return current_knowledge

            clean_content = re.sub(r'<(think|thinking|thought)>[\s\S]*?</\1>', '', raw_content, flags=re.IGNORECASE).strip()
            clean_content = re.sub(r'\[(think|thinking|thought)\][\s\S]*?\[/\1\]', '', clean_content, flags=re.IGNORECASE).strip()

            json_match = re.search(r'(\{[\s\S]*\})', clean_content)
            if not json_match:
                self.logger.log(f"No JSON structure found in LLM response for extraction pass chunk {chunk_index}")
                return current_knowledge

            delta_payload = self._reconstruct_json(clean_content, f"extraction chunk {chunk_index}")
            if not delta_payload and json_match:  # empty dict means full failure
                self.logger.log(f"JSON extraction failed for chunk {chunk_index}, keeping existing knowledge")
                return current_knowledge

            return self._deep_merge(current_knowledge, delta_payload)

        except Exception as e:
            raise RuntimeError(f"LM Studio API Connection Failure: {str(e)}")

    def _local_audit(self, current_knowledge: Dict[str, Any], raw_chunk: str, chunk_index: int) -> Dict[str, Any]:
        """Local (no API call) audit: finds knowledge keys whose keywords are absent from the chunk.
        Replaces the expensive LLM re-query with a cheap keyword-match check."""
        missing = {}
        chunk_lower = raw_chunk.lower()
        for category, content in current_knowledge.items():
            keywords = [kw for kw in re.findall(r'\w+', category.lower()) if len(kw) > 3]
            if keywords and not any(kw in chunk_lower for kw in keywords):
                missing[category] = content
        if missing:
            self.logger.log(f"[AUDIT] chunk {chunk_index}: found {len(missing)} categories with no keyword match in source")
        return missing  # return flagged categories for caller to handle

    def process_and_adapt(self, db: DBSession, project_id: int, incoming_messages: List[Dict[str, str]], filename: str) -> Dict[str, Any]:
        # Health check before starting
        self.logger.log("Checking LM Studio connectivity...")
        if not self.check_lm_studio_health():
            raise RuntimeError("LM Studio is not responding. Please start LM Studio, load a model, and enable the server.")

        # Load baseline
        self.logger.log("Loading current project knowledge state...")
        active_knowledge = get_project_knowledge(db, project_id) or {}
        if active_knowledge:
            self.logger.log(f"Loaded {len(active_knowledge)} existing knowledge categories")
        else:
            self.logger.log("Starting with empty knowledge base")

        # Prepare text streams
        total_raw_text = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in incoming_messages])
        raw_token_count = tracker.count_tokens(total_raw_text)
        self.logger.log(f"Processing conversation with {raw_token_count:,} estimated tokens...")
        self.logger.log(f"Request timeout set to {settings.REQUEST_TIMEOUT} seconds")

        # Track progress externally
        processing_stats = {'chunks_processed': 0, 'total_tokens_processed': 0}
        logical_call_count = 0
        self._http_request_count = 0

        # Store chunk texts for the audit pass
        chunk_texts = {}

        # ---- PASS 1: EXTRACTION (all chunks) ----
        self.logger.log("=== PASS 1: EXTRACTION ===")

        def extraction_callback(chunk_data, chunk_index):
            nonlocal active_knowledge, logical_call_count
            decoded_chunk = chunk_data['text']

            # Store for audit pass
            chunk_texts[chunk_index] = decoded_chunk

            self.logger.log(f"Processing chunk {chunk_index}... ({len(decoded_chunk)} chars, {chunk_data['token_count']} tokens) [{logical_call_count} logical calls, {self._http_request_count} HTTP requests]")
            self.logger.log(f"   Current knowledge categories: {len(active_knowledge.keys())}")

            # EXTRACTION pass only
            self.logger.log(f"   Extraction pass on chunk {chunk_index}...")
            logical_call_count += 1

            try:
                delta = self._call_llm_for_knowledge_merge(active_knowledge, decoded_chunk, chunk_index)
                if delta:
                    self.logger.log(f"   Extracted {len(delta)} new/updated categories from chunk {chunk_index}")
                active_knowledge = self._deep_merge(active_knowledge, delta)
            except Exception as e:
                self.logger.log(f"   Extraction error on chunk {chunk_index}: {str(e)[:200]}")

            processing_stats['chunks_processed'] = chunk_index + 1
            processing_stats['total_tokens_processed'] += chunk_data['token_count']

            # Emit live stats callback for dashboard updates
            if self.stats_callback and (chunk_index % 2 == 0 or chunk_data['is_tail_chunk']):
                compressed_summary_block = json.dumps(active_knowledge)
                current_compressed_tokens = tracker.count_tokens(compressed_summary_block)
                ratio = (current_compressed_tokens / raw_token_count * 100) if raw_token_count > 0 else 0
                self.stats_callback(
                    raw_tokens=raw_token_count,
                    compressed_tokens=current_compressed_tokens,
                    ratio=ratio,
                    chunks_processed=processing_stats['chunks_processed']
                )

            # Check budget
            compressed_summary_block = json.dumps(active_knowledge)
            current_compressed_tokens = tracker.count_tokens(compressed_summary_block)
            budget_reached = current_compressed_tokens >= self.streaming_processor.max_target_tokens

            return {
                'chunk_index': chunk_index,
                'tokens_processed': chunk_data['token_count'],
                'is_tail_chunk': chunk_data['is_tail_chunk'],
                'active_categories': len(active_knowledge.keys()),
                'current_compressed_tokens': current_compressed_tokens,
                'budget_reached': budget_reached
            }

        self.logger.log(f"Chunk size: {self.streaming_processor.chunk_size_tokens} tokens")
        self.logger.log(f"Overlap: {self.streaming_processor.overlap_tokens} tokens")
        self.logger.log("Starting LLM processing - EXTRACTION PASS...")

        try:
            result = self.streaming_processor.stream_process_large_file(
                text=total_raw_text,
                process_chunk_callback=extraction_callback,
                preserve_tail=True
            )
            stream_stats = result.get('statistics', {})
            total_chunks = stream_stats.get('total_chunks_processed', 0)
            self.logger.log(f"Extraction pass completed: {total_chunks} chunks processed, {logical_call_count} logical calls ({self._http_request_count} HTTP requests)")
        except RuntimeError as e:
            raise
        except Exception as e:
            raise RuntimeError(f"Error during extraction processing: {str(e)}") from e

        # ---- PASS 2: LOCAL AUDIT (no API calls) ----
        self.logger.log("=== PASS 2: LOCAL AUDIT ===")

        chunk_indices = sorted(chunk_texts.keys())
        for ci in chunk_indices:
            decoded_chunk = chunk_texts[ci]
            self._local_audit(active_knowledge, decoded_chunk, ci)

        total_logical_calls = logical_call_count
        self.logger.log(f"Audit pass completed: {total_chunks} chunks audited (local)")
        self.logger.log(f"Total LLM calls this run: {total_logical_calls} logical calls ({self._http_request_count} HTTP requests)")

        # Update processing statistics
        self.streaming_processor.update_stats(
            raw_tokens=raw_token_count,
            compressed_tokens=0
        )

        # COMMIT
        compressed_summary_block = json.dumps(active_knowledge)
        compressed_payload_tokens = tracker.count_tokens(compressed_summary_block)

        self.streaming_processor.stats['total_compressed_tokens'] = compressed_payload_tokens
        self.streaming_processor.stats['compression_ratio'] = self.streaming_processor.calculate_compression_ratio(
            raw_token_count, compressed_payload_tokens
        )

        session_record = create_session_record(
            db=db,
            project_id=project_id,
            filename=filename,
            raw_tokens=raw_token_count,
            compressed_tokens=compressed_payload_tokens,
            knowledge_snapshot=active_knowledge
        )

        update_adaptive_knowledge(
            db=db,
            project_id=project_id,
            session_id=session_record.id,
            updated_knowledge=active_knowledge,
            raw_context_stream=total_raw_text
        )

        dashboard_data = self.streaming_processor.get_dashboard_data()

        self.logger.log(f"Knowledge base updated with {len(active_knowledge)} categories")
        self.logger.log(f"Run log: {self.logger.main_log_path}")
        self.logger.log(f"AI output log: {self.logger.ai_output_path}")

        # Close the logger (appends completion timestamp)
        self.logger.close()

        return {
            'knowledge': active_knowledge,
            'dashboard_data': dashboard_data,
            'processing_stats': {
                'chunks_processed': stream_stats.get('total_chunks_processed', 0),
                'total_tokens_processed': stream_stats.get('total_raw_tokens', 0),
                'processing_time_seconds': stream_stats.get('processing_time_seconds', 0),
                'memory_efficiency': stream_stats.get('memory_efficiency', 0),
                'total_logical_calls': total_logical_calls,
                'total_http_requests': self._http_request_count,
            }
        }
