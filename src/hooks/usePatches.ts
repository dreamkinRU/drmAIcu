import { useState, useEffect } from 'react';
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
    if (!confirm('Применить патч ' + patch.patch_id + '?')) return;
    setApplyingPatch(true);
    try {
      const data = await applyPatchApi(patch);
      if (data.success) {
        setPatchLog(prev => [...prev, '[' + new Date().toLocaleTimeString() + '] ✅ ' + data.message]);
        alert(data.message + '\nСписок патчей обновлен.');
        loadPatches();
      } else {
        alert('Ошибка: ' + data.error);
      }
    } catch {
      alert('Ошибка сети');
    } finally {
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
    if (!confirm('Применить все патчи (' + patchStats.pending + ' шт.)?')) return;
    setApplyingPatch(true);
    try {
      const data = await applyAllPendingApi();
      if (data.success) {
        alert('Применено: ' + data.results.filter(r => r.success).length + '\nСписок патчей обновлен.');
        loadPatches();
      }
    } catch {
      alert('Ошибка сети');
    } finally {
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
