import sys, importlib.util
sys.path.insert(0, '.')

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec.loader)
    spec.loader.exec_module(mod)
    return mod

md = load('markdown_parser', 'engine/parser/markdown_parser.py')
tx = load('txt_parser', 'engine/parser/txt_parser.py')

# --- md tests ---
p = md.MarkdownParser()
raw = open('_test_md_parser.py').read()
msgs = p.parse(raw)
print(f"md: {len(msgs)} msgs")
for m in msgs:
    print(f"  [{m['role']}] {m['content'][:60].replace(chr(10),' ')}...")

assert 'system' in [m['role'] for m in msgs], "no system"
assert 'tool' in [m['role'] for m in msgs], "no tool"
assists = [m for m in msgs if m['role']=='assistant']
assert any('pluginIdentifier' in a['content'] for a in assists), "code block lost"

# --- txt tests ---
p2 = tx.TXTParser()

tagged = "<|im_system|>You are a bot.\n<|im_user|>Hello world.\n<|im_assistant|>Hi back."
r = p2.parse(tagged)
print(f"txt tagged: {[m['role'] for m in r]}")
assert [m['role'] for m in r] == ['system','assistant'], f"tagged fail: {[m['role'] for m in r]}"

bare = "System\nYou are a bot.\nuser\nHello.\nassistant\nHi."
r = p2.parse(bare)
print(f"txt bare: {[m['role'] for m in r]}")
assert [m['role'] for m in r] == ['system','user','assistant'], f"bare fail"

headered = "### System\nYou are a parser.\n### User\nHello.\n### Assistant\nHi."
r = p2.parse(headered)
print(f"txt header: {[m['role'] for m in r]}")
assert [m['role'] for m in r] == ['system','user','assistant'], f"header fail"

mixed = "### User\nThe word assistant on its own line.\n### Assistant\nReply."
r = p2.parse(mixed)
print(f"txt mixed: {[m['role'] for m in r]}")
assert [m['role'] for m in r] == ['user','assistant'], f"mixed fail: {[m['role'] for m in r]}"

empty = p2.parse("   \n\n  ")
assert empty[0]['role'] == 'user', "empty should fallback"

print("\nAll checks passed")
