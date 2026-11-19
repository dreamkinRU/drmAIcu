interface ToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  label?: string;
  color?: string;
}

export default function Toggle({ enabled, onChange, label, color = 'bg-emerald-500' }: ToggleProps) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <button
        onClick={() => onChange(!enabled)}
        className={`w-10 h-5 rounded-full transition-all relative ${enabled ? color : 'bg-gray-700'}`}
      >
        <div
          className="w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all"
          style={{ left: enabled ? '22px' : '2px' }}
        />
      </button>
      {label && <span className="text-sm text-gray-400">{label}</span>}
    </label>
  );
}
