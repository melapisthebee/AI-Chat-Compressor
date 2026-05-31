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

    def process_and_adapt(self, db: DBSession, project_id: int, incoming_messages: List[Dict[str, str]], filename: str) -> Dict[str, Any]:
        """
        Orchestrates sliding window splitting, tokens diagnostics, historical extraction,
        and database committing loops for an active project workspace.
        """
        # Pull down native nested dicts from your migrated SQLAlchemy JSON schema
        active_knowledge = get_project_knowledge(db, project_id)
        
        total_raw_text = "\n".join([f"{m['role']}: {m['content']}" for m in incoming_messages])
        raw_token_count = tracker.count_tokens(total_raw_text)
        
        tail_messages = []
        historical_messages = []
        tail_tokens = 0
        
        msgs_to_process = list(incoming_messages)
        
        # 1. Split hot trailing context window away from history bounds
        while msgs_to_process:
            msg = msgs_to_process.pop()
            msg_len = tracker.count_tokens(msg['content'])
            
            if tail_tokens + msg_len <= settings.PRESERVE_RECENT_TOKENS:
                tail_messages.insert(0, msg)
                tail_tokens += msg_len
            else:
                remaining_tail_budget = settings.PRESERVE_RECENT_TOKENS - tail_tokens
                
                if remaining_tail_budget > 0:
                    tokens = tracker.split_into_tokens(msg['content'])
                    tail_ids = tokens[-remaining_tail_budget:]
                    hist_ids = tokens[:-remaining_tail_budget]
                    
                    tail_messages.insert(0, {"role": msg['role'], "content": tracker.decode_tokens(tail_ids)})
                    historical_messages.append({"role": msg['role'], "content": tracker.decode_tokens(hist_ids)})
                    tail_tokens += remaining_tail_budget
                else:
                    historical_messages.append(msg)
                
                while msgs_to_process:
                    historical_messages.append(msgs_to_process.pop())
                break
        
        historical_messages.reverse()

        # 2. Iterate slice windows over chronological history segments
        historical_text = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in historical_messages])
        raw_tokens_list = tracker.split_into_tokens(historical_text)
        
        chunk_size = settings.CHUNK_SIZE_TOKENS
        token_slices = [raw_tokens_list[i:i + chunk_size] for i in range(0, len(raw_tokens_list), chunk_size)]
        
        print(f"Slicing historical segment into {len(token_slices)} text chunks for synthesis...")
        
        for token_slice in token_slices:
            decoded_chunk = tracker.decode_tokens(token_slice)
            active_knowledge = self._call_llm_for_knowledge_merge(active_knowledge, decoded_chunk)

        # 3. Complete structural logging updates
        compressed_summary_block = "=== ADAPTIVE PROJECT CONTEXT ===\n" + json.dumps(active_knowledge, indent=2)
        compressed_payload_tokens = tracker.count_tokens(compressed_summary_block) + tail_tokens

        session_record = create_session_record(
            db=db, project_id=project_id, filename=filename,
            raw_tokens=raw_token_count, compressed_tokens=compressed_payload_tokens
        )

        # FIXED: Now forwarding the complete historical_text string as the raw validation context
        update_adaptive_knowledge(
            db=db, 
            project_id=project_id, 
            session_id=session_record.id,
            updated_knowledge=active_knowledge,
            raw_context_stream=historical_text  # Feeds the keyword validator layer
        )

        return active_knowledge