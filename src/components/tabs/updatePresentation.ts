export function cleanCommandOutput(value: unknown): string {
  if (typeof value !== 'string') return '';
  return value
    .replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, '')
    .replace(/(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]/g, '')
    .replace(/\x1b[@-_]/g, '')
    .replace(/\r\n?/g, '\n');
}

const STATE_LABELS: Record<string, string> = {
  IDLE: 'Ожидание', CHECKED: 'План готов', APPLYING: 'Обновление',
  CODE_UPDATED: 'Исходники обновлены', RESTORING: 'Восстановление',
  PREPARING: 'Подготовка окружения', RESTART_REQUIRED: 'Требуется перезапуск',
  COMPLETED: 'Завершено', FAILED: 'Ошибка',
  RECOVERY_REQUIRED: 'Требуется восстановление', UPDATE_NEEDS_REPAIR: 'Требуется исправление',
};

export function updateStateLabel(state: unknown): string {
  return typeof state === 'string' ? (Object.prototype.hasOwnProperty.call(STATE_LABELS, state) ? STATE_LABELS[state] : state) : '—';
}

export function hasNpmWarnings(step: {step?: string; ok?: boolean; stdout?: unknown; stderr?: unknown}): boolean {
  return step.step === 'npm' && step.ok === true && [step.stdout, step.stderr].some(value => /^\s*npm\s+warn(?:ing)?\b/im.test(cleanCommandOutput(value)));
}
