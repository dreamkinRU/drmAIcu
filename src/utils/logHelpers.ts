// Помощники для вкладки «Логи»: время записи и понятные пути исправления
// для типовых git-ошибок синхронизации (подробности — docs/USER_GUIDE.md,
// раздел «Типовые ошибки и пути исправления»).

/** Текущее время в формате HH:MM:SS (как в LogEntry.time). */
export function nowStr(): string {
  const d = new Date();
  const p = (n: number): string => String(n).padStart(2, '0');
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

// Каждой узнаваемой ошибке добавляем путь исправления — ошибку больше не нужно
// успеть прочитать за полсекунды: она остаётся в плашке и во вкладке «Логи».
const GIT_HINTS: Array<[RegExp, string]> = [
  [/safe\.directory|dubious ownership/i,
    'Владелец папки репозитория не совпадает с текущим пользователем. Исправление (cmd от своего имени): git config --global --add safe.directory "<путь к репозиторию>".'],
  [/is denied|отказано в доступе|Permission denied/i,
    'Нет прав на файл/папку репозитория. Исправление: закройте программы, удерживающие файлы (редактор, OneDrive/Dropbox, антивирус), убедитесь, что панель запущена от пользователя-владельца репозитория.'],
  [/Authentication failed|could not read Username|403|401/i,
    'GitHub не принял учётные данные. Исправление: обновите сохранённый логин/токен (Панель управления → Диспетчер учётных данных → git:https://github.com) или выполните git pull в этом репозитории вручную, чтобы заново пройти авторизацию.'],
  [/non-fast-forward|rejected|fetch first/i,
    'Ветка разошлась с удалённой. Исправление: подтяните чужие коммиты (git pull --rebase) и повторите синхронизацию; если пуш всё равно отклоняется — проверьте защиту ветки на GitHub.'],
  [/not a git repository/i,
    'Папка не является репозиторием (нет .git). Исправление: укажите корень существующего репозитория или выполните в нём git init.'],
  [/CONFLICT|merge conflict/i,
    'Конфликт слияния. Исправление: разрешите конфликты в перечисленных файлах, затем git add <файлы> и git rebase --continue (отмена — git rebase --abort).'],
  [/index\.lock|cannot lock ref/i,
    'Git заблокирован незавершённой операцией. Исправление: закройте другие git-клиенты (GitHub Desktop, IDE); если не помогло — удалите файл .git/index.lock.'],
  [/detached HEAD/i,
    'Репозиторий в состоянии detached HEAD. Исправление: переключитесь на нужную ветку (вкладка «Репозитории» → «Ветки») и повторите операцию.'],
];

/** Добавить к тексту git-ошибки путь исправления, если она узнаваема. */
export function withFixHint(msg: string): string {
  if (!msg) return msg;
  for (const [re, hint] of GIT_HINTS) {
    if (hint && re.test(msg)) return msg + ' — ' + hint;
  }
  return msg;
}
