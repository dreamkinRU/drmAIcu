import os
import re
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    print("=== Настройка аварийного отката (Реальные файлы) ===")
    
    # 1. Создаём rollback.html
    rollback_html = os.path.join(BASE_DIR, 'rollback.html')
    with open(rollback_html, 'w', encoding='utf-8') as f:
        f.write("""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>🚨 Аварийный откат - drmAIcu</title>
    <style>
        body { font-family: sans-serif; background: #1a1a2e; color: #fff; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
        .container { max-width: 600px; background: rgba(255,255,255,0.05); border: 2px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 40px; text-align: center; }
        h1 { color: #ff6b6b; }
        .btn { display: block; width: 100%; padding: 15px; margin: 10px 0; font-size: 1.1em; font-weight: bold; border: none; border-radius: 10px; cursor: pointer; text-decoration: none; }
        .btn-rollback { background: #ff6b6b; color: white; }
        .btn-back { background: rgba(255,255,255,0.1); color: white; border: 1px solid rgba(255,255,255,0.2); }
        .result { margin-top: 20px; padding: 15px; border-radius: 10px; display: none; }
        .success { background: rgba(76,175,80,0.2); color: #4caf50; border: 1px solid #4caf50; }
        .error { background: rgba(255,107,107,0.2); color: #ff6b6b; border: 1px solid #ff6b6b; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚨 Аварийный откат</h1>
        <p>Используйте эту страницу, если панель управления не загружается из-за ошибки патча.</p>
        <button class="btn btn-rollback" id="btn" onclick="rollback()">↩️ Откатить последний патч</button>
        <a href="/" class="btn btn-back">🏠 Вернуться на главную</a>
        <div class="result" id="result"></div>
    </div>
    <script>
        async function rollback() {
            const btn = document.getElementById('btn');
            const res = document.getElementById('result');
            btn.disabled = true; btn.textContent = '⏳ Откатываю...'; res.style.display = 'none';
            try {
                const response = await fetch('/api/patches/rollback', { method: 'POST' });
                const data = await response.json();
                if (data.success) {
                    res.className = 'result success'; res.style.display = 'block';
                    res.innerHTML = '<strong>✅ Успешно!</strong><br>' + (data.message || 'Патч откатан.') + '<br>Перезагрузите страницу.';
                    btn.textContent = '✅ Готово';
                } else { throw new Error(data.error || 'Ошибка'); }
            } catch (e) {
                res.className = 'result error'; res.style.display = 'block';
                res.innerHTML = '<strong>❌ Ошибка:</strong> ' + e.message + '<br>Убедитесь, что ядро (порт 8080) запущено.';
                btn.disabled = false; btn.textContent = '↩️ Откатить последний патч';
            }
        }
    </script>
</body>
</html>""")
    print("✅ Создан: rollback.html")

    # 2. Создаём vite-rollback-plugin.js
    plugin_js = os.path.join(BASE_DIR, 'vite-rollback-plugin.js')
    with open(plugin_js, 'w', encoding='utf-8') as f:
        f.write("""export default function rollbackPlugin() {
  return {
    name: 'vite-rollback-plugin',
    enforce: 'pre',
    transformIndexHtml(html) {
      const script = `
<script>
(function() {
  function inject(overlay) {
    if (overlay.querySelector('.rollback-banner')) return;
    const banner = document.createElement('div');
    banner.className = 'rollback-banner';
    banner.innerHTML = '<div style="background:#ff6b6b;color:#fff;padding:15px;font-family:sans-serif;font-size:14px;border-bottom:3px solid #ff4757;">' +
      '<strong>🚨 Фронтенд сломан?</strong> Откройте <a href="http://127.0.0.1:8080/rollback" target="_blank" style="color:#fff;text-decoration:underline;font-weight:bold;background:rgba(255,255,255,0.2);padding:2px 6px;border-radius:4px;">http://127.0.0.1:8080/rollback</a> и нажмите «Откатить»' +
      ' <a href="http://127.0.0.1:8080/rollback" target="_blank" style="display:inline-block;background:#fff;color:#ff6b6b;padding:5px 10px;border-radius:6px;text-decoration:none;font-weight:bold;margin-left:10px;">↩️ Открыть откат</a></div>';
    if (overlay.shadowRoot) overlay.shadowRoot.insertBefore(banner, overlay.shadowRoot.firstChild);
    else overlay.insertBefore(banner, overlay.firstChild);
  }
  const obs = new MutationObserver(m => m.forEach(mut => mut.addedNodes.forEach(n => {
    if (n.tagName === 'VITE-ERROR-OVERLAY' || (n.classList && n.classList.contains('vite-error-overlay'))) inject(n);
  })));
  obs.observe(document.body, { childList: true, subtree: true });
  window.addEventListener('load', () => { const o = document.querySelector('vite-error-overlay, .vite-error-overlay'); if (o) inject(o); });
})();
</script>`;
      return html.replace('</head>', script + '</head>');
    }
  };
}
""")
    print("✅ Создан: vite-rollback-plugin.js")

    # 3. Модифицируем main.py
    main_py = os.path.join(BASE_DIR, 'main.py')
    with open(main_py, 'r', encoding='utf-8') as f:
        main_content = f.read()

    # Добавляем импорт FileResponse, если его нет
    if 'FileResponse' not in main_content:
        if 'from fastapi.responses import' in main_content:
            main_content = main_content.replace('from fastapi.responses import', 'from fastapi.responses import FileResponse, ')
        else:
            main_content = main_content.replace('from fastapi import', 'from fastapi import FileResponse, ', 1)
        print("✅ Добавлен импорт FileResponse в main.py")

    # Вставляем эндпоинт /rollback перед первым @app.get или @app.post
    match = re.search(r'^(@app\.(?:get|post|put|delete)\([^\n]*\n)', main_content, re.MULTILINE)
    if match:
        anchor = match.group(1)
        new_endpoint = (
            "@app.get('/rollback')\n"
            "def rollback_page():\n"
            "    \"\"\"Аварийная страница отката\"\"\"\n"
            "    rollback_html = os.path.join(BASE, 'rollback.html')\n"
            "    if os.path.exists(rollback_html):\n"
            "        return FileResponse(rollback_html)\n"
            "    return {'error': 'rollback.html not found'}\n\n\n"
        )
        main_content = main_content.replace(anchor, new_endpoint + anchor, 1)
        print("✅ Добавлен эндпоинт /rollback в main.py")
        
        with open(main_py, 'w', encoding='utf-8') as f:
            f.write(main_content)
    else:
        print("⚠️ Не удалось найти @app.get/post в main.py. Проверьте файл вручную.")

    # 4. Модифицируем vite.config.js
    vite_js = os.path.join(BASE_DIR, 'vite.config.js')
    with open(vite_js, 'r', encoding='utf-8') as f:
        vite_content = f.read()

    if 'rollbackPlugin' not in vite_content:
        # Добавляем импорт
        vite_content = vite_content.replace(
            "import react from '@vitejs/plugin-react'",
            "import react from '@vitejs/plugin-react'\nimport rollbackPlugin from './vite-rollback-plugin.js'"
        )
        # Добавляем в plugins
        vite_content = vite_content.replace(
            "plugins: [react()],",
            "plugins: [react(), rollbackPlugin()],"
        )
        # Если там нет запятой после react()
        vite_content = vite_content.replace(
            "plugins: [react()]",
            "plugins: [react(), rollbackPlugin()]"
        )
        
        with open(vite_js, 'w', encoding='utf-8') as f:
            f.write(vite_content)
        print("✅ Модифицирован vite.config.js")

    print("\n🎉 ГОТОВО! Все реальные файлы обновлены.")
    print("Теперь перезапустите ядро (🔄 в панели) и запустите `npm run dev`.")

if __name__ == '__main__':
    main()