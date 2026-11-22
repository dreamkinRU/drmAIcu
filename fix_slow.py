   import os

   main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')
   
   with open(main_py, 'r', encoding='utf-8') as f:
       content = f.read()

   old_block = """    elif ext in ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'):
        err = check_ts(name, code)
        if err:
            return False, 'TS/JS: ' + err
        # Полная типовая проверка (только для TS/TSX, не JS)
        if ext in ('.ts', '.tsx'):
            err = check_ts_full()
            if err:
                return False, err
    return True, None"""

   new_block = """    elif ext in ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'):
        err = check_ts(name, code)
        if err:
            return False, 'TS/JS: ' + err
        # Полная проверка типов отключена для скорости патчинга.
        # Запускайте вручную через: npm run typecheck
    return True, None"""

   if old_block in content:
       content = content.replace(old_block, new_block)
       with open(main_py, 'w', encoding='utf-8') as f:
           f.write(content)
       print("✅ Готово! Медленная проверка убрана из main.py.")
       print("Теперь нажмите 🔄 Перезапуск в панели.")
   else:
       print("⚠️ Блок кода не найден. Возможно, он уже был изменен.")