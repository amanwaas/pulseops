import React, { useState } from 'react';
import { Activity, Play, Plus, Trash2, Globe, Clock, ShieldAlert } from 'lucide-react';
import { HealthTarget } from '../api/types';
import { StatusPill } from './StatusPill';
import { EnvironmentBadge } from './EnvironmentBadge';
import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';

interface HealthTargetsListProps {
  targets: HealthTarget[];
  projectId: string;
  onRefresh: () => void;
  selectedTargetId: string | null;
  onSelectTarget: (id: string) => void;
}

export const HealthTargetsList: React.FC<HealthTargetsListProps> = ({
  targets,
  projectId,
  onRefresh,
  selectedTargetId,
  onSelectTarget,
}) => {
  const { isDeveloper, isAdmin } = useAuth();
  const [probingId, setProbingId] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newEnv, setNewEnv] = useState<'production' | 'staging' | 'testing' | 'development'>('production');
  const [newUrl, setNewUrl] = useState('');
  const [newInterval, setNewInterval] = useState(60);

  const handleProbe = async (targetId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setProbingId(targetId);
    try {
      await api.health.probeTarget(targetId);
      onRefresh();
    } catch (err) {
      console.error('Probe failed', err);
    } finally {
      setProbingId(null);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUrl) return;
    try {
      await api.health.createTarget(projectId, {
        environment: newEnv,
        endpoint_url: newUrl,
        check_interval_seconds: newInterval,
        timeout_seconds: 5,
        is_active: true,
      });
      setNewUrl('');
      setShowAddForm(false);
      onRefresh();
    } catch (err) {
      console.error('Failed to create health target', err);
    }
  };

  const handleDelete = async (targetId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Are you sure you want to delete this monitoring endpoint?')) return;
    try {
      await api.health.deleteTarget(targetId);
      onRefresh();
    } catch (err) {
      console.error('Delete target error', err);
    }
  };

  return (
    <div className="rounded-2xl border border-surface-800 bg-surface-900/40 p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <span>Health Monitoring Targets</span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-surface-800 text-slate-400 border border-surface-700 font-mono">
              {targets.length}
            </span>
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Click a target below to load its latency timeline & deployment correlation graph.
          </p>
        </div>

        {isAdmin && (
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="px-3 py-1.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium flex items-center gap-1.5 transition-colors shadow-sm"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Target
          </button>
        )}
      </div>

      {/* Add Target Modal/Drawer */}
      {showAddForm && (
        <form onSubmit={handleCreate} className="mb-4 p-4 rounded-xl bg-surface-950/80 border border-surface-800 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Environment</label>
              <select
                value={newEnv}
                onChange={(e: any) => setNewEnv(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-surface-900 border border-surface-700 text-xs text-slate-200"
              >
                <option value="production">Production</option>
                <option value="staging">Staging</option>
                <option value="testing">Testing</option>
                <option value="development">Development</option>
              </select>
            </div>

            <div className="sm:col-span-2">
              <label className="block text-[11px] font-medium text-slate-400 mb-1">Health Check URL</label>
              <input
                type="url"
                required
                placeholder="https://api.myproject.com/healthz"
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-surface-900 border border-surface-700 text-xs text-slate-200"
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-slate-400">Interval:</span>
              <select
                value={newInterval}
                onChange={(e) => setNewInterval(Number(e.target.value))}
                className="px-2 py-1 rounded-lg bg-surface-900 border border-surface-700 text-xs text-slate-200"
              >
                <option value={30}>30s</option>
                <option value={60}>60s</option>
                <option value={120}>120s</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-3 py-1 rounded-lg text-xs text-slate-400 hover:text-slate-200"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-3 py-1 rounded-lg bg-brand-600 hover:bg-brand-500 text-white text-xs font-medium"
              >
                Save Endpoint
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Targets List */}
      <div className="space-y-2">
        {targets.length === 0 ? (
          <div className="py-6 text-center text-slate-500 text-xs">
            No health targets configured. Add an endpoint to begin uptime monitoring.
          </div>
        ) : (
          targets.map((t) => {
            const isSelected = selectedTargetId === t.id;
            return (
              <div
                key={t.id}
                onClick={() => onSelectTarget(t.id)}
                className={`flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3.5 rounded-xl border transition-all cursor-pointer ${
                  isSelected
                    ? 'border-brand-500/60 bg-brand-950/20 shadow-md shadow-brand-950/40'
                    : 'border-surface-800/80 bg-surface-950/40 hover:bg-surface-800/30'
                }`}
              >
                <div className="flex items-start sm:items-center gap-3">
                  <EnvironmentBadge environment={t.environment} />
                  <div>
                    <div className="font-mono text-xs text-slate-200 hover:text-brand-300 flex items-center gap-1.5 truncate max-w-sm sm:max-w-md">
                      <Globe className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                      <span className="truncate">{t.endpoint_url}</span>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-1">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Every {t.check_interval_seconds}s (timeout {t.timeout_seconds}s)
                      </span>
                      {t.consecutive_failures > 0 && (
                        <span className="text-rose-400 flex items-center gap-1">
                          <ShieldAlert className="w-3 h-3" />
                          {t.consecutive_failures} failures
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-center">
                  <StatusPill status={t.last_status} size="sm" />

                  {isDeveloper && (
                    <button
                      onClick={(e) => handleProbe(t.id, e)}
                      disabled={probingId === t.id}
                      title="Trigger immediate probe"
                      className="p-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 text-slate-300 hover:text-white transition-colors disabled:opacity-50"
                    >
                      <Play className={`w-3.5 h-3.5 ${probingId === t.id ? 'animate-spin text-brand-400' : ''}`} />
                    </button>
                  )}

                  {isAdmin && (
                    <button
                      onClick={(e) => handleDelete(t.id, e)}
                      title="Remove target"
                      className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-surface-800 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
