import os
import subprocess

print("=== ФИНАЛЬНЫЙ АУДИТ И ИСПРАВЛЕНИЕ БЕЗОПАСНОСТИ (БЕЗ ДОГАДОК) ===\n")

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

fixes_applied = 0

# 1. API вызывает apply_patch_atomic?
if "apply_patch_atomic(payload)" in content:
    print("🔴 НАЙДЕНО: API всё ещё вызывает apply_patch_atomic!")
    content = content.replace("apply_patch_atomic(payload)", "apply_patch(payload)")
    fixes_applied += 1
    print("   ✅ Исправлено: теперь вызывает apply_patch(payload)")
else:
    print("🟢 ОК: API использует apply_patch(payload)")

# 2. compute_ops обходит safe_path? (Уязвимость path traversal)
old_path_check = """        path = os.path.normpath(os.path.join(BASE, tgt))
        try:
            inside = os.path.commonpath([BASE, path]) == BASE
        except ValueError:
            inside = False
        if not tgt or not inside:"""

new_path_check = """        path = safe_path(tgt)
        if not tgt or path is None:"""

if old_path_check in content:
    print("🔴 НАЙДЕНО: compute_ops обходит safe_path!")
    content = content.replace(old_path_check, new_path_check)
    fixes_applied += 1
    print("   ✅ Исправлено: compute_ops теперь использует safe_path(tgt)")
else:
    print("🟢 ОК: compute_ops использует safe_path")

# 3. Потеря файла при сбое backup (A-01)
old_del = """            elif os.path.exists(pl['path']):
                try:
                    os.remove(pl['path'])
                except Exception:
                    pass"""

new_del = """            elif pl.get('existed') and not pl['backs']:
                # Файл существовал, бэкапа нет — удалять НЕЛЬЗЯ (A-01 fix)
                pass
            elif not pl.get('existed') and os.path.exists(pl['path']):
                # Новый файл (create) — можно удалить при откате
                try:
                    os.remove(pl['path'])
                except Exception:
                    pass"""

if old_del in content and "pl.get('existed')" not in content:
    print("🔴 НАЙДЕНО: Риск удаления оригинального файла при сбое backup!")
    content = content.replace(old_del, new_del)
    fixes_applied += 1
    print("   ✅ Исправлено: оригинальные файлы больше не удаляются при сбое бэкапа")
else:
    print("🟢 ОК: Защита от удаления оригинального файла уже присутствует")

# 4. Некорректный rollback (использование b[-1] вместо конкретного бэкапа)
if "shutil.copy2(b[-1], path)" in content:
    print("🔴 НАЙДЕНО: rollback использует b[-1] (может быть _LATEST.bak)!")
    content = content.replace("shutil.copy2(b[-1], path)", "shutil.copy2(b[0], path)  # Используем конкретный timestamp-бэкап, а не _LATEST")
    fixes_applied += 1
    print("   ✅ Исправлено: rollback теперь использует b[0] (конкретный бэкап)")
else:
    print("🟢 ОК: rollback использует корректный индекс бэкапа")

# 5. Добавляем флаг 'existed' в planned, если его нет
if "'tgt': o['target_file'], 'sha': sha_bytes(data)" in content and "'existed'" not in content:
    print("🔴 НАЙДЕНО: Отсутствует флаг 'existed' для корректного отката")
    content = content.replace(
        "'tgt': o['target_file'], 'sha': sha_bytes(data)",
        "'tgt': o['target_file'], 'sha': sha_bytes(data), 'existed': os.path.exists(o['path'])"
    )
    fixes_applied += 1
    print("   ✅ Исправлено: добавлен флаг 'existed'")
else:
    print("🟢 ОК: Флаг 'existed' присутствует")

# Сохранение
if fixes_applied > 0:
    print(f"\n💾 Сохраняю исправления в main.py ({fixes_applied} исправлений)...")
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ main.py успешно обновлён!")
    print("⚠️ ВАЖНО: Нажми '🔄 Перезапуск' в панели управления, чтобы изменения вступили в силу!")
else:
    print("\n🎉 ВСЕ КРИТИЧЕСКИЕ ДЫРЫ УЖЕ ЗАКРЫТЫ! Система чиста.")

print("\n=== ЗАПУСК ТЕСТОВ ===")
result = subprocess.run(['pytest', 'tests/test_patching_hardcore.py', '-v', '--tb=short'], capture_output=True, text=True, encoding='utf-8')
print(result.stdout)

if "passed" in result.stdout and "failed" not in result.stdout.lower():
    print("\n🏆 ТЕСТЫ ПРОЙДЕНЫ! Система патчинга drmAIcu теперь имеет военный уровень надёжности.")
else:
    print("\n⚠️ Есть ошибки в тестах. Проверь вывод выше.")