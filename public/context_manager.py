#!/usr/bin/env python3
# context_manager.py
# Версия 1.0
# Экспорт/импорт контекста для drmAIcu

import json
import os
import sys
import hashlib
from datetime import datetime
import zipfile

VERSION = "3.0.5"
PROJECT_NAME = "drmAIcu"
CONTEXT_FILE = "context_export.json"

# Файлы для экспорта
FILES_TO_EXPORT = [
    'main.py',
    'agent_engine.py',
    'settings.json',
    'launcher.bat',
    'context_manager.py'
]

# Директории для экспорта (только список файлов)
DIRS_TO_EXPORT = [
    'backups',
    'logs'
]


def calculate_file_hash(filepath):
    """Вычисляет SHA256 хеш файла"""
    if not os.path.exists(filepath):
        return None
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception as e:
        print(f"[ERROR] Cannot hash {filepath}: {e}")
        return None


def export_context():
    """Экспортирует контекст проекта в JSON"""
    print(f"[INFO] Экспорт контекста {PROJECT_NAME} v{VERSION}...")
    
    context = {
        "version": VERSION,
        "project": PROJECT_NAME,
        "timestamp": datetime.now().isoformat(),
        "files": {},
        "metadata": {
            "python_version": sys.version,
            "platform": sys.platform,
            "cwd": os.getcwd()
        }
    }
    
    # Экспорт файлов
    for filename in FILES_TO_EXPORT:
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    content = f.read()
                context["files"][filename] = {
                    "content": content,
                    "hash": calculate_file_hash(filename),
                    "size": len(content),
                    "modified": os.path.getmtime(filename)
                }
                print(f"[OK] {filename} ({len(content)} chars)")
            except Exception as e:
                print(f"[ERROR] {filename}: {e}")
        else:
            print(f"[WARN] {filename} not found")
    
    # Экспорт директорий (только список файлов)
    for dirname in DIRS_TO_EXPORT:
        if os.path.exists(dirname):
            context["metadata"][f"{dirname}_files"] = []
            for root, dirs, files in os.walk(dirname):
                for file in files:
                    filepath = os.path.join(root, file)
                    rel_path = os.path.relpath(filepath, '.')
                    context["metadata"][f"{dirname}_files"].append({
                        "path": rel_path,
                        "size": os.path.getsize(filepath),
                        "modified": os.path.getmtime(filepath)
                    })
            print(f"[OK] {dirname} ({len(context['metadata'][f'{dirname}_files'])} files)")
    
    # Сохранение JSON
    try:
        with open(CONTEXT_FILE, 'w', encoding='utf-8') as f:
            json.dump(context, f, indent=2, ensure_ascii=False)
        print(f"\n[SUCCESS] Контекст экспортирован в {CONTEXT_FILE}")
        print(f"[INFO] Размер: {os.path.getsize(CONTEXT_FILE)} bytes")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save context: {e}")
        return False


def export_context_zip():
    """Экспортирует контекст в ZIP архив"""
    print(f"[INFO] Экспорт контекста в ZIP...")
    
    # Сначала создаём JSON
    if not export_context():
        return False
    
    # Создаём ZIP
    context_archive = "context_export.zip"
    try:
        with zipfile.ZipFile(context_archive, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(CONTEXT_FILE)
            
            # Добавляем файлы
            for filename in FILES_TO_EXPORT:
                if os.path.exists(filename):
                    zipf.write(filename)
            
            # Добавляем директории
            for dirname in DIRS_TO_EXPORT:
                if os.path.exists(dirname):
                    for root, dirs, files in os.walk(dirname):
                        for file in files:
                            filepath = os.path.join(root, file)
                            arcname = os.path.relpath(filepath, '.')
                            zipf.write(filepath, arcname)
        
        print(f"\n[SUCCESS] Архив создан: {context_archive}")
        print(f"[INFO] Размер: {os.path.getsize(context_archive)} bytes")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to create ZIP: {e}")
        return False


def import_context(json_path=None):
    """Импортирует контекст из JSON"""
    if json_path is None:
        json_path = CONTEXT_FILE
    
    if not os.path.exists(json_path):
        print(f"[ERROR] Файл {json_path} не найден")
        return False
    
    print(f"[INFO] Импорт контекста из {json_path}...")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            context = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load context: {e}")
        return False
    
    # Проверка версии
    if context.get("version") != VERSION:
        print(f"[WARN] Версия контекста ({context.get('version')}) != текущая ({VERSION})")
        response = input("Продолжить? (y/n): ")
        if response.lower() != 'y':
            return False
    
    # Создание бэкапа перед импортом
    backup_dir = f"backup_before_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    print(f"[INFO] Создание бэкапа в {backup_dir}...")
    
    for filename in FILES_TO_EXPORT:
        if os.path.exists(filename):
            backup_path = os.path.join(backup_dir, filename)
            try:
                with open(filename, 'r', encoding='utf-8') as src:
                    content = src.read()
                with open(backup_path, 'w', encoding='utf-8') as dst:
                    dst.write(content)
                print(f"[OK] Backup: {filename}")
            except Exception as e:
                print(f"[ERROR] Backup {filename}: {e}")
    
    # Импорт файлов
    files_data = context.get("files", {})
    for filename, file_info in files_data.items():
        try:
            content = file_info.get("content", "")
            
            # Проверка хеша если есть
            expected_hash = file_info.get("hash")
            if expected_hash:
                actual_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
                if actual_hash != expected_hash:
                    print(f"[WARN] Hash mismatch for {filename}")
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"[OK] Restored: {filename} ({len(content)} chars)")
        except Exception as e:
            print(f"[ERROR] Restore {filename}: {e}")
    
    print(f"\n[SUCCESS] Контекст импортирован")
    print(f"[INFO] Бэкап сохранён в: {backup_dir}")
    return True


def show_context_info(json_path=None):
    """Показывает информацию о контексте"""
    if json_path is None:
        json_path = CONTEXT_FILE
    
    if not os.path.exists(json_path):
        print(f"[ERROR] Файл {json_path} не найден")
        return
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            context = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load context: {e}")
        return
    
    print(f"\n{'='*60}")
    print(f"Контекст: {context.get('project')} v{context.get('version')}")
    print(f"Время экспорта: {context.get('timestamp')}")
    print(f"{'='*60}")
    
    files = context.get("files", {})
    print(f"\nФайлы ({len(files)}):")
    for filename, info in files.items():
        size = info.get("size", 0)
        hash_val = info.get("hash", "N/A")[:16] + "..." if info.get("hash") else "N/A"
        print(f"  - {filename}: {size} chars, hash: {hash_val}")
    
    metadata = context.get("metadata", {})
    print(f"\nМетаданные:")
    print(f"  Python: {metadata.get('python_version', 'N/A').split()[0]}")
    print(f"  Platform: {metadata.get('platform', 'N/A')}")
    print(f"  CWD: {metadata.get('cwd', 'N/A')}")
    
    for dirname in DIRS_TO_EXPORT:
        dir_files = metadata.get(f"{dirname}_files", [])
        if dir_files:
            print(f"  {dirname}: {len(dir_files)} files")
    
    print(f"{'='*60}\n")


def main():
    if len(sys.argv) < 2:
        print(f"""
{PROJECT_NAME} Context Manager v1.0

Использование:
  python context_manager.py export          - Экспорт контекста в JSON
  python context_manager.py export-zip      - Экспорт контекста в ZIP
  python context_manager.py import [file]   - Импорт контекста из JSON
  python context_manager.py info [file]     - Показать информацию о контексте

Примеры:
  python context_manager.py export
  python context_manager.py import context_export.json
  python context_manager.py info
""")
        return
    
    command = sys.argv[1].lower()
    
    if command == "export":
        export_context()
    elif command == "export-zip":
        export_context_zip()
    elif command == "import":
        json_path = sys.argv[2] if len(sys.argv) > 2 else None
        import_context(json_path)
    elif command == "info":
        json_path = sys.argv[2] if len(sys.argv) > 2 else None
        show_context_info(json_path)
    else:
        print(f"[ERROR] Неизвестная команда: {command}")


if __name__ == "__main__":
    main()
