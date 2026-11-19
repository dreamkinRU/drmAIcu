import ast, shutil
from datetime import datetime

PATH = 'main.py'
bak = PATH + '_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.pre_op7.bak'
shutil.copy2(PATH, bak)
print('Backup:', bak)

src = open(PATH, encoding='utf-8').read()

old = ("        save_manifest(man)\n"
       "        log('Patch ' + pid + ' applied atomically to ' + str(len(planned)) + ' file(s)', 'SUCCESS')")
new = ("        if len(man['applied']) > 100:\n"
       "            man['applied'] = man['applied'][-100:]\n"
       "        if len(man['history']) > 500:\n"
       "            man['history'] = man['history'][-500:]\n"
       "        save_manifest(man)\n"
       "        log('Patch ' + pid + ' applied atomically to ' + str(len(planned)) + ' file(s)', 'SUCCESS')")

n = src.count(old)
if n != 1:
    print('ERROR: found %d occurrences (expected 1)' % n)
    raise SystemExit(1)

src = src.replace(old, new, 1)
try:
    ast.parse(src)
    print('OK: ast.parse passed')
except SyntaxError as e:
    print('ERROR: syntax error:', e)
    raise SystemExit(1)

open(PATH, 'w', encoding='utf-8').write(src)
print('DONE: manifest rotation added')