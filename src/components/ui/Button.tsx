import React from 'react';

interface ButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  disabled?: boolean;
  className?: string;
  type?: 'button' | 'submit';
}

export default function Button({
  children,
  onClick,
  variant = 'primary',
  disabled = false,
  className = '',
  type = 'button',
}: ButtonProps) {
  const variants = {
    primary: 'bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white shadow-lg shadow-emerald-500/20',
    secondary: 'bg-gray-700 hover:bg-gray-600 text-gray-300',
    danger: 'bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/50',
    ghost: 'bg-gray-800/50 hover:bg-gray-700 text-gray-400 border border-gray-700',
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`px-4 py-2 rounded-lg font-bold text-sm transition-all ${variants[variant]} ${disabled ? 'opacity-50 cursor-not-allowed' : ''} ${className}`}
    >
      {children}
    </button>
  );
}
