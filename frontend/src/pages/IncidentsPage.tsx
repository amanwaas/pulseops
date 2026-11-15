import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, Clock, Globe, ShieldAlert, Check } from 'lucide-react';
import { api } from '../api/client';
import { Incident } from '../api/types';
import { formatDistanceToNow, parseISO } from 'date-fns';
import { useAuth } from '../hooks/useAuth';

export const IncidentsPage: React.FC = () => {
  const { isDeveloper } = useAuth();
  const [statusFilter, setStatusFilter] = useState<'all' | 'open' | 'resolved'>('all');

  const { data: incidents = [], refetch, isLoading } = useQuery<Incident[]>({
    queryKey: ['incidents', statusFilter],
    queryFn: () => api.incidents.list({ status: statusFilter === 'all' ? undefined : statusFilter }),
    refetchInterval: 15000,
  });

  const handleResolve = async (incidentId: string) => {
    try {
      await api.incidents.resolve(incidentId);
      refetch();
    } catch (err) {
      console.error('Failed to resolve incident', err);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-surface-800">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2.5">
            <ShieldAlert className="w-6 h-6 text-rose-400" />
            Incidents & Outages Log
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Tracks service downtime events, failure reasons, and resolution lifecycles.
          </p>
        </div>

        {/* Status Filter */}
        <div className="flex items-center gap-1 p-1 rounded-xl bg-surface-900 border border-surface-800">
          {(['all', 'open', 'resolved'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium uppercase tracking-wider transition-colors ${
                statusFilter === s
                  ? 'bg-surface-800 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="py-20 text-center text-xs font-mono text-slate-500">
          Loading incident history...
        </div>
      ) : incidents.length === 0 ? (
        <div className="py-20 text-center rounded-2xl border border-surface-800 bg-surface-900/30 space-y-2">
          <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto" />
          <h3 className="text-base font-semibold text-slate-200">No Incidents Recorded</h3>
          <p className="text-xs text-slate-500">
            All monitored microservice endpoints are functioning normally.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {incidents.map((inc) => {
            const isOpen = inc.status === 'open';
            return (
              <div
                key={inc.id}
                className={`p-4 rounded-2xl border transition-all ${
                  isOpen
                    ? 'border-rose-500/40 bg-rose-950/20 shadow-md shadow-rose-950/30'
                    : 'border-surface-800 bg-surface-900/40'
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div
                      className={`p-2 rounded-xl mt-0.5 ${
                        isOpen ? 'bg-rose-500/20 text-rose-400' : 'bg-surface-800 text-slate-400'
                      }`}
                    >
                      {isOpen ? (
                        <AlertTriangle className="w-5 h-5 animate-pulse" />
                      ) : (
                        <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                      )}
                    </div>

                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-100">{inc.project_name || 'Project'}</span>
                        <span className="text-[11px] px-2 py-0.5 rounded font-mono uppercase bg-surface-800 text-slate-300 border border-surface-700">
                          {inc.environment}
                        </span>
                        <span
                          className={`text-[10px] font-mono uppercase font-bold px-2 py-0.5 rounded ${
                            isOpen
                              ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                              : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                          }`}
                        >
                          {inc.status}
                        </span>
                      </div>

                      <p className="text-xs font-mono text-slate-300 mt-1">
                        {inc.failure_reason}
                      </p>

                      <div className="flex items-center gap-4 text-[11px] text-slate-500 mt-2 font-mono">
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          Started: {formatDistanceToNow(parseISO(inc.started_at), { addSuffix: true })}
                        </span>
                        {inc.resolved_at && (
                          <span className="text-emerald-400 flex items-center gap-1">
                            <Check className="w-3 h-3" />
                            Resolved: {formatDistanceToNow(parseISO(inc.resolved_at), { addSuffix: true })}
                          </span>
                        )}
                        <span>Failed Probes: {inc.consecutive_failures}</span>
                      </div>
                    </div>
                  </div>

                  {isOpen && isDeveloper && (
                    <button
                      onClick={() => handleResolve(inc.id)}
                      className="px-3 py-1.5 rounded-xl bg-emerald-600/30 hover:bg-emerald-600/50 border border-emerald-500/40 text-emerald-300 text-xs font-medium self-end sm:self-center transition-colors flex items-center gap-1.5"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Mark Resolved
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
