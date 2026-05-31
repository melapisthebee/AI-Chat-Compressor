import json
import re
from typing import List, Dict, Any
from openai import OpenAI
from sqlalchemy.orm import Session as DBSession

from config.settings import settings
from engine.tokenizer import tracker
from database.queries import get_project_knowledge, create_session_record, update_adaptive_knowledge

class CompressionEngine:
    def __init__(self):
        """
        Initializes the compression engine client utilizing configured environment parameters
        loaded via Pydantic Settings. Assumes a running local instance of LM Studio.
        """
        self.client = OpenAI(
            base_url=settings.LM_STUDIO_BASE_URL,
            api_key=settings.LM_STUDIO_API_KEY
        )

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
            response = self.client.chat.completions.create(
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
            if json_match:
                clean_json_str = json_match.group(1).strip()
                
                try:
                    delta_payload = json.loads(clean_json_str)
                except json.JSONDecodeError:
                    # Auto-repair loose quote serialization common in small model outputs
                    try:
                        fixed_json_str = clean_json_str.replace("'", '"')
                        fixed_json_str = re.sub(r'\\(?!["\\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', fixed_json_str)
                        delta_payload = json.loads(fixed_json_str)
                    except Exception:
                        raise ValueError("JSON payload formatting could not be verified by parsing engines.")

                # DIVERGENCE POINT: Combine the state in memory deterministically using Python
                return self._deep_merge(current_knowledge, delta_payload)
            else:
                return current_knowledge

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
                response = self.client.chat.completions.create(
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
            """Centralized parser for LLM responses to ensure structural integrity."""
            # Clean thoughts
            clean_content = re.sub(r'<(think|thinking|thought)>[\s\S]*?</\1>', '', content, flags=re.IGNORECASE).strip()
            clean_content = re.sub(r'\[(think|thinking|thought)\][\s\S]*?\[/\1\]', '', clean_content, flags=re.IGNORECASE).strip()
            
            json_match = re.search(r'(\{[\s\S]*\})', clean_content)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    # Attempt light repair
                    fixed = json_match.group(1).replace("'", '"')
                    try:
                        return json.loads(fixed)
                    except:
                        return {}
            return {}

    def process_and_adapt(self, db: DBSession, project_id: int, incoming_messages: List[Dict[str, str]], filename: str) -> Dict[str, Any]:
            """
            Orchestrates the two-pass 'Map-Verify' pipeline:
            1. Extract: Slices and extracts draft knowledge states.
            2. Audit: Validates draft states against source text.
            3. Commit: Updates the adaptive knowledge core.
            """
            # Load baseline
            active_knowledge = get_project_knowledge(db, project_id)
            
            # Prepare text streams
            total_raw_text = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in incoming_messages])
            raw_token_count = tracker.count_tokens(total_raw_text)
            
            # Slicing logic
            raw_tokens_list = tracker.split_into_tokens(total_raw_text)
            chunk_size = settings.CHUNK_SIZE_TOKENS
            token_slices = [raw_tokens_list[i:i + chunk_size] for i in range(0, len(raw_tokens_list), chunk_size)]
            
            # PASS 1: EXTRACTION
            print(f"Extraction Pass: Processing {len(token_slices)} segments...")
            for token_slice in token_slices:
                decoded_chunk = tracker.decode_tokens(token_slice)
                delta = self._call_llm_for_knowledge_merge(active_knowledge, decoded_chunk)
                active_knowledge = self._deep_merge(active_knowledge, delta)
                
            # PASS 2: AUDIT
            print(f"Audit Pass: Verifying state integrity...")
            for token_slice in token_slices:
                decoded_chunk = tracker.decode_tokens(token_slice)
                audit_delta = self._call_llm_for_verification(active_knowledge, decoded_chunk)
                if audit_delta:
                    active_knowledge = self._deep_merge(active_knowledge, audit_delta)

            # COMMIT
            compressed_summary_block = json.dumps(active_knowledge)
            compressed_payload_tokens = tracker.count_tokens(compressed_summary_block)

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
            
            return active_knowledge