interface StatusBadgeProps {
  status: string;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const colors: Record<string, string> = {
    active: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    frozen: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    offline: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    online: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    error: 'bg-red-500/20 text-red-400 border-red-500/30',
  };
  const labels: Record<string, string> = {
    active: 'АКТИВЕН',
    frozen: 'ЗАМОРОЖЕН',
    offline: 'ОФФЛАЙН',
    online: 'ОНЛАЙН',
    error: 'ОШИБКА',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${colors[status] || colors.offline}`}>
      {labels[status] || status}
    </span>
  );
}
