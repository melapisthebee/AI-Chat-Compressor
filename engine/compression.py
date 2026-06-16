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
from engine.streaming_processor import StreamingTokenProcessor, TokenBudgetManager
from database.queries import get_project_knowledge, create_session_record, update_adaptive_knowledge


class CompressionEngine:
    def __init__(self, streaming_processor: Optional[StreamingTokenProcessor] = None):
        """
        Initializes the compression engine client utilizing configured environment parameters
        loaded via Pydantic Settings. Assumes a running local instance of LM Studio.
        
        Args:
            streaming_processor: Optional custom streaming processor instance
        """
        self.client = OpenAI(
            base_url=settings.LM_STUDIO_BASE_URL,
            api_key=settings.LM_STUDIO_API_KEY,
            timeout=settings.REQUEST_TIMEOUT
        )
        self.streaming_processor = streaming_processor or StreamingTokenProcessor()
        self.token_budget_manager = TokenBudgetManager()
    
    def check_lm_studio_health(self) -> bool:
        """
        Checks if LM Studio is running and responding.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Try a simple models list call to verify connectivity
            response = self.client.models.list()
            models = list(response)
            if models:
                print(f"✓ LM Studio is healthy. Available models: {len(models)}")
                return True
            else:
                print("⚠️ LM Studio is running but returned no models")
                return False
        except Exception as e:
            print(f"❌ LM Studio health check failed: {str(e)}")
            print("   Please ensure LM Studio is running and the server is enabled.")
            return False

    def _call_llm_with_retry(self, call_func, *args, **kwargs):
        """
        Wrapper method that implements retry logic for LLM API calls.
        Retries on transient failures (connection errors, timeouts, rate limits) 
        with exponential backoff.
        
        Args:
            call_func: The function to call (e.g., self.client.chat.completions.create)
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            The response from the API call
            
        Raises:
            Exception: Re-raises the last exception if all retries are exhausted
        """
        max_retries = settings.MAX_RETRIES
        base_delay = settings.RETRY_BASE_DELAY
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return call_func(*args, **kwargs)
            except (APIConnectionError, APITimeoutError, RateLimitError) as e:
                last_exception = e
                error_str = str(e).lower()
                
                # Check for non-retryable errors (model unloaded, terminated, etc.)
                if "model is unloaded" in error_str or "terminated" in error_str:
                    print(f"❌ Non-retryable error: {str(e)}")
                    raise RuntimeError(f"Model unavailable: {str(e)}. Please reload the model in LM Studio and retry.")
                
                # For timeouts, provide helpful context
                if "timeout" in error_str and attempt == 0:
                    print(f"⚠️ First timeout detected. This can happen with large conversations or slow models.")
                    print(f"   LM Studio may still be processing. Retrying with exponential backoff...")
                
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    print(f"⚠️ Transient failure detected (attempt {attempt + 1}/{max_retries + 1}): {str(e)}")
                    print(f"🔄 Retrying in {delay} seconds...")
                    print(f"   💡 Tip: If this persists, try:\n      - Loading a smaller/faster model in LM Studio\n      - Increasing REQUEST_TIMEOUT in settings.py\n      - Reducing chunk size in the app")
                    time.sleep(delay)
                else:
                    print(f"❌ All {max_retries + 1} attempts failed. Last error: {str(e)}")
                    print(f"\n💡 Troubleshooting:")
                    print(f"   1. Check that LM Studio is running and the model is loaded")
                    print(f"   2. Try loading a smaller model (e.g., 7B instead of 70B)")
                    print(f"   3. Increase REQUEST_TIMEOUT in config/settings.py (currently {settings.REQUEST_TIMEOUT}s)")
                    print(f"   4. Reduce chunk size in the app settings")
                    raise RuntimeError(f"LM Studio API failed after {max_retries + 1} attempts. {str(e)}")
            except Exception as e:
                # Check for non-retryable errors in other exceptions too
                error_str = str(e).lower()
                if "model is unloaded" in error_str or "terminated" in error_str:
                    print(f"❌ Non-retryable error: {str(e)}")
                    raise RuntimeError(f"Model unavailable: {str(e)}. Please reload the model in LM Studio and retry.")
                # Non-transient errors, don't retry
                print(f"❌ Non-retryable error: {str(e)}")
                raise
        
        # Should never reach here, but just in case
        raise last_exception

    def _deep_merge(self, base: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively updates the base dictionary structure with fresh delta attributes.
        Preserves untouched sibling keys at all depths of the nested JSON tree.
        """
        for key, value in delta.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def _call_llm_for_knowledge_merge(self, current_knowledge: Dict[str, Any], raw_chunk: str) -> Dict[str, Any]:
        """
        Asks the local model to extract ONLY brand new updates, modifications, or active deltas.
        
        Implements progressive JSON recovery:
        1. Try exact parse
        2. Try with thought tag removal  
        3. Apply json-repair character-level correction (if available)
        4. Fallback to current_knowledge (preserve existing state)
        """
        system_prompt = (
            "You are a sharp, high-fidelity technical extraction engine. You never run code or write conversational fluff.\n"
            "Your task is to analyze a new conversation transcript chunk and extract workspace updates, architecture constraints, dependencies, or workflow states.\n\n"
            "CRITICAL CONSTRAINTS:\n"
            "1. Output ONLY a raw JSON object containing the NEW, UPDATED, or CHANGED components. Do NOT replicate unchanged categories or historical records.\n"
            "2. Structure extractions dynamically by grouping related files or tools under abstract, high-level structural layer keys that describe their architectural domain.\n"
            "3. Never output introductory conversational text, explanations, markdown fences, or <think> tags. Output exactly one valid JSON object.\n\n"
            "Format structure example for deltas:\n"
            "{\n"
            "  \"<insert_architectural_layer_key>\": {\n"
            "    \"<insert_file_or_component_name>\": {\n"
            "      \"command\": \"...\",\n"
            "      \"args\": [...],\n"
            "      \"workingDirectory\": \"...\",\n"
            "      \"dependencies\": [...],\n"
            "      \"technical_notes\": \"Detailed engineering modifications or additions go here...\"\n"
            "    }\n"
            "  },\n"
            "  \"current_active_track\": {\n"
            "    \"status\": \"Updated workflow state\",\n"
            "    \"active_issue_or_bug\": \"Description of errors or stack traces if identified...\",\n"
            "    \"next_immediate_steps\": \"Updated scannable steps to resume work...\"\n"
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
                response_format={"type": "text"}
            )
            
            raw_content = response.choices[0].message.content.strip()
            
            # Catch raw unpopulated strings or unresolved thinking loops early
            if not raw_content or raw_content.endswith("</think>"):
                return current_knowledge

            # Universal Thought Stripper: Clean tag structures before attempting JSON boundaries
            clean_content = re.sub(r'<(think|thinking|thought)>[\s\S]*?</\1>', '', raw_content, flags=re.IGNORECASE).strip()
            clean_content = re.sub(r'\[(think|thinking|thought)\][\s\S]*?\[/\1\]', '', clean_content, flags=re.IGNORECASE).strip()

            # Find outer object limits cleanly
            json_match = re.search(r'(\{[\s\S]*\})', clean_content)
            if not json_match:
                print("⚠️ No JSON structure found in LLM response for extraction pass")
                return current_knowledge  # Preserve existing state on parse failure
            
            raw_json_str = json_match.group(1).strip()
            recovery_attempts = []
                            
            # Attempt 1: Direct parse
            try:
                delta_payload = json.loads(raw_json_str)
                recovery_attempts.append("Attempt 1: Direct parse successful")
            except json.JSONDecodeError as e:
                recovery_attempts.append(f"Attempt 1 (direct): {str(e)}")
                # Attempt 2: Single-quote to double-quote replacement
                try:
                    fixed_json_str = raw_json_str.replace("'", '"')
                    delta_payload = json.loads(fixed_json_str)
                    recovery_attempts.append("Attempt 2: Quote normalization successful")
                except Exception as e:
                    recovery_attempts.append(f"Attempt 2 (quotes): {str(e)}")
                    # Attempt 3: Apply json-repair character-level correction
                    if JSON_REPAIR_AVAILABLE:
                        try:
                            repaired_str = repair_json(raw_json_str, return_objects=False)
                            delta_payload = json.loads(repaired_str)
                            recovery_attempts.append("Attempt 3: json-repair successful")
                        except Exception as e:
                            recovery_attempts.append(f"Attempt 3 (json-repair): {str(e)}")
                            # All recovery attempts failed - log detailed error
                            print(f"❌ JSON Recovery Failed in extraction pass after {len(recovery_attempts)} attempts:")
                            for attempt in recovery_attempts:
                                print(f"   - {attempt}")
                            print(f"   Raw response preview: {raw_json_str[:300]}...")
                            return current_knowledge  # Preserve existing state
                    else:
                        print("⚠️ json-repair library not installed - skipping character-level correction")
                        recovery_attempts.append("Attempt 3: Skipped (json-repair not installed)")
                        print(f"❌ JSON Recovery Failed after {len(recovery_attempts)} attempts")
                        for attempt in recovery_attempts:
                            print(f"   - {attempt}")
                        return current_knowledge  # Preserve existing state
            
            # Successful parse - log recovery if needed
            if len(recovery_attempts) > 1:
                print(f"✓ JSON extracted after {len(recovery_attempts)} recovery attempts")
                for attempt in recovery_attempts[1:]:  # Skip first success message
                    print(f"   Recovery: {attempt}")

            # DIVERGENCE POINT: Combine the state in memory deterministically using Python
            return self._deep_merge(current_knowledge, delta_payload)

        except Exception as e:
            raise RuntimeError(f"LM Studio API Connection Failure: {str(e)}")

    def _call_llm_for_verification(self, current_knowledge: Dict[str, Any], raw_chunk: str) -> Dict[str, Any]:
        """
        PASS 2 (Audit): Compares the current draft knowledge state against a specific source chunk.
        Returns a delta dictionary ONLY if gaps or hallucinations are detected.
        """
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
                response_format={"type": "text"}
            )
            
            return self._extract_json_from_response(response.choices[0].message.content)
            
        except Exception as e:
            # Audit failures should not crash the pipeline; log and return empty delta (no changes)
            print(f"Audit pass warning: {e}")
            return {}

    def _extract_json_from_response(self, content: str) -> Dict[str, Any]:
        """
        Centralized parser for LLM responses with progressive recovery strategies.
        
        Implements multi-stage JSON recovery:
        1. Try exact parse
        2. Try with thought tag removal
        3. Apply json-repair character-level correction (if available)
        4. Fallback to empty delta (preserve existing state)
        
        Args:
            content: Raw LLM response string potentially containing JSON
            
        Returns:
            Parsed JSON dictionary or empty dict on all failures
        """
        # Stage 1: Clean thought blocks first
        clean_content = re.sub(r'<(think|thinking|thought)>[\s\S]*?</\1>', '', content, flags=re.IGNORECASE).strip()
        clean_content = re.sub(r'\[(think|thinking|thought)\][\s\S]*?\[/\1\]', '', clean_content, flags=re.IGNORECASE).strip()
        
        # Stage 2: Find outer JSON object boundaries
        json_match = re.search(r'(\{[\s\S]*\})', clean_content)
        if not json_match:
            print("⚠️ No JSON object found in LLM response")
            return {}
        
        json_str = json_match.group(1).strip()
        recovery_attempts = []
        
        # Attempt 1: Direct parse
        try:
            result = json.loads(json_str)
            if recovery_attempts:
                print(f"✓ JSON recovered on attempt {len(recovery_attempts) + 1}: Direct parse")
            return result
        except json.JSONDecodeError as e:
            recovery_attempts.append(f"Attempt 1 (direct): {str(e)}")
        
        # Attempt 2: Single-quote to double-quote replacement
        try:
            fixed_str = json_str.replace("'", '"')
            result = json.loads(fixed_str)
            recovery_attempts.append("Attempt 2: Single-quote replacement")
            print(f"✓ JSON recovered on attempt {len(recovery_attempts)}: Quote normalization")
            return result
        except Exception as e:
            recovery_attempts.append(f"Attempt 2 (quotes): {str(e)}")
        
        # Attempt 3: json-repair library (character-level correction)
        if JSON_REPAIR_AVAILABLE:
            try:
                repaired_str = repair_json(json_str, return_objects=False)
                result = json.loads(repaired_str)
                recovery_attempts.append("Attempt 3: json-repair character-level correction")
                print(f"✓ JSON recovered on attempt {len(recovery_attempts)}: json-repair library")
                return result
            except Exception as e:
                recovery_attempts.append(f"Attempt 3 (json-repair): {str(e)}")
        else:
            recovery_attempts.append("Attempt 3: json-repair not installed")
        
        # Attempt 4: Remove trailing content and try again
        try:
            # Try to find valid JSON prefix before any trailing garbage
            clean_str = re.sub(r'[,\}\]\s]*$', '', json_str)
            result = json.loads(clean_str)
            recovery_attempts.append("Attempt 4: Trailing content removal")
            print(f"✓ JSON recovered on attempt {len(recovery_attempts)}: Trailing cleanup")
            return result
        except Exception as e:
            recovery_attempts.append(f"Attempt 4 (trailing): {str(e)}")
        
        # All attempts failed - log detailed context for debugging
        error_log = "\n".join(recovery_attempts)
        print(f"❌ JSON Recovery Failed after all attempts:")
        print(f"   Original content length: {len(json_str)} chars")
        print(f"   Recovery attempts:\n{error_log}")
        if len(json_str) > 200:
            print(f"   First 200 chars: {json_str[:200]}...")
        else:
            print(f"   Content: {json_str}")
        
        # Fallback: Return empty delta to preserve existing state
        return {}

    def process_and_adapt(self, db: DBSession, project_id: int, incoming_messages: List[Dict[str, str]], filename: str) -> Dict[str, Any]:
        """
        Orchestrates the two-pass 'Map-Verify' pipeline with streaming support:
        1. Extract: Slices and extracts draft knowledge states.
        2. Audit: Validates draft states against source text.
        3. Commit: Updates the adaptive knowledge core.
        
        Uses streaming chunk processing for memory efficiency on large files.
        """
        # Health check before starting
        print("\n🔍 Checking LM Studio connectivity...")
        if not self.check_lm_studio_health():
            raise RuntimeError("LM Studio is not responding. Please start LM Studio, load a model, and enable the server.")
        
        # Load baseline
        print("💾 Loading current project knowledge state...")
        active_knowledge = get_project_knowledge(db, project_id)
        if active_knowledge:
            print(f"✓ Loaded {len(active_knowledge)} existing knowledge categories")
        else:
            print("ℹ️ Starting with empty knowledge base")
        
        # Prepare text streams
        total_raw_text = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in incoming_messages])
        raw_token_count = tracker.count_tokens(total_raw_text)
        print(f"\n📊 Processing conversation with {raw_token_count:,} estimated tokens...")
        print(f"⏱️  Request timeout set to {settings.REQUEST_TIMEOUT} seconds")
        
        # Track progress externally
        processing_stats = {'chunks_processed': 0, 'total_tokens_processed': 0}
        
        # Define chunk processing callback
        def process_chunk_callback(chunk_data, chunk_index):
            """Process a single chunk through the LLM pipeline."""
            nonlocal active_knowledge
            decoded_chunk = chunk_data['text']
            
            # Enhanced progress indicator with detailed state
            if chunk_index % 5 == 0 or chunk_data['is_tail_chunk']:
                status = "(TAIL CHUNK)" if chunk_data['is_tail_chunk'] else f"({processing_stats['chunks_processed']} LLM calls made)"
                print(f"🔄 Processing chunk {chunk_index}... ({len(decoded_chunk)} chars, {chunk_data['token_count']} tokens) {status}")
                print(f"   📊 Current knowledge categories: {len(active_knowledge.keys())}")
            
            # PASS 1: EXTRACTION for this chunk
            print(f"   🔍 Extraction pass on chunk {chunk_index}...")
            try:
                delta = self._call_llm_for_knowledge_merge(active_knowledge, decoded_chunk)
                if delta:  # Only log if there's actual content
                    print(f"   ✓ Extracted {len(delta)} new/updated categories")
                active_knowledge = self._deep_merge(active_knowledge, delta)
            except Exception as e:
                print(f"   ⚠️ Extraction error on chunk {chunk_index}: {str(e)[:100]}")
                # Continue with existing knowledge
            
            # PASS 2: AUDIT for this chunk (only if extraction succeeded)
            print(f"   🔎 Audit pass on chunk {chunk_index}...")
            try:
                audit_delta = self._call_llm_for_verification(active_knowledge, decoded_chunk)
                if audit_delta:
                    print(f"   ✓ Audit found {len(audit_delta)} corrections/additions")
                    active_knowledge = self._deep_merge(active_knowledge, audit_delta)
            except Exception as e:
                print(f"   ⚠️ Audit error on chunk {chunk_index}: {str(e)[:100]}")
                # Continue with existing knowledge
            
            # Update stats
            processing_stats['chunks_processed'] = chunk_index + 1
            processing_stats['total_tokens_processed'] += chunk_data['token_count']
            
            return {
                'chunk_index': chunk_index,
                'tokens_processed': chunk_data['token_count'],
                'is_tail_chunk': chunk_data['is_tail_chunk'],
                'active_categories': len(active_knowledge.keys())
            }
        
        # Use streaming processor for memory-efficient processing
        print(f"Extraction & Audit Pass: Processing with streaming chunks...")
        print(f"Chunk size: {self.streaming_processor.chunk_size_tokens} tokens")
        print(f"Overlap: {self.streaming_processor.overlap_tokens} tokens")
        
        try:
            print("\n🚀 Starting LLM processing...")
            result = self.streaming_processor.stream_process_large_file(
                text=total_raw_text,
                process_chunk_callback=process_chunk_callback,
                preserve_tail=True
            )
            stream_stats = result.get('statistics', {})
            print(f"\n✅ Completed processing {stream_stats.get('total_chunks_processed', 0)} chunks")
        except RuntimeError as e:
            # Re-raise critical errors (like model unloaded)
            raise
        except Exception as e:
            # Wrap other errors with context
            raise RuntimeError(f"Error during chunk processing: {str(e)}") from e
        
        # Update processing statistics
        self.streaming_processor.update_stats(
            raw_tokens=raw_token_count,
            compressed_tokens=0  # Will be calculated after compression
        )
        
        # COMMIT
        compressed_summary_block = json.dumps(active_knowledge)
        compressed_payload_tokens = tracker.count_tokens(compressed_summary_block)
        
        # Update stats with final compressed count
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
        
        # Update stats with final compressed count and prepare dashboard data
        dashboard_data = self.streaming_processor.get_dashboard_data()
        
        print(f"\n📊 Dashboard Data: {dashboard_data}")
        print(f"✅ Knowledge base updated with {len(active_knowledge)} categories")
        
        # Return dashboard data along with knowledge
        stream_stats = result.get('statistics', {})
        return {
            'knowledge': active_knowledge,
            'dashboard_data': dashboard_data,
            'processing_stats': {
                'chunks_processed': stream_stats.get('total_chunks_processed', 0),
                'total_tokens_processed': stream_stats.get('total_raw_tokens', 0),
                'processing_time_seconds': stream_stats.get('processing_time_seconds', 0),
                'memory_efficiency': stream_stats.get('memory_efficiency', 0)
            }
        }
