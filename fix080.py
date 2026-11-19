import json

path = 'patch/080.json'
d = json.load(open(path, encoding='utf-8'))
o = d['operations'][14]
assert "tmp = pl['path'] + '.tmp'" in o['find'], 'op 15 is not the write loop'

for k in ('find', 'replace'):
    o[k] = '\n'.join(l[4:] if l.startswith('    ') else l for l in o[k].split('\n'))

with open(path, 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)

src = open('main.py', encoding='utf-8').read().replace('\r\n', '\n')
print('op15 find count:', src.count(o['find'].replace('\r\n', '\n')))