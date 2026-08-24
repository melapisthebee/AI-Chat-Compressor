import sys, json, os, tempfile
sys.path.insert(0, '.')
from engine.discovery import get_lmstudio_conversations_dir, list_all_conversations
from pathlib import Path

# Build a fake LM Studio dir tree
tmp = tempfile.mkdtemp()
home_mock = Path(tmp) / "fakehome"
conv_dir = home_mock / ".lmstudio" / "conversations" / "Project A"
conv_dir.mkdir(parents=True)

with open(conv_dir / "chat1.json", 'w') as f:
    json.dump({"name": "Alpha", "assistantLastMessagedAt": 100}, f)
with open(conv_dir / "chat2.json", 'w') as f:
    json.dump({"name": "Beta", "assistantLastMessagedAt": 200, "preset": "default"}, f)

# Patch Path.home()
orig_home = Path.home
Path.home = lambda: home_mock

try:
    d = get_lmstudio_conversations_dir()
    expected = home_mock / ".lmstudio" / "conversations"
    assert d == expected, f"dir mismatch: {d} vs {expected}"

    chats = list_all_conversations()
    names = [c['name'] for c in chats]
    print(f"chats: {names}")
    assert names == ['Beta', 'Alpha'], f"not sorted by last_messaged_at: {names}"

    print("Discovery module OK")
finally:
    Path.home = orig_home
    import shutil; shutil.rmtree(tmp)
