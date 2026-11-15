import React, { useState } from 'react';
import { X, Bell, Plus, Trash2, Send, CheckCircle2 } from 'lucide-react';
import { AlertConfig, AlertChannel } from '../api/types';
import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';

interface AlertConfigModalProps {
  projectId: string;
  projectName: string;
  configs: AlertConfig[];
  isOpen: boolean;
  onClose: () => void;
  onRefresh: () => void;
}

export const AlertConfigModal: React.FC<AlertConfigModalProps> = ({
  projectId,
  projectName,
  configs,
  isOpen,
  onClose,
  onRefresh,
}) => {
  const { isAdmin } = useAuth();
  const [channelType, setChannelType] = useState<AlertChannel>('slack');
  const [destUrl, setDestUrl] = useState('');
  const [notifyDeploy, setNotifyDeploy] = useState(true);
  const [notifyHealth, setNotifyHealth] = useState(true);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testSuccessId, setTestSuccessId] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!destUrl) return;
    try {
      await api.alerts.create(projectId, {
        channel_type: channelType,
        destination_url: destUrl,
        notify_on_deployment_fail: notifyDeploy,
        notify_on_health_fail: notifyHealth,
      });
      setDestUrl('');
      onRefresh();
    } catch (err) {
      console.error('Failed to create alert channel', err);
    }
  };

  const handleDelete = async (configId: string) => {
    try {
      await api.alerts.delete(configId);
      onRefresh();
    } catch (err) {
      console.error('Failed to delete alert config', err);
    }
  };

  const handleTest = async (configId: string) => {
    setTestingId(configId);
    try {
      await api.alerts.test(configId);
      setTestSuccessId(configId);
      setTimeout(() => setTestSuccessId(null), 3000);
    } catch (err) {
      console.error('Alert test dispatch failed', err);
    } finally {
      setTestingId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-xl rounded-2xl border border-surface-800 bg-surface-900 p-6 shadow-2xl space-y-5">
        <div className="flex items-center justify-between border-b border-surface-800 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-purple-500/20 text-purple-400">
              <Bell className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Alerting Notification Channels</h2>
              <p className="text-xs text-slate-400">Project: {projectName}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-surface-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Existing Configured Channels */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-300">Configured Notification Targets</label>
          {configs.length === 0 ? (
            <div className="p-4 rounded-xl bg-surface-950/60 border border-surface-800 text-center text-xs text-slate-500">
              No alert channels configured for this project yet.
            </div>
          ) : (
            configs.map((c) => (
              <div
                key={c.id}
                className="flex items-center justify-between gap-3 p-3 rounded-xl bg-surface-950/80 border border-surface-800 text-xs"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold uppercase tracking-wider text-purple-400 bg-purple-950/50 px-2 py-0.5 rounded border border-purple-800/60 font-mono text-[10px]">
                      {c.channel_type}
                    </span>
                    <span className="font-mono text-slate-300 text-xs">{c.masked_destination}</span>
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1 flex gap-2">
                    {c.notify_on_deployment_fail && <span>• Deploy Failures</span>}
                    {c.notify_on_health_fail && <span>• Downtime & Recovery</span>}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleTest(c.id)}
                    disabled={testingId === c.id}
                    className="px-2.5 py-1 rounded-lg bg-surface-800 hover:bg-surface-700 text-slate-300 hover:text-white flex items-center gap-1 transition-colors disabled:opacity-50"
                  >
                    {testSuccessId === c.id ? (
                      <span className="text-emerald-400 flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> Sent
                      </span>
                    ) : (
                      <>
                        <Send className="w-3.5 h-3.5" />
                        Test
                      </>
                    )}
                  </button>

                  {isAdmin && (
                    <button
                      onClick={() => handleDelete(c.id)}
                      className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-surface-800 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Add Channel Form */}
        {isAdmin && (
          <form onSubmit={handleAdd} className="p-4 rounded-xl bg-surface-950/80 border border-surface-800 space-y-3">
            <div className="text-xs font-semibold text-slate-200">Add Notification Channel</div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-[11px] font-medium text-slate-400 mb-1">Channel Type</label>
                <select
                  value={channelType}
                  onChange={(e: any) => setChannelType(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-lg bg-surface-900 border border-surface-700 text-xs text-slate-200"
                >
                  <option value="slack">Slack Webhook</option>
                  <option value="teams">Microsoft Teams</option>
                  <option value="webhook">Generic Webhook</option>
                  <option value="email">Email Address</option>
                </select>
              </div>

              <div className="sm:col-span-2">
                <label className="block text-[11px] font-medium text-slate-400 mb-1">
                  Destination URL / Email
                </label>
                <input
                  type="text"
                  required
                  placeholder={
                    channelType === 'email'
                      ? 'devops-alerts@company.com'
                      : 'https://hooks.slack.com/services/...'
                  }
                  value={destUrl}
                  onChange={(e) => setDestUrl(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-lg bg-surface-900 border border-surface-700 text-xs text-slate-200"
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-4 text-xs text-slate-300 pt-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={notifyDeploy}
                  onChange={(e) => setNotifyDeploy(e.target.checked)}
                  className="rounded bg-surface-900 border-surface-700 text-brand-500 focus:ring-0"
                />
                Deployment Failures
              </label>

              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={notifyHealth}
                  onChange={(e) => setNotifyHealth(e.target.checked)}
                  className="rounded bg-surface-900 border-surface-700 text-brand-500 focus:ring-0"
                />
                Downtime & Recovery
              </label>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="submit"
                className="px-3.5 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium flex items-center gap-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                Add Channel
              </button>
            </div>
          </form>
        )}

        <div className="flex justify-end pt-2">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-surface-800 hover:bg-surface-700 text-slate-200 text-xs font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
