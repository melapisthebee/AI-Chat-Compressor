# engine/discovery.py
import os
import json
from pathlib import Path
from typing import List, Dict, Any

def get_lmstudio_conversations_dir() -> Path:
    """Return the base conversations path across OS platforms."""
    home = Path.home()
    primary = home / ".lmstudio" / "conversations"
    if primary.exists():
        return primary

    alt = home / ".cache" / "lm-studio" / "conversations"
    if alt.exists():
        return alt

    # Default fallback - create directory structure if missing
    primary.mkdir(parents=True, exist_ok=True)
    return primary

def scan_all_conversations_recursive() -> List[Dict[str, Any]]:
    """
    Recursively scans ~/.lmstudio/conversations for all .json conversation files.
    Parses top-level headers and folder paths.
    """
    root_dir = get_lmstudio_conversations_dir()
    discovered = []

    # Recursively traverse directory tree downwards
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".json"):
                full_path = os.path.join(dirpath, filename)
                rel_folder = os.path.relpath(dirpath, root_dir)
                folder_tag = "Root" if rel_folder == "." else rel_folder

                try:
                    mtime = os.path.getmtime(full_path)
                    with open(full_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Header extraction
                    messages = data.get("messages", [])
                    title = data.get("name") or data.get("title") or Path(filename).stem

                    discovered.append({
                        "path": full_path,
                        "filename": filename,
                        "folder": folder_tag,
                        "title": title,
                        "created_at": data.get("createdAt"),
                        "last_updated": mtime,
                        "message_count": len(messages),
                        "raw_json": data
                    })
                except (json.JSONDecodeError, OSError):
                    continue

    # Sort descending by file modification timestamp
    discovered.sort(key=lambda x: x["last_updated"], reverse=True)
    return discovered


def find_latest_conversation():
    """Recursively scan for the most recently modified .json file."""
    conv_dir = get_lmstudio_conversations_dir()

    json_files = glob.glob(os.path.join(conv_dir, "**", "*.conversation.json"), recursive=True)
    if not json_files:
        json_files = glob.glob(os.path.join(conv_dir, "**", "*.json"), recursive=True)

    if not json_files:
        raise FileNotFoundError(f"No conversation JSON files found in {conv_dir}")

    return max(json_files, key=os.path.getmtime)


def list_all_conversations():
    """Return sorted list of dicts with metadata for every saved conversation."""
    conv_dir = get_lmstudio_conversations_dir()
    json_files = glob.glob(os.path.join(conv_dir, "**", "*.json"), recursive=True)

    summaries = []
    for filepath in json_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                summaries.append({
                    "path": filepath,
                    "name": data.get("name", "Untitled"),
                    "created_at": data.get("createdAt"),
                    "last_messaged_at": data.get("assistantLastMessagedAt"),
                    "preset": data.get("preset"),
                })
        except (json.JSONDecodeError, OSError):
            continue

    summaries.sort(key=lambda x: x.get("last_messaged_at") or 0, reverse=True)
    return summaries


def watch_active_chat(poll_interval=2):
    """Poll the conversation folder and auto-parse on every turn."""
    last_processed_time = 0
    current_file = None

    print("👀 Watching LM Studio conversations for updates...")

    while True:
        try:
            latest = find_latest_conversation()
            mtime = os.path.getmtime(latest)

            if latest != current_file or mtime > last_processed_time:
                current_file = latest
                last_processed_time = mtime

                print(f"\n🔄 Detected change in: {os.path.basename(latest)}")
                # events = parse_lm_studio_raw_json(latest)
                # print(f"Parsed {len(events)} events.")

        except Exception:
            pass

        time.sleep(poll_interval)


if __name__ == "__main__":
    try:
        latest_path = find_latest_conversation()
        print(f"🎯 Latest chat: {latest_path}")

        all_chats = list_all_conversations()
        print(f"📚 Discovered {len(all_chats)} conversations.")
    except Exception as e:
        print(f"Error discovering files: {e}")
