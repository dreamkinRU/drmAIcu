import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { MDFile } from '../../types';
import { mdFiles } from '../../utils/constants';

// Метка кнопки без ведущего пути: docs/ARCHITECTURE.md → ARCHITECTURE.md,
// а файл в корне (README.md) → /README.md.
function mdButtonLabel(name: string): string {
  if (name.startsWith('docs/')) return name.slice('docs/'.length);
  return '/' + name;
}

type ViewMode = 'preview' | 'edit';

interface MDTabProps {
  selectedMDFile: MDFile | null;
  mdContent: string;
  setMdContent: (value: string) => void;
  mdFileExists: boolean;
  loadRealMDFile: (file: MDFile) => void;
  saveRealMDFile: () => void;
}

export default function MDTab({
  selectedMDFile, mdContent, setMdContent, mdFileExists,
  loadRealMDFile, saveRealMDFile,
}: MDTabProps) {
  const [view, setView] = useState<ViewMode>('preview');

  // При выборе другого файла всегда возвращаемся в режим просмотра,
  // чтобы не увидеть «сырое» полотно разметки вместо документа.
  useEffect(() => { setView('preview'); }, [selectedMDFile?.name]);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">📝 Документация</h2>

      <div className="grid md:grid-cols-4 gap-4">
        {mdFiles.map(file => (
          <button
            key={file.name}
            onClick={() => loadRealMDFile(file)}
            className={`rounded-xl border-2 p-4 text-left transition-all ${
              selectedMDFile?.name === file.name
                ? 'border-emerald-500/50 bg-emerald-500/5'
                : 'border-gray-700 bg-gray-900/50 hover:border-gray-600'
            }`}
          >
            <h3 className="font-bold text-white text-base mb-2">{mdButtonLabel(file.name)}</h3>
            <p className="text-xs text-gray-400">{file.description}</p>
          </button>
        ))}
      </div>

      {selectedMDFile && (
        <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
          <div className="flex justify-between items-center gap-3 mb-4 flex-wrap">
            <h3 className="text-lg font-bold text-gray-300">📝 {mdButtonLabel(selectedMDFile.name)}</h3>
            <div className="flex items-center gap-2">
              <div className="flex rounded-lg overflow-hidden border border-gray-700">
                <button
                  type="button"
                  onClick={() => setView('preview')}
                  className={`px-3 py-1.5 text-xs font-semibold transition-all ${
                    view === 'preview'
                      ? 'bg-cyan-500/15 text-cyan-300'
                      : 'bg-gray-800/50 text-gray-300 hover:bg-gray-700/50'
                  }`}
                >
                  👁 Просмотр
                </button>
                <button
                  type="button"
                  onClick={() => setView('edit')}
                  className={`px-3 py-1.5 text-xs font-semibold transition-all ${
                    view === 'edit'
                      ? 'bg-cyan-500/15 text-cyan-300'
                      : 'bg-gray-800/50 text-gray-300 hover:bg-gray-700/50'
                  }`}
                >
                  ✏️ Редактор
                </button>
              </div>
              <button
                onClick={saveRealMDFile}
                className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-bold"
              >
                💾 Сохранить
              </button>
            </div>
          </div>
          {!mdFileExists && (
            <div className="mb-4 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-sm">
              ⚠️ Файл не существует. Напишите содержимое и нажмите "Сохранить".
            </div>
          )}
          {view === 'preview' ? (
            <div className="h-96 overflow-y-auto rounded-lg bg-gray-800 border border-gray-700 px-5 py-4">
              <div className="prose prose-invert max-w-none prose-headings:text-white prose-a:text-cyan-300 prose-code:text-emerald-300 prose-pre:bg-gray-900 prose-strong:text-white">
                <ReactMarkdown>{mdContent}</ReactMarkdown>
              </div>
            </div>
          ) : (
            <textarea
              value={mdContent}
              onChange={(e) => setMdContent(e.target.value)}
              placeholder="Начните писать…"
              className="w-full h-96 px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm font-mono focus:border-emerald-500 focus:outline-none resize-none"
            />
          )}
          <div className="mt-2 text-xs text-gray-500">
            Символов: {mdContent.length} | Строк: {mdContent.split('\n').length}
          </div>
        </div>
      )}
    </div>
  );
}
