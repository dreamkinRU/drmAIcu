import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import rollbackPlugin from './vite-rollback-plugin.js'
import tailwindcss from '@tailwindcss/vite'

// ANTI-RELOAD-FIX: бэкенд в рантайме пишет служебные файлы в корень проекта
// (data/plugins/ — журнал активности при каждом exec capability, settings.json,
// agents.json, pipelines.json, patch/, backups/ и т.п.). Без игноров Vite
// считал каждое такое изменение правкой исходников и выполнял ПОЛНУЮ
// перезагрузку страницы — это «периодические обновления раз в 10–30 секунд»
// и цикл перезагрузок при работе с плагинами (exec → запись журнала → reload).
const runtimeIgnores = [
  '**/.git/**',
  '**/node_modules/**',
  '**/dist/**',
  '**/__pycache__/**',
  '**/data/**',              // данные плагинов: registry/permissions/state/journal/activity
  '**/logs/**',
  '**/patch/**',             // патчи и архив патчей
  '**/backups/**',
  '**/project_archive/**',
  '**/settings.json',        // конфиг бэкенда (пишется при сохранении настроек провайдеров)
  '**/agents.json',
  '**/pipelines.json',
  '**/patch_manifest.json',
  '**/patch_journal.json',
  '**/.project-history.json',
  '**/.project-important.json',
  '**/restart.flag',
  '**/*.log',
]

export default defineConfig({
  plugins: [react(), tailwindcss(), rollbackPlugin()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    watch: {
      ignored: runtimeIgnores,
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      }
    }
  }
})
