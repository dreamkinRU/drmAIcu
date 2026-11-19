import { MDFile } from '../../types';
import { mdFiles } from '../../utils/constants';

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
            <h3 className="font-bold text-white text-base mb-2">{file.name}</h3>
            <p className="text-xs text-gray-400">{file.description}</p>
          </button>
        ))}
      </div>

      {selectedMDFile && (
        <div className="rounded-xl border border-gray-700 bg-gray-900/50 p-6">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-lg font-bold text-gray-300">📝 {selectedMDFile.name}</h3>
            <button
              onClick={saveRealMDFile}
              className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-bold"
            >
              💾 Сохранить
            </button>
          </div>
          {!mdFileExists && (
            <div className="mb-4 p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-sm">
              ⚠️ Файл не существует. Напишите содержимое и нажмите "Сохранить".
            </div>
          )}
          <textarea
            value={mdContent}
            onChange={(e) => setMdContent(e.target.value)}
            placeholder="Начните писать..."
            className="w-full h-96 px-4 py-3 rounded-lg bg-gray-800 border border-gray-700 text-white text-sm font-mono focus:border-emerald-500 focus:outline-none resize-none"
          />
          <div className="mt-2 text-xs text-gray-500">
            Символов: {mdContent.length} | Строк: {mdContent.split('\n').length}
          </div>
        </div>
      )}
    </div>
  );
}
