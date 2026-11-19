export function getCategoryColor(cat: string): string {
  const colors: Record<string, string> = {
    critical: 'bg-red-500/20 text-red-400 border-red-500/30',
    code: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    config: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    docs: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
    backup: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    archive: 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
    trash: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    logs: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
    scripts: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    web: 'bg-pink-500/20 text-pink-400 border-pink-500/30',
    other: 'bg-gray-700/20 text-gray-400 border-gray-600',
    error: 'bg-red-500/20 text-red-400 border-red-500/30',
  };
  return colors[cat] || colors.other;
}

export function getCategoryLabel(cat: string): string {
  const labels: Record<string, string> = {
    critical: '🔴 Критичный',
    code: '💻 Код',
    config: '⚙️ Конфиг',
    docs: '📝 Документация',
    backup: '💾 Бэкап',
    archive: '📦 Архив',
    trash: '🗑 Мусор',
    logs: '📃 Логи',
    scripts: '⚙️ Скрипт',
    web: '🌐 Web',
    other: '📄 Другое',
    error: '❌ Ошибка',
  };
  return labels[cat] || cat;
}
