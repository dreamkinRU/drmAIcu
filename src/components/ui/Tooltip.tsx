interface TooltipProps {
  children: React.ReactNode;
  text: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
}

export default function Tooltip({ children, text, position = 'bottom' }: TooltipProps) {
  const posClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };
  const arrowClasses = {
    top: 'top-full left-1/2 -translate-x-1/2 border-t-gray-900',
    bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-gray-900',
    left: 'left-full top-1/2 -translate-y-1/2 border-l-gray-900',
    right: 'right-full top-1/2 -translate-y-1/2 border-r-gray-900',
  };
  return (
    <div className="relative group">
      {children}
      <div
        className={`absolute ${posClasses[position]} px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-xs text-gray-300 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-[100] shadow-xl`}
      >
        {text}
        <div className={`absolute ${arrowClasses[position]} border-4 border-transparent`}></div>
      </div>
    </div>
  );
}
