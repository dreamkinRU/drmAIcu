import json

p = 'patch/080.json'
d = json.load(open(p, encoding='utf-8'))
ops = d['operations']

# 1. check_ts: путь от main.py, а не от BASE
o = ops[3]
assert 'def check_ts(name, code):' in o['replace'], 'op4 is not the helpers block'
a = "    script = os.path.join(BASE, 'tools', 'tscheck.cjs')"
b = ("    root = os.path.dirname(os.path.abspath(__file__))\n"
     "    script = os.path.join(root, 'tools', 'tscheck.cjs')")
assert o['replace'].count(a) == 1
o['replace'] = o['replace'].replace(a, b).replace(
    'capture_output=True, timeout=30, cwd=BASE)',
    'capture_output=True, timeout=30, cwd=root)')

# 2. дедупликация записей по файлу
dedup = {
    "type": "search_and_replace",
    "target_file": "main.py",
    "find": "    planned = []\n    for o in ops:\n        dir_name = os.path.dirname(o['path'])",
    "replace": "    final = {}\n    for o in ops:\n        final[os.path.normcase(o['path'])] = o\n    ops = list(final.values())\n    planned = []\n    for o in ops:\n        dir_name = os.path.dirname(o['path'])"
}
if not any(x.get('find') == dedup['find'] for x in ops):
    ops.append(dedup)

d['description'] += ' + check_ts path fix + per-file dedup'
with open(p, 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
print('ops now:', len(ops))