# make082.py — one-off bootstrap: applies patch 082 directly to main.py
import ast, os, shutil
from datetime import datetime

PATH = 'main.py'

raw = open(PATH, encoding='utf-8').read()
had_crlf = '\r\n' in raw
src = raw.replace('\r\n', '\n')

ts = datetime.now().strftime('%Y%m%d_%H%M%S')
bak = PATH + '_' + ts + '.pre082.bak'
shutil.copy2(PATH, bak)
print('Backup:', bak)

def must_replace(text, find, replace, label):
    n = text.count(find)
    if n != 1:
        print('FAIL [%s]: expected 1 occurrence, found %d' % (label, n))
        raise SystemExit(1)
    print('OK   [%s]' % label)
    return text.replace(find, replace, 1)

def extract_function(text, name):
    lines = text.split('\n')
    start = None
    for i, l in enumerate(lines):
        if l.startswith('def ' + name + '('):
            start = i
            break
    if start is None:
        return None
    j = start + 1
    while j < len(lines):
        if lines[j].strip() and not lines[j][0].isspace():
            break
        j += 1
    end = j
    while end > start and not lines[end-1].strip():
        end -= 1
    return '\n'.join(lines[start:end])

# Op1: globals
a1 = "BACKUP_DIR = os.path.join(BASE, 'backups')"
src = must_replace(src, a1, a1 + "\nMAIN_HASH = None\nPATCH_LOCK = threading.Lock()", 'op1 globals')

# Op2: sha_file
a2 = "def sha(text):\n    return hashlib.sha256(text.encode('utf-8')).hexdigest()"
sha_file_fn = ("def sha_file(path):\n"
    "    h = hashlib.sha256()\n"
    "    with open(path, 'rb') as f:\n"
    "        for chunk in iter(lambda: f.read(65536), b''):\n"
    "            h.update(chunk)\n"
    "    return h.hexdigest()")
src = must_replace(src, a2, a2 + "\n\n\n" + sha_file_fn, 'op2 sha_file')

# Op3: backup() single + rotation
old_backup = extract_function(src, 'backup')
if old_backup is None:
    print('FAIL [op3 backup]: not found'); raise SystemExit(1)
new_backup = ("def backup(path):\n"
    "    out = []\n"
    "    if not os.path.exists(path):\n"
    "        return out\n"
    "    name = os.path.relpath(path, BASE).replace(os.sep, '__').replace(':', '')\n"
    "    ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')\n"
    "    dst = os.path.join(BACKUP_DIR, name + '_' + ts + '.bak')\n"
    "    try:\n"
    "        shutil.copy2(path, dst)\n"
    "        out.append(dst)\n"
    "    except Exception:\n"
    "        pass\n"
    "    prefix = name + '_'\n"
    "    try:\n"
    "        existing = [f for f in os.listdir(BACKUP_DIR) if f.startswith(prefix) and f.endswith('.bak')]\n"
    "        if len(existing) > 10:\n"
    "            existing.sort()\n"
    "            for old in existing[:-10]:\n"
    "                try:\n"
    "                    os.remove(os.path.join(BACKUP_DIR, old))\n"
    "                except Exception:\n"
    "                    pass\n"
    "    except Exception:\n"
    "        pass\n"
    "    return out")
src = must_replace(src, old_backup, new_backup, 'op3 backup')

# Op4: search_and_replace idempotency
a4 = "    if find_n not in content_n:"
r4 = ("    if replace_n in content_n and find_n not in content_n:\n"
      "        return content\n"
      "    if find_n not in content_n:")
src = must_replace(src, a4, r4, 'op4 idempotency')

# Op5: lock + stale-code detection
a5 = ("def apply_patch(raw):\n"
      "    data = resolve(raw)\n"
      "    pid = str(data.get('patch_id', 'unknown'))\n"
      "    ops = compute_ops(data)")
r5 = ("def apply_patch(raw):\n"
      "    if not PATCH_LOCK.acquire(blocking=False):\n"
      "        return {'success': False, 'error': 'Another patch is already being applied. Please wait.'}\n"
      "    try:\n"
      "        return _apply_patch_inner(raw)\n"
      "    finally:\n"
      "        PATCH_LOCK.release()\n"
      "\n"
      "\n"
      "def _apply_patch_inner(raw):\n"
      "    global MAIN_HASH\n"
      "    current_hash = sha_file(os.path.join(BASE, 'main.py'))\n"
      "    if MAIN_HASH and current_hash != MAIN_HASH:\n"
      "        log('Code changed on disk - refusing to apply patch', 'ERROR')\n"
      "        return {'success': False, 'error': 'Code changed on disk. Please restart the system.'}\n"
      "    data = resolve(raw)\n"
      "    pid = str(data.get('patch_id', 'unknown'))\n"
      "    ops = compute_ops(data)")
src = must_replace(src, a5, r5, 'op5 lock+stale')

# Op6: expected_sha in planning block
a6 = ("        backs = backup(o['path'])\n"
      "        data = to_bytes(o['new'], file_newline(o['path']))")
r6 = ("        backs = backup(o['path'])\n"
      "        expected_sha = o.get('expected_sha')\n"
      "        if expected_sha and os.path.exists(o['path']):\n"
      "            actual = sha_file(o['path'])\n"
      "            if actual != expected_sha:\n"
      "                return {'success': False, 'error': 'File modified: ' + o['target_file'] + '. Refresh the page.'}\n"
      "        data = to_bytes(o['new'], file_newline(o['path']))")
src = must_replace(src, a6, r6, 'op6 expected_sha')

# Op7: manifest rotation
a7 = ("    save_manifest(man)\n"
      "    log('Patch ' + pid + ' applied atomically to ' + str(len(planned)) + ' file(s)', 'SUCCESS')")
r7 = ("    if len(man['applied']) > 100:\n"
      "        man['applied'] = man['applied'][-100:]\n"
      "    if len(man['history']) > 500:\n"
      "        man['history'] = man['history'][-500:]\n"
      "    save_manifest(man)\n"
      "    log('Patch ' + pid + ' applied atomically to ' + str(len(planned)) + ' file(s)', 'SUCCESS')")
src = must_replace(src, a7, r7, 'op7 manifest rotation')

# Op8: MAIN_HASH init at startup
a8 = ("    log('Starting drmAIcu Core v3.5.0 MULTI-ATOMIC...')\n"
      "    get_engine()")
r8 = ("    log('Starting drmAIcu Core v3.5.0 MULTI-ATOMIC...')\n"
      "    MAIN_HASH = sha_file(os.path.join(BASE, 'main.py'))\n"
      "    log('Code hash: ' + MAIN_HASH[:16] + '...', 'INFO')\n"
      "    get_engine()")
src = must_replace(src, a8, r8, 'op8 MAIN_HASH init')

try:
    ast.parse(src)
    print('OK   [ast.parse]')
except SyntaxError as e:
    print('FAIL [ast.parse]:', e); raise SystemExit(1)

if had_crlf:
    src = src.replace('\n', '\r\n')
open(PATH, 'w', encoding='utf-8', newline='').write(src)
print('DONE: main.py updated. Backup at', bak)