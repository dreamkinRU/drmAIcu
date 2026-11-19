import json, os

d = json.load(open('patch/080.json', encoding='utf-8'))

def read(p):
    return open(p, encoding='utf-8').read().replace('\r\n', '\n')

keep, skipped = [], []
for i, o in enumerate(d['operations'], 1):
    t = o['target_file']
    label = f"{i} {t} :: {o.get('find', 'CREATE').splitlines()[0][:55]}"
    if o['type'] == 'create':
        if os.path.exists(t):
            skipped.append(label + '  [already exists]')
        else:
            keep.append(o)
        continue
    src = read(t)
    f = o['find'].replace('\r\n', '\n')
    r = o['replace'].replace('\r\n', '\n')
    if r in src:
        skipped.append(label + '  [already applied]')
    elif src.count(f) == 1:
        keep.append(o)
    else:
        skipped.append(label + f"  [find x{src.count(f)} - MANUAL CHECK]")

d['operations'] = keep
d['patch_id'] = '080c'
d['description'] = 'Engine fix: remaining operations'
json.dump(d, open('patch/080c.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('keep:', len(keep))
for s in skipped:
    print('SKIP', s)