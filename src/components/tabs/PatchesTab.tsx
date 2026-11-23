import { PatchInfo } from '../../types';
import { PatchStats } from '../../services/api';
import Modal from '../ui/Modal';

interface PatchesTabProps {
  patches: PatchInfo[];
  patchStats: PatchStats;
  selectedPatch: PatchInfo | null;
  patchPreview: any;
  applyingPatch: boolean;
  patchFilter: 'all' | 'pending' | 'applied' | 'errors';
  setPatchFilter: (filter: 'all' | 'pending' | 'applied' | 'errors') => void;
  patchLog: string[];
  previewPatch: (patch: PatchInfo) => void;
  applyPatch: (patch: PatchInfo) => void;
  rollbackLastPatch: () => void;
  archivePatch: (filename: string) => void;
  deletePatch: (filename: string) => void;
  applyAllPending: () => void;
  setSelectedPatch: (patch: PatchInfo | null) => void;
  setPatchPreview: (preview: any) => void;
}

export default function PatchesTab({
  patches, patchStats, selectedPatch, patchPreview, applyingPatch,
  patchFilter, setPatchFilter, patchLog,
  previewPatch, applyPatch, rollbackLastPatch,
  archivePatch, deletePatch, applyAllPending,
  setSelectedPatch, setPatchPreview,
}: PatchesTabProps) {
  const filteredPatches = patches.filter(p => {
    if (patchFilter === 'pending') return !p.is_applied && !p.error;
    if (patchFilter === 'applied') return p.is_applied;
    if (patchFilter === 'errors') return p.error;
    return true;
  });

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold">🔄 Система автопатчей</h2>
          <p className="text-sm text-gray-400 mt-1">Сканирование patch/ и Загрузок каждые 5 сек</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={rollbackLastPatch}
            className="px-4 py-2 rounded-lg bg-red-500/20 border border-red-500/50 text-red-400 text-sm font-bold hover:bg-red-500/30"
          >
            ↩ Откатить
          </button>
          <button
            onClick={applyAllPending}
            disabled={applyingPatch || !patchStats.pending}
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-500 text-white text-sm font-bold disabled:opacity-50"
          >
            ⚡ Применить все ({patchStats.pending || 0})
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-4">
          <div className="text-xs text-gray-500">Всего</div>
          <div className="text-2xl font-bold text-white">{patchStats.total || 0}</div>
        </div>
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4">
          <div className="text-xs text-emerald-400">Применено</div>
          <div className="text-2xl font-bold text-emerald-400">{patchStats.applied || 0}</div>
        </div>
        <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-4">
          <div className="text-xs text-yellow-400">Ожидают</div>
          <div className="text-2xl font-bold text-yellow-400">{patchStats.pending || 0}</div>
        </div>
        <div className="rounded-xl border border-red-500/30 bg-red-500/5 p-4">
          <div className="text-xs text-red-400">С ошибками</div>
          <div className="text-2xl font-bold text-red-400">{patchStats.errors || 0}</div>
        </div>
        <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 p-4">
          <div className="text-xs text-blue-400">Бэкапов</div>
          <div className="text-2xl font-bold text-blue-400">{patchStats.backups_count || 0}</div>
        </div>
      </div>

      <div className="flex gap-2">
        {(['all', 'pending', 'applied', 'errors'] as const).map(f => (
          <button
            key={f}
            onClick={() => setPatchFilter(f)}
            className={`px-4 py-2 rounded-lg text-sm font-bold transition-all ${
              patchFilter === f
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'
                : 'bg-gray-800 text-gray-400 border border-gray-700'
            }`}
          >
            {f === 'all' ? '📋 Все' : f === 'pending' ? '⏳ Ожидают' : f === 'applied' ? '✅ Применены' : '❌ С ошибками'}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {filteredPatches.map(patch => (
          <div
            key={patch.filename}
            className={`rounded-xl border-2 p-4 transition-all ${
              patch.is_applied
                ? 'border-emerald-500/30 bg-emerald-500/5'
                : patch.error
                ? 'border-red-500/30 bg-red-500/5'
                : 'border-gray-700 bg-gray-900/50 hover:border-cyan-500/30'
            }`}
          >
            <div className="flex justify-between items-start gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3 mb-2 flex-wrap">
                  <span className="px-2 py-1 rounded bg-gray-800 text-xs font-mono text-cyan-400">
                    #{patch.patch_id}
                  </span>
                  <span className="font-bold text-white truncate">{patch.target_file}</span>
                  {patch.is_applied && (
                    <span className="px-2 py-0.5 rounded text-xs bg-emerald-500/20 text-emerald-400">
                      ПРИМЕНЕН
                    </span>
                  )}
                  {patch.error && (
                    <span className="px-2 py-0.5 rounded text-xs bg-red-500/20 text-red-400">
                      ОШИБКА
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-400 mb-2">{patch.description}</p>
                <div className="flex gap-4 flex-wrap text-xs text-gray-500">
                  <span>👤 {patch.author}</span>
                  <span>📄 {patch.content_length} символов</span>
                </div>
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  onClick={() => previewPatch(patch)}
                  className="px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs font-bold"
                >
                  👁 Просмотр
                </button>
                {!patch.is_applied && !patch.error && (
                  <button
                    onClick={() => applyPatch(patch)}
                    disabled={applyingPatch}
                    className="px-3 py-1.5 rounded bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold disabled:opacity-50"
                  >
                    ✅ Применить
                  </button>
                )}
                <button
                  onClick={() => archivePatch(patch.filename)}
                  className="px-3 py-1.5 rounded bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 text-xs font-bold"
                >
                  📦 В архив
                </button>
                <button
                  onClick={() => deletePatch(patch.filename)}
                  className="px-3 py-1.5 rounded bg-red-500/20 hover:bg-red-500/30 text-red-400 text-xs font-bold"
                >
                  🗑 Удалить
                </button>
              </div>
            </div>
          </div>
        ))}
        {patches.length === 0 && (
          <div className="text-center py-12 text-gray-500 border-2 border-dashed border-gray-700 rounded-xl">
            <p className="text-lg mb-2">📂 Нет патчей в patch/ и Загрузках</p>
          </div>
        )}
      </div>

      <Modal
        isOpen={!!selectedPatch && !!patchPreview}
        onClose={() => {
          setSelectedPatch(null);
          setPatchPreview(null);
        }}
        title={selectedPatch ? `Превью патча #${selectedPatch.patch_id}` : ''}
      >
        {patchPreview?.success ? (
          <div className="space-y-4">
            <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
              ✅ {patchPreview.message}
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="p-3 rounded bg-gray-800">
                <div className="text-gray-500 text-xs">Старый размер</div>
                <div className="font-bold">
                  {patchPreview.old_size} байт / {patchPreview.old_lines} строк
                </div>
              </div>
              <div className="p-3 rounded bg-gray-800">
                <div className="text-gray-500 text-xs">Новый размер</div>
                <div className="font-bold">
                  {patchPreview.new_size} байт / {patchPreview.new_lines} строк
                </div>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => {
                  setSelectedPatch(null);
                  setPatchPreview(null);
                }}
                className="flex-1 py-3 rounded-lg bg-gray-700 hover:bg-gray-600 text-white font-bold"
              >
                Отмена
              </button>
              <button
                onClick={() => {
                  if (selectedPatch) applyPatch(selectedPatch);
                  setSelectedPatch(null);
                  setPatchPreview(null);
                }}
                disabled={applyingPatch}
                className="flex-1 py-3 rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-500 text-white font-bold disabled:opacity-50"
              >
                ✅ Применить
              </button>
            </div>
          </div>
        ) : patchPreview ? (
          <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400">
            ❌ {patchPreview.error}
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
