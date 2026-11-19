import StatusBadge from '../ui/StatusBadge';
import { Agent, Provider, OllamaModel } from '../../types';
import { PatchStats } from '../../services/api';

interface PanelTabProps {
  agents: Agent[];
  providers: Provider[];
  installedModels: OllamaModel[];
  patchStats: PatchStats;
}

export default function PanelTab({ agents, providers, installedModels, patchStats }: PanelTabProps) {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Панель управления</h2>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
          <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><span>🤖</span> Агенты</h3>
          <div className="space-y-2">
            {agents.map(a => (
              <div key={a.id} className="flex justify-between items-center text-sm">
                <span className={a.enabled ? 'text-emerald-400' : 'text-gray-500'}>{a.name}</span>
                <StatusBadge status={a.status} />
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
          <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><span>🌐</span> Провайдеры</h3>
          <div className="space-y-2">
            {providers.map(p => (
              <div key={p.name} className="flex justify-between items-center text-sm">
                <span className={p.enabled ? 'text-white' : 'text-gray-500'}>{p.name}</span>
                <StatusBadge status={p.status} />
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
          <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><span>🧠</span> Модели Ollama</h3>
          <div className="space-y-2">
            {installedModels.length === 0 ? (
              <p className="text-gray-500 text-sm">Нет моделей</p>
            ) : (
              installedModels.map((m, idx) => (
                <div key={idx} className="flex justify-between items-center text-sm">
                  <span className="font-mono text-emerald-400">{m.name}</span>
                  <span className="text-gray-500">{m.size_gb} GB</span>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
          <h3 className="text-lg font-bold mb-4 flex items-center gap-2"><span>🔄</span> Патчи</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-gray-400">Всего:</span><span className="font-bold text-white">{patchStats.total || 0}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Применено:</span><span className="font-bold text-emerald-400">{patchStats.applied || 0}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Ожидают:</span><span className="font-bold text-yellow-400">{patchStats.pending || 0}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Бэкапов:</span><span className="font-bold text-blue-400">{patchStats.backups_count || 0}</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}
