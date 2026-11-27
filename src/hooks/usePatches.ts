import { useState, useEffect, useRef } from 'react';
import { PatchInfo } from '../types';
import { POLL_INTERVALS } from '../utils/constants';
import {
  loadPatchList,
  loadPatchStats,
  previewPatch as previewPatchApi,
  applyPatchApi,
  rollbackLastPatch as rollbackLastPatchApi,
  archivePatchApi,
  deletePatchApi,
  applyAllPendingApi,
  PatchStats,
} from '../services/api';

export function usePatches(addLog: (entry: any) => void) {
  const [patches, setPatches] = useState<PatchInfo[]>([]);
  const [patchStats, setPatchStats] = useState<PatchStats>({
    total: 0, applied: 0, pending: 0, errors: 0, backups_count: 0,
  });
  const [selectedPatch, setSelectedPatch] = useState<PatchInfo | null>(null);
  const [patchPreview, setPatchPreview] = useState<any>(null);
  const [applyingPatch, setApplyingPatch] = useState(false);
  const applyGuard = useRef(false);
  const [patchFilter, setPatchFilter] = useState<'all' | 'pending' | 'applied' | 'errors'>('all');
  const [patchLog, setPatchLog] = useState<string[]>([]);

  // ANTI-JITTER: setState только при реальном изменении — иначе каждый опрос
  // создаёт новый список и перерисовывает вкладку без причины.
  const sameJson = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

  const loadPatches = async () => {
    const [list, stats] = await Promise.all([loadPatchList(), loadPatchStats()]);
    setPatches(prev => (sameJson(prev, list) ? prev : list));
    setPatchStats(prev => (sameJson(prev, stats) ? prev : stats));
  };

  const previewPatch = async (patch: PatchInfo) => {
    setSelectedPatch(patch);
    setPatchPreview(null);
    const data = await previewPatchApi(patch);
    setPatchPreview(data);
  };

  const applyPatch = async (patch: PatchInfo) => {
    if (applyingPatch || patch.is_applied || patches.some(p => p.patch_id === patch.patch_id && p.is_applied)) return;
    if (!confirm('Применить патч ' + patch.patch_id + '?')) return;
    if (applyGuard.current) return;
    applyGuard.current = true;
    setApplyingPatch(true);
    setPatchLog(prev => [...prev, 'Начато применение #' + patch.patch_id]);
    try {
      const data = await applyPatchApi(patch);
      if (data.success) {
        setSelectedPatch(null);
        setPatchPreview(null);
        setPatches(prev => prev.map(p => p.patch_id === patch.patch_id ? { ...p, is_applied: true } : p));
        setPatchLog(prev => [...prev, '[' + new Date().toLocaleTimeString() + '] ✅ ' + data.message]);
        alert(data.message + '\nСписок патчей обновлен.');
        loadPatches();
      } else {
        setPatchLog(prev => [...prev, 'Ошибка #' + patch.patch_id + ': ' + (data.error || 'Результат неизвестен')]);
        alert('Ошибка: ' + data.error);
      }
    } catch {
      setPatchLog(prev => [...prev, 'Связь потеряна — проверьте манифест перед повтором']);
      alert('Ошибка сети');
    } finally {
      applyGuard.current = false;
      setApplyingPatch(false);
    }
  };

  const rollbackLastPatch = async () => {
    if (!confirm('Откатить последний патч?')) return;
    const data = await rollbackLastPatchApi();
    if (data.success) {
      alert(data.message + '\nСписок патчей обновлен.');
      loadPatches();
    } else {
      alert('Ошибка: ' + data.error);
    }
  };

  const archivePatch = async (filename: string) => {
    const data = await archivePatchApi(filename);
    if (data.success) {
      loadPatches();
      setPatchLog(prev => [...prev, '[' + new Date().toLocaleTimeString() + '] 📦 ' + data.message]);
    } else {
      alert(data.error || 'Архивация не завершена');
    }
  };

  const deletePatch = async (filename: string) => {
    if (!confirm('Удалить ' + filename + '?')) return;
    const data = await deletePatchApi(filename);
    if (data.success) {
      loadPatches();
      setPatchLog(prev => [...prev, '[' + new Date().toLocaleTimeString() + '] 🗑 ' + data.message]);
    }
  };

  const applyAllPending = async () => {
    if (applyGuard.current || !confirm('Применить все патчи (' + patchStats.pending + ' шт.)?')) return;
    applyGuard.current = true;
    setApplyingPatch(true);
    try {
      const data = await applyAllPendingApi();
      const count = data.results.filter(r => r.success).length;
      const message = 'Применено: ' + count + (data.success ? '' : '; пакет остановлен или результат неизвестен');
      setPatchLog(prev => [...prev, message]);
      alert(message);
      setSelectedPatch(null);
      setPatchPreview(null);
      await loadPatches();
    } catch {
      alert('Ошибка сети');
    } finally {
      applyGuard.current = false;
      setApplyingPatch(false);
    }
  };

  useEffect(() => {
    loadPatches();
    const interval = setInterval(loadPatches, POLL_INTERVALS.PATCHES);
    return () => clearInterval(interval);
  }, []);

  return {
    patches, patchStats, selectedPatch, patchPreview, applyingPatch,
    patchFilter, setPatchFilter, patchLog,
    loadPatches, previewPatch, applyPatch, rollbackLastPatch,
    archivePatch, deletePatch, applyAllPending,
    setSelectedPatch, setPatchPreview,
  };
}
