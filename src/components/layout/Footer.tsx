import { TabId } from '../../types';

interface FooterProps {
  setActiveTab: (tab: TabId) => void;
}

export default function Footer({ setActiveTab }: FooterProps) {
  return (
    <footer className="fixed bottom-0 left-0 right-0 border-t border-gray-800 bg-gray-900/95 backdrop-blur-sm py-3 px-4 z-50">
      <div className="max-w-7xl mx-auto flex items-center justify-between text-xs text-gray-500">
        <div className="flex items-center gap-4">
          <button onClick={() => setActiveTab('md')} className="hover:text-emerald-400 transition-colors flex items-center gap-1">
            <span>📝</span> MD
          </button>
          <button onClick={() => setActiveTab('logs')} className="hover:text-emerald-400 transition-colors flex items-center gap-1">
            <span>▤</span> Логи
          </button>
        </div>
        <span>v.3.5.3 HARDENED • dreamkin • 2026</span>
      </div>
    </footer>
  );
}
