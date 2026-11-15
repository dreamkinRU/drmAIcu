import json
import os
import sys

def diagnose(patch_filename="patch/patch_008.json"):
    print("="*70)
    print("🔍 DRM AICU: ДИАГНОСТИКА ПАТЧЕЙ")
    print("="*70)
    
    # 1. Проверка существования файла патча
    if not os.path.exists(patch_filename):
        print(f"❌ ОШИБКА: Файл '{patch_filename}' не найден!")
        print("   Проверь, что ты сохранил его именно в папку patch/ под этим именем.")
        return
    
    print(f"✅ Файл патча найден: {patch_filename}")
    
    # 2. Проверка валидности JSON
    try:
        with open(patch_filename, 'r', encoding='utf-8') as f:
            patch_data = json.load(f)
        print("✅ JSON валиден и корректно отформатирован.")
    except json.JSONDecodeError as e:
        print(f"❌ ОШИБКА JSON: Файл поврежден или имеет неверный формат!")
        print(f"   Детали: {e}")
        return
    except Exception as e:
        print(f"❌ ОШИБКА ЧТЕНИЯ: {e}")
        return

    # 3. Проверка обязательных полей
    print("\n📋 Проверка полей внутри патча:")
    has_target = 'target_file' in patch_data
    has_type = 'type' in patch_data
    has_diff = 'diff' in patch_data
    has_full = 'full_file_content' in patch_data
    
    print(f"   [-] target_file:       {'✅' if has_target else '❌'} ({patch_data.get('target_file', 'ОТСУТСТВУЕТ')})")
    print(f"   [-] type:              {'✅' if has_type else '❌'} ({patch_data.get('type', 'ОТСУТСТВУЕТ')})")
    print(f"   [-] diff:              {'✅' if has_diff else '❌'} ({'Присутствует' if has_diff else 'ОТСУТСТВУЕТ'})")
    print(f"   [-] full_file_content: {'✅' if has_full else '❌'} ({'Присутствует' if has_full else 'ОТСУТСТВУЕТ'})")

    # 4. Проверка совместимости main.py
    print("\n⚙️ Проверка совместимости текущего main.py:")
    if not os.path.exists('main.py'):
        print("❌ ОШИБКА: Файл 'main.py' не найден в корневой папке!")
        return
    
    with open('main.py', 'r', encoding='utf-8') as f:
        main_content = f.read()
        
    has_unified_diff_support = 'unified_diff' in main_content and 'parse_unified_diff' in main_content
    
    if has_unified_diff_support:
        print("✅ main.py ПОДДЕРЖИВАЕТ формат unified_diff (версия 3.2.0+)")
    else:
        print("❌ main.py НЕ ПОДДЕРЖИВАЕТ формат unified_diff (старая версия)")
        print("   ⚠️ ЭТО И ЕСТЬ ГЛАВНАЯ ПРИЧИНА ОШИБКИ!")

    # 5. Итоговый вердикт
    print("\n" + "="*70)
    print("🎯 ИТОГОВЫЙ ВЕРДИКТ:")
    if not has_target:
        print("❌ В патче отсутствует поле 'target_file'. Исправь JSON.")
    elif has_type and patch_data.get('type') == 'unified_diff':
        if not has_unified_diff_support:
            print("❌ КРИТИЧЕСКАЯ ОШИБКА: Ты пытаешься применить unified_diff патч,")
            print("   но твой текущий main.py НЕ УМЕЕТ его читать (в нем нет функции parse_unified_diff).")
            print("   👉 РЕШЕНИЕ: Тебе нужно сначала успешно применить ПОЛНЫЙ патч (full_replace)")
            print("      для main.py (патч 007), который добавляет эту поддержку.")
            print("      Пока main.py не обновлен, все патчи должны быть в формате full_replace.")
        else:
            print("✅ Патч выглядит корректно, и main.py готов его принять.")
            print("   Если ошибка сохраняется, смотри вывод в консоли Python (там будет traceback).")
    else:
        print("✅ Патч в формате full_replace. main.py должен его принять.")
        if not has_full:
            print("   ⚠️ Но в патче отсутствует поле 'full_file_content', что вызовет ошибку!")
    
    print("="*70)

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "patch/patch_008.json"
    diagnose(target)