import json
import re
from typing import List, Dict
from openai import OpenAI
from sqlalchemy.orm import Session as DBSession

from config.settings import settings
from engine.tokenizer import tracker
from database.queries import get_project_knowledge, create_session_record, update_adaptive_knowledge

class CompressionEngine:
    def __init__(self):
        self.client = OpenAI(
            base_url=settings.LM_STUDIO_BASE_URL,
            api_key=settings.LM_STUDIO_API_KEY
        )

    def _call_llm_for_knowledge_merge(self, current_knowledge: Dict[str, str], raw_chunk: str) -> Dict[str, str]:
        """Asks the local model to merge raw context into the existing project state."""
        system_prompt = (
            "You are a strict data-serialization engine mapping developer workspaces. You never run code.\n"
            "Your task is to update the 'Current Knowledge Categories' dictionary based on fresh log segments.\n\n"
            "CRITICAL CONSTRAINTS & INHERITANCE RULES:\n"
            "1. YOU MUST INHERIT AND PRESERVE ALL EXISTING CATEGORIES AND KEYS from 'Current Knowledge Categories'.\n"
            "2. Do NOT delete, clear, or overwrite an existing configuration block unless explicitly told to.\n"
            "3. HIGH-FIDELITY EXTRACTION REQUIRED: Group components under clear, high-level category keys that you invent based on the context (e.g., 'mcp_servers', 'frontend_modules', 'database_utilities').\n"
            "4. Never output introductory conversational text or <think> tags. Output exactly one raw JSON object.\n\n"
            "Format example:\n"
            "{\n"
            "  \"<insert_system_group_name>\": {\n"
            "    \"<insert_component_name>\": {\n"
            "      \"command\": \"...\",\n"
            "      \"args\": [...],\n"
            "      \"workingDirectory\": \"...\",\n"
            "      \"dependencies\": [...],\n"
            "      \"technical_notes\": \"Detailed engineering descriptions, rules, or paths go here...\"\n"
            "    }\n"
            "  },\n"
            "  \"current_active_track\": {\n"
            "    \"status\": \"Current workflow state (e.g., Debugging / Implementation / Testing)\",\n"
            "    \"active_issue_or_bug\": \"Clear description of active errors, stack traces, or broken features...\",\n"
            "    \"next_immediate_steps\": \"Bulleted string of the next mechanical steps to resume work seamlessly...\"\n"
            "  }\n"
            "}"
        )

        user_payload = {
            "Current Knowledge Categories": current_knowledge,
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
            
            if not raw_content or raw_content.endswith("</think>"):
                return current_knowledge

            # Upgraded Universal Thought Stripper
            # Uses a backreference (\1) to ensure matching open/close tags are cleanly wiped
            clean_content = re.sub(r'<(think|thinking|thought)>[\s\S]*?</\1>', '', raw_content, flags=re.IGNORECASE).strip()
            clean_content = re.sub(r'\[(think|thinking|thought)\][\s\S]*?\[/\1\]', '', clean_content, flags=re.IGNORECASE).strip()

            # Now find the true outer JSON boundaries safely
            json_match = re.search(r'(\{[\s\S]*\})', clean_content)
            if json_match:
                clean_json_str = json_match.group(1).strip()
                
                try:
                    return json.loads(clean_json_str)
                except json.JSONDecodeError:
                    # SMART AUTO-REPAIR: Fix loose backslashes only if they aren't already valid JSON escapes
                    try:
                        fixed_json_str = clean_json_str.replace("'", '"')
                        # Doubling only single backslashes not followed by standard escape codes
                        fixed_json_str = re.sub(r'\\(?!["\\\/bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', fixed_json_str)
                        return json.loads(fixed_json_str)
                    except Exception:
                        raise ValueError("JSON structural formatting remains invalid after basic repair patches.")
            else:
                return current_knowledge

        except Exception as e:
            print(f"Extraction pipeline bypass: {e}")
            return current_knowledge

    def process_and_adapt(self, db: DBSession, project_id: int, incoming_messages: List[Dict[str, str]], filename: str):
        """Executes sliding window compression with partial message splitting."""
        active_knowledge = get_project_knowledge(db, project_id)
        
        total_raw_text = "\n".join([f"{m['role']}: {m['content']}" for m in incoming_messages])
        raw_token_count = tracker.count_tokens(total_raw_text)
        
        tail_messages = []
        historical_messages = []
        tail_tokens = 0
        
        # Copy message array to process backward safely
        msgs_to_process = list(incoming_messages)
        
        # 1. Distribute context into Hot Tail vs. Older History
        while msgs_to_process:
            msg = msgs_to_process.pop()
            msg_len = tracker.count_tokens(msg['content'])
            
            # If the entire message fits in the remaining tail budget, take it
            if tail_tokens + msg_len <= settings.PRESERVE_RECENT_TOKENS:
                tail_messages.insert(0, msg)
                tail_tokens += msg_len
            else:
                # The message crosses the boundary. Split it!
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
                
                # All remaining backward messages belong entirely to history
                while msgs_to_process:
                    historical_messages.append(msgs_to_process.pop())
                break
        
        # Restore chronological order for historical tracking
        historical_messages.reverse()

        # 2. Process historical text slices through the LLM
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
        
        # PASS NATIVE DICTIONARIES - Do NOT use json.dumps() or wrap keys in string blocks!
        update_adaptive_knowledge(
            db=db, project_id=project_id, session_id=session_record.id,
            updated_knowledge=active_knowledge
        )
        
        return active_knowledge