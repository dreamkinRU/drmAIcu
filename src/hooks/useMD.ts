import { useState } from 'react';
import { MDFile } from '../types';
import { loadMDFile, saveMDFile } from '../services/api';

export function useMD() {
  const [selectedMDFile, setSelectedMDFile] = useState<MDFile | null>(null);
  const [mdContent, setMdContent] = useState('');
  const [mdFileExists, setMdFileExists] = useState(true);

  const loadRealMDFile = async (file: MDFile) => {
    setSelectedMDFile(file);
    setMdFileExists(true);
    const data = await loadMDFile(file.name);
    if (data.error) {
      setMdFileExists(false);
      setMdContent('');
    } else {
      setMdContent(data.content);
    }
  };

  const saveRealMDFile = async () => {
    if (!selectedMDFile) return;
    const data = await saveMDFile(selectedMDFile.name, mdContent);
    if (data.success) {
      setMdFileExists(true);
      alert('Файл сохранён!');
    } else {
      alert('Ошибка: ' + data.error);
    }
  };

  return {
    selectedMDFile, setSelectedMDFile,
    mdContent, setMdContent,
    mdFileExists,
    loadRealMDFile, saveRealMDFile,
  };
}
