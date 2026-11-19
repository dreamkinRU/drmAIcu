import { useState } from 'react';
import { CodeIssue } from '../types';
import { initialCodeIssues } from '../utils/constants';

export function useCodeIssues() {
  const [codeIssues, setCodeIssues] = useState<CodeIssue[]>(initialCodeIssues);

  const fixCodeIssue = (issueId: number) => {
    const issue = codeIssues.find(i => i.id === issueId);
    if (!issue || issue.fixed) return;
    const fixLog = [
      '═══════════════════════════════════════',
      '⚠️ Реальное исправление через PatchMaster',
      '═══════════════════════════════════════',
      '',
      '1️⃣  Файл: ' + issue.file,
      '2️⃣  Тройной бэкап',
      '3️⃣  Замена в строке ' + issue.line,
      '4️⃣  Валидация',
      '5️⃣  Атомарная замена',
      '',
      '🔧 КАК ВЫПОЛНИТЬ:',
      'Шаг 1: Попросите ИИ сгенерировать патч',
      'Шаг 2: Сохраните JSON в patch/',
      'Шаг 3: Откройте вкладку "🔄 Патчи"',
      'Шаг 4: Нажмите "✅ Применить"',
      '',
      '═══════════════════════════════════════',
    ];
    setCodeIssues(prev =>
      prev.map(i => (i.id === issueId ? { ...i, fixed: true, fixLog } : i))
    );
  };

  const fixAll = () => {
    codeIssues.filter(i => !i.fixed).forEach(i => fixCodeIssue(i.id));
  };

  return { codeIssues, setCodeIssues, fixCodeIssue, fixAll };
}
