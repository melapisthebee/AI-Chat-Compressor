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

    def check_lm_studio_health(self) -> bool:
        try:
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
            try:
                return call_func(*args, **kwargs)
            except (APIConnectionError, APITimeoutError, RateLimitError) as e:
                last_exception = e
                error_str = str(e).lower()

                if "model is unloaded" in error_str or "terminated" in error_str:
                    self.logger.log(f"Non-retryable error: {str(e)}")
                    raise RuntimeError(f"Model unavailable: {str(e)}. Please reload the model in LM Studio and retry.")

                if "timeout" in error_str and attempt == 0:
                    self.logger.log("First timeout detected. This can happen with large conversations or slow models.")
                    self.logger.log("   LM Studio may still be processing. Retrying with exponential backoff...")

                if attempt < max_retries:
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

    def _deep_compare(self, base: Dict[str, Any], delta: Dict[str, Any]) -> bool:
        if set(base.keys()) != set(delta.keys()):
            return False
        for key in base.keys():
            if key not in delta:
                return False
            if isinstance(base[key], dict) and isinstance(delta[key], dict):
                if not self._deep_compare(base[key], delta[key]):
                    return False
            elif base[key] != delta[key]:
                return False
        return True

    def _deep_merge(self, base: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
        if self._deep_compare(base, delta):
            return base

        for key, value in delta.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

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
            '    "next_immediate_steps": "Updated scannable steps to resume work..."'
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

            raw_json_str = json_match.group(1).strip()
            recovery_attempts = []

            try:
                delta_payload = json.loads(raw_json_str)
                recovery_attempts.append("Attempt 1: Direct parse successful")
            except json.JSONDecodeError as e:
                recovery_attempts.append(f"Attempt 1 (direct): {str(e)}")
                try:
                    fixed_json_str = raw_json_str.replace("'", '"')
                    delta_payload = json.loads(fixed_json_str)
                    recovery_attempts.append("Attempt 2: Quote normalization successful")
                except Exception as e:
                    recovery_attempts.append(f"Attempt 2 (quotes): {str(e)}")
                    if JSON_REPAIR_AVAILABLE:
                        try:
                            repaired_str = repair_json(raw_json_str, return_objects=False)
                            delta_payload = json.loads(repaired_str)
                            recovery_attempts.append("Attempt 3: json-repair successful")
                        except Exception as e:
                            recovery_attempts.append(f"Attempt 3 (json-repair): {str(e)}")
                            self.logger.log(f"JSON Recovery Failed in extraction pass chunk {chunk_index} after {len(recovery_attempts)} attempts:")
                            for attempt in recovery_attempts:
                                self.logger.log(f"   - {attempt}")
                            return current_knowledge
                    else:
                        recovery_attempts.append("Attempt 3: Skipped (json-repair not installed)")
                        self.logger.log(f"JSON Recovery Failed in extraction pass chunk {chunk_index} after {len(recovery_attempts)} attempts")
                        for attempt in recovery_attempts:
                            self.logger.log(f"   - {attempt}")
                        return current_knowledge

            if len(recovery_attempts) > 1:
                self.logger.log(f"JSON extracted after {len(recovery_attempts)} recovery attempts (chunk {chunk_index})")

            return self._deep_merge(current_knowledge, delta_payload)

        except Exception as e:
            raise RuntimeError(f"LM Studio API Connection Failure: {str(e)}")

    def _call_llm_for_verification(self, current_knowledge: Dict[str, Any], raw_chunk: str, chunk_index: int) -> Dict[str, Any]:
        system_prompt = (
            "You are a Quality Assurance Auditor for an LLM Knowledge extraction system.\n"
            "Your task is to compare an existing Knowledge State against a Raw Text Chunk.\n"
            "1. If the knowledge state is comprehensive and accurate based on the chunk, return an empty JSON object: {}\n"
            "2. If the chunk contains critical information NOT present in the knowledge state, OR if the state contains hallucinations contradicted by the chunk, output a JSON object with ONLY the corrections/additions.\n"
            "3. Do not replicate the full state. Output only the delta (key-value pairs to update or add).\n"
            "4. Never output conversational text, explanations, or markdown fences. Return valid JSON only."
        )

        user_payload = {
            "Draft Knowledge State": current_knowledge,
            "Source Text Chunk": raw_chunk
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
                extra_body={"prompt_quantization": "Q8_0"}
            )

            raw_content = response.choices[0].message.content.strip()

            # Log the raw AI output for debugging
            self.logger.log_ai_output(f"AUDIT chunk {chunk_index}", raw_content)

            return self._extract_json_from_response(raw_content)

        except Exception as e:
            self.logger.log(f"Audit pass warning chunk {chunk_index}: {e}")
            return {}

    def _extract_json_from_response(self, content: str) -> Dict[str, Any]:
        clean_content = re.sub(r'<(think|thinking|thought)>[\s\S]*?</\1>', '', content, flags=re.IGNORECASE).strip()
        clean_content = re.sub(r'\[(think|thinking|thought)\][\s\S]*?\[/\1\]', '', clean_content, flags=re.IGNORECASE).strip()

        json_match = re.search(r'(\{[\s\S]*\})', clean_content)
        if not json_match:
            return {}

        json_str = json_match.group(1).strip()
        recovery_attempts = []

        try:
            result = json.loads(json_str)
            if recovery_attempts:
                self.logger.log(f"JSON recovered on attempt {len(recovery_attempts) + 1}: Direct parse")
            return result
        except json.JSONDecodeError as e:
            recovery_attempts.append(f"Attempt 1 (direct): {str(e)}")

        try:
            fixed_str = json_str.replace("'", '"')
            result = json.loads(fixed_str)
            recovery_attempts.append("Attempt 2: Single-quote replacement")
            self.logger.log(f"JSON recovered on attempt {len(recovery_attempts)}: Quote normalization")
            return result
        except Exception as e:
            recovery_attempts.append(f"Attempt 2 (quotes): {str(e)}")

        if JSON_REPAIR_AVAILABLE:
            try:
                repaired_str = repair_json(json_str, return_objects=False)
                result = json.loads(repaired_str)
                recovery_attempts.append("Attempt 3: json-repair character-level correction")
                self.logger.log(f"JSON recovered on attempt {len(recovery_attempts)}: json-repair library")
                return result
            except Exception as e:
                recovery_attempts.append(f"Attempt 3 (json-repair): {str(e)}")
        else:
            recovery_attempts.append("Attempt 3: json-repair not installed")

        try:
            clean_str = re.sub(r'[,\}\]\s]*$', '', json_str)
            result = json.loads(clean_str)
            recovery_attempts.append("Attempt 4: Trailing content removal")
            self.logger.log(f"JSON recovered on attempt {len(recovery_attempts)}: Trailing cleanup")
            return result
        except Exception as e:
            recovery_attempts.append(f"Attempt 4 (trailing): {str(e)}")

        error_log = "\n".join(recovery_attempts)
        self.logger.log(f"JSON Recovery Failed after all attempts:")
        self.logger.log(f"   Original content length: {len(json_str)} chars")
        self.logger.log(f"   Recovery attempts:\n{error_log}")
        if len(json_str) > 200:
            self.logger.log(f"   First 200 chars: {json_str[:200]}...")
        else:
            self.logger.log(f"   Content: {json_str}")

        return {}

    def process_and_adapt(self, db: DBSession, project_id: int, incoming_messages: List[Dict[str, str]], filename: str) -> Dict[str, Any]:
        # Initialize per-run logger
        self.logger = RunLogger()

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
        llm_call_count = 0

        # Store chunk texts for the audit pass
        chunk_texts = {}

        # ---- PASS 1: EXTRACTION (all chunks) ----
        self.logger.log("=== PASS 1: EXTRACTION ===")

        def extraction_callback(chunk_data, chunk_index):
            nonlocal active_knowledge, llm_call_count
            decoded_chunk = chunk_data['text']

            # Store for audit pass
            chunk_texts[chunk_index] = decoded_chunk

            self.logger.log(f"Processing chunk {chunk_index}... ({len(decoded_chunk)} chars, {chunk_data['token_count']} tokens) [{llm_call_count} LLM calls made]")
            self.logger.log(f"   Current knowledge categories: {len(active_knowledge.keys())}")

            # EXTRACTION pass only
            self.logger.log(f"   Extraction pass on chunk {chunk_index}...")
            llm_call_count += 1
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
            self.logger.log(f"Extraction pass completed: {total_chunks} chunks processed, {llm_call_count} LLM calls made")
        except RuntimeError as e:
            raise
        except Exception as e:
            raise RuntimeError(f"Error during extraction processing: {str(e)}") from e

        # ---- PASS 2: AUDIT (all chunks) ----
        self.logger.log("=== PASS 2: AUDIT ===")

        audit_llm_call_count = 0
        chunk_indices = sorted(chunk_texts.keys())

        for ci in chunk_indices:
            decoded_chunk = chunk_texts[ci]
            self.logger.log(f"Audit pass on chunk {ci}... [{llm_call_count + audit_llm_call_count} LLM calls made]")
            audit_llm_call_count += 1

            try:
                audit_delta = self._call_llm_for_verification(active_knowledge, decoded_chunk, ci)
                if audit_delta:
                    self.logger.log(f"   Audit found {len(audit_delta)} corrections/additions for chunk {ci}")
                    active_knowledge = self._deep_merge(active_knowledge, audit_delta)
                else:
                    self.logger.log(f"   Audit found no changes needed for chunk {ci}")
            except Exception as e:
                self.logger.log(f"   Audit error on chunk {ci}: {str(e)[:200]}")

        total_llm_calls = llm_call_count + audit_llm_call_count
        self.logger.log(f"Audit pass completed: {total_chunks} chunks audited, {audit_llm_call_count} LLM calls made")
        self.logger.log(f"Total LLM calls this run: {total_llm_calls} ({llm_call_count} extraction + {audit_llm_call_count} audit)")

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
            compressed_tokens=compressed_payload_tokens
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
                'total_llm_calls': total_llm_calls,
            }
        }
