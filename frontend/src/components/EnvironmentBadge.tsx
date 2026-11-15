import React from 'react';
import { Environment } from '../api/types';

interface EnvironmentBadgeProps {
  environment: Environment | string;
}

export const EnvironmentBadge: React.FC<EnvironmentBadgeProps> = ({ environment }) => {
  const getBadgeStyle = () => {
    switch (environment.toLowerCase()) {
      case 'production':
        return 'bg-purple-950/60 border-purple-500/40 text-purple-300';
      case 'staging':
        return 'bg-blue-950/60 border-blue-500/40 text-blue-300';
      case 'testing':
        return 'bg-amber-950/60 border-amber-500/40 text-amber-300';
      case 'development':
      default:
        return 'bg-slate-800/80 border-slate-700 text-slate-300';
    }
  };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono uppercase tracking-wider border ${getBadgeStyle()}`}>
      {environment}
    </span>
  );
};
