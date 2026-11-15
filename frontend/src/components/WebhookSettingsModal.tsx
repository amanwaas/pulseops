import React, { useState } from 'react';
import { X, Copy, Check, RefreshCw, Key, Link as LinkIcon, ShieldAlert } from 'lucide-react';
import { ProjectDetail } from '../api/types';
import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';

interface WebhookSettingsModalProps {
  project: ProjectDetail;
  isOpen: boolean;
  onClose: () => void;
  onSecretRegenerated: () => void;
}

export const WebhookSettingsModal: React.FC<WebhookSettingsModalProps> = ({
  project,
  isOpen,
  onClose,
  onSecretRegenerated,
}) => {
  const { isAdmin } = useAuth();
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [copiedSecret, setCopiedSecret] = useState(false);
  const [revealedSecret, setRevealedSecret] = useState<string | null>(null);
  const [isRegenerating, setIsRegenerating] = useState(false);

  if (!isOpen) return null;

  const handleCopyUrl = () => {
    navigator.clipboard.writeText(project.webhook_url);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  };

  const handleCopySecret = () => {
    navigator.clipboard.writeText(revealedSecret || project.masked_secret);
    setCopiedSecret(true);
    setTimeout(() => setCopiedSecret(false), 2000);
  };

  const handleRegenerate = async () => {
    if (!confirm('Regenerating this signing secret will immediately invalidate your existing GitHub/GitLab webhook configurations. Proceed?')) {
      return;
    }
    setIsRegenerating(true);
    try {
      const res = await api.projects.regenerateSecret(project.id);
      setRevealedSecret(res.new_webhook_secret);
      onSecretRegenerated();
    } catch (err) {
      console.error('Failed to regenerate secret', err);
    } finally {
      setIsRegenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-xl rounded-2xl border border-surface-800 bg-surface-900 p-6 shadow-2xl space-y-5">
        <div className="flex items-center justify-between border-b border-surface-800 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-brand-500/20 text-brand-400">
              <Key className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">CI/CD Webhook Integration</h2>
              <p className="text-xs text-slate-400">Project: {project.name}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-surface-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Webhook URL Box */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
            <LinkIcon className="w-3.5 h-3.5 text-brand-400" />
            Webhook Ingestion Endpoint URL
          </label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              readOnly
              value={project.webhook_url}
              className="w-full px-3 py-2 rounded-xl bg-surface-950 border border-surface-800 text-xs font-mono text-slate-200 select-all"
            />
            <button
              onClick={handleCopyUrl}
              className="px-3 py-2 rounded-xl bg-surface-800 hover:bg-surface-700 text-slate-300 hover:text-white text-xs font-medium flex items-center gap-1 transition-colors"
            >
              {copiedUrl ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Signing Secret Box */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
              <Key className="w-3.5 h-3.5 text-amber-400" />
              HMAC Signing Secret (Encrypted at Rest)
            </label>
            {isAdmin && (
              <button
                onClick={handleRegenerate}
                disabled={isRegenerating}
                className="text-[11px] text-rose-400 hover:text-rose-300 flex items-center gap-1 hover:underline"
              >
                <RefreshCw className={`w-3 h-3 ${isRegenerating ? 'animate-spin' : ''}`} />
                Regenerate Secret
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            <input
              type="text"
              readOnly
              value={revealedSecret || project.masked_secret}
              className={`w-full px-3 py-2 rounded-xl bg-surface-950 border border-surface-800 text-xs font-mono select-all ${
                revealedSecret ? 'text-amber-300 font-semibold border-amber-500/50' : 'text-slate-400'
              }`}
            />
            {revealedSecret && (
              <button
                onClick={handleCopySecret}
                className="px-3 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-medium flex items-center gap-1"
              >
                {copiedSecret ? <Check className="w-4 h-4 text-emerald-300" /> : <Copy className="w-4 h-4" />}
              </button>
            )}
          </div>
          {revealedSecret && (
            <p className="text-[11px] text-amber-400/90 font-medium">
              ⚠️ Copy this secret now into GitHub/GitLab Secrets! It will not be shown again.
            </p>
          )}
        </div>

        {/* Integration Instructions */}
        <div className="p-3.5 rounded-xl bg-surface-950/80 border border-surface-800 text-xs text-slate-300 space-y-2">
          <div className="font-semibold text-slate-200">
            {project.provider === 'github' ? 'GitHub Actions Integration' : 'GitLab CI/CD Integration'}
          </div>
          {project.provider === 'github' ? (
            <p className="text-slate-400 leading-relaxed">
              In your GitHub Repository &gt; <strong>Settings &gt; Webhooks</strong>, add the Webhook URL above, set Content type to <code className="text-brand-300 bg-surface-900 px-1 py-0.5 rounded">application/json</code>, enter your Secret, and check <strong>Workflow runs</strong> and <strong>Deployments</strong>. GitHub will automatically sign all requests with <code className="text-brand-300">X-Hub-Signature-256</code>.
            </p>
          ) : (
            <p className="text-slate-400 leading-relaxed">
              In your GitLab Project &gt; <strong>Settings &gt; Webhooks</strong>, paste the Webhook URL, enter your Secret Token in the <strong>Secret token</strong> field, and select <strong>Pipeline events</strong> and <strong>Deployment events</strong>.
            </p>
          )}
        </div>

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
