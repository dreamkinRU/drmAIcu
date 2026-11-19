import React from 'react';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  maxWidth?: string;
  maxHeight?: string;
}

export default function Modal({ isOpen, onClose, title, children, maxWidth = 'max-w-4xl', maxHeight = 'max-h-[90vh]' }: ModalProps) {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 bg-black/80 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className={`bg-gray-900 border border-gray-700 rounded-xl p-6 ${maxWidth} w-full ${maxHeight} overflow-hidden flex flex-col`}
        onClick={(e) => e.stopPropagation()}
      >
        {title && (
          <div className="flex justify-between items-start mb-4">
            <h3 className="text-xl font-bold">{title}</h3>
            <button onClick={onClose} className="text-gray-400 text-2xl hover:text-white">
              ×
            </button>
          </div>
        )}
        <div className="flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
