import React from 'react';
import { AlertTriangle, CheckCircle, ExternalLink } from 'lucide-react';
import { Incident } from '../api/types';
import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';

interface IncidentBannerProps {
  incidents: Incident[];
  onResolved: () => void;
}

export const IncidentBanner: React.FC<IncidentBannerProps> = ({ incidents, onResolved }) => {
  const { isDeveloper } = useAuth();

  if (!incidents || incidents.length === 0) {
    return null;
  }

  const handleResolve = async (incidentId: string) => {
    try {
      await api.incidents.resolve(incidentId);
      onResolved();
    } catch (e) {
      console.error('Failed to resolve incident:', e);
    }
  };

  return (
    <div className="mb-6 space-y-2">
      {incidents.map((inc) => (
        <div
          key={inc.id}
          className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-rose-950/40 border border-rose-500/40 text-rose-200 shadow-lg shadow-rose-950/20"
        >
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-lg bg-rose-500/20 text-rose-400 mt-0.5">
              <AlertTriangle className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-rose-100">{inc.project_name || 'Service Target'}</span>
                <span className="text-xs px-2 py-0.5 rounded bg-rose-900/60 font-mono uppercase text-rose-300 border border-rose-700/50">
                  {inc.environment}
                </span>
                <span className="text-xs text-rose-400">
                  Failed {inc.consecutive_failures} consecutive checks
                </span>
              </div>
              <p className="text-sm text-rose-300/90 mt-1 font-mono text-xs">
                {inc.failure_reason}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-center">
            {isDeveloper && (
              <button
                onClick={() => handleResolve(inc.id)}
                className="px-3 py-1.5 rounded-lg bg-emerald-600/30 hover:bg-emerald-600/50 border border-emerald-500/40 text-emerald-300 text-xs font-medium flex items-center gap-1.5 transition-colors"
              >
                <CheckCircle className="w-3.5 h-3.5" />
                Resolve Incident
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
