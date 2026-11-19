import os, shutil, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(os.path.dirname(ROOT), 'drmAIcu_archive',
                    datetime.now().strftime('%Y%m%d_%H%M%S'))
APPLY = '--apply' in sys.argv

DIRS = ['backups', 'patch/archive', 'backend']
FILES = [
    # мёртвые API-дублёры
    'api.py', 'backend/api.py', 'backend/requirements.txt',
    # мёртвый фронтенд
    'src/services/api.ts', 'src/pages/Dashboard.tsx',
    # fixer-скрипты
    'apply_smart_cleanup.py', 'upgrade_cleanup_backend.py', 'upgrade_cleanup_ui.py',
    'fix_cleanup_ui_exact.py', 'fix_main_robustness.py', 'fix_apptsx.py',
    'fix_ui_patch_fields.py', 'add_test_apply.py', 'diagnose.py',
    # мусор корня
    'dev.cmd', 'report.txt', 'diag.bat', '!patch_system.txt',
    # старые версии в public
    'public/App.tsx', 'public/agent_engine.py', 'public/context_manager.py',
    'public/main.py', 'public/main_v3.0.4_ru.py', 'public/main_v3.0.4_fixed.py',
    'public/main_v3.0.7.py', 'public/main_v3.0.8.py', 'public/main_v3.1.0.py',
    'public/USER_GUIDE_v3.2.0.md', 'public/NEW_FEATURES_v3.2.0.md',
    'public/INSTALL.md', 'public/INTERFACE_UPDATE_v3.2.0.md',
    'public/launcher.bat', 'public/settings.json',
]

def size(p):
    if os.path.isfile(p):
        return os.path.getsize(p)
    return sum(os.path.getsize(os.path.join(r, f))
               for r, _, fs in os.walk(p) for f in fs)

total = n = 0
for rel in DIRS + FILES:
    src = os.path.join(ROOT, rel.replace('/', os.sep))
    if not os.path.exists(src):
        print('skip:', rel)
        continue
    s = size(src); total += s; n += 1
    print(f'{"MOVE" if APPLY else "PLAN"} {rel:42} {s/1024:9.1f} KB')
    if APPLY:
        dst = os.path.join(DEST, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)

print('---')
print(f'объектов: {n}, объём: {total/1048576:.2f} MB')
print('архив:', DEST if APPLY else '(dry-run)')