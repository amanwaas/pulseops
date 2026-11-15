import React from 'react';
import { HealthStatus } from '../api/types';

interface StatusPillProps {
  status: HealthStatus;
  size?: 'sm' | 'md' | 'lg';
}

export const StatusPill: React.FC<StatusPillProps> = ({ status, size = 'md' }) => {
  const getStyles = () => {
    switch (status) {
      case 'UP':
        return {
          bg: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
          dot: 'bg-emerald-500',
          ping: 'bg-emerald-400',
          label: 'OPERATIONAL',
        };
      case 'DOWN':
        return {
          bg: 'bg-rose-500/10 border-rose-500/30 text-rose-400',
          dot: 'bg-rose-500',
          ping: 'bg-rose-400',
          label: 'CRITICAL DOWN',
        };
      case 'DEGRADED':
        return {
          bg: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
          dot: 'bg-amber-500',
          ping: 'bg-amber-400',
          label: 'DEGRADED',
        };
      default:
        return {
          bg: 'bg-slate-500/10 border-slate-500/30 text-slate-400',
          dot: 'bg-slate-500',
          ping: 'bg-slate-400',
          label: 'UNKNOWN',
        };
    }
  };

  const config = getStyles();
  const textClasses = size === 'sm' ? 'text-xs px-2 py-0.5' : size === 'lg' ? 'text-sm px-3.5 py-1.5' : 'text-xs px-2.5 py-1';
  const dotClasses = size === 'sm' ? 'w-1.5 h-1.5' : 'w-2 h-2';

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${config.bg} ${textClasses}`}>
      <span className="relative flex">
        {status === 'UP' && (
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${config.ping}`} />
        )}
        <span className={`relative inline-flex rounded-full ${config.dot} ${dotClasses}`} />
      </span>
      <span>{config.label}</span>
    </span>
  );
};
