import json

d = json.load(open('patch/080.json', encoding='utf-8'))
bad = 0
for i, o in enumerate(d['operations'], 1):
    t = o['target_file']
    if o['type'] == 'create':
        print(f'{i:2} CREATE   {t}')
        continue
    try:
        s = open(t, encoding='utf-8').read()
    except UnicodeDecodeError:
        s = open(t, encoding='cp1251').read()
    except Exception as e:
        print(f'{i:2} ERR      {t}: {e}')
        bad += 1
        continue
    s = s.replace('\r\n', '\n')
    f = o['find'].replace('\r\n', '\n')
    n = s.count(f)
    mark = 'OK  ' if n == 1 else ('MISS' if n == 0 else 'DUP ')
    if n != 1:
        bad += 1
    print(f'{i:2} {mark} x{n} {t} :: {f.splitlines()[0][:70]}')
print('---')
print('problem ops:', bad)