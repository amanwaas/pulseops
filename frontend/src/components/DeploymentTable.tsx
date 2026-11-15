import React, { useState } from 'react';
import { GitCommit, GitBranch, ExternalLink, Search, Clock, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { Deployment, Environment } from '../api/types';
import { EnvironmentBadge } from './EnvironmentBadge';
import { formatDistanceToNow, parseISO } from 'date-fns';

interface DeploymentTableProps {
  deployments: Deployment[];
  repoUrl?: string;
}

export const DeploymentTable: React.FC<DeploymentTableProps> = ({ deployments, repoUrl }) => {
  const [search, setSearch] = useState('');
  const [selectedEnv, setSelectedEnv] = useState<string>('all');

  const filteredDeployments = deployments.filter((d) => {
    const matchesEnv = selectedEnv === 'all' || d.environment.toLowerCase() === selectedEnv.toLowerCase();
    const matchesSearch =
      search === '' ||
      d.commit_sha.toLowerCase().includes(search.toLowerCase()) ||
      d.branch.toLowerCase().includes(search.toLowerCase()) ||
      (d.commit_message && d.commit_message.toLowerCase().includes(search.toLowerCase())) ||
      (d.author && d.author.toLowerCase().includes(search.toLowerCase()));
    return matchesEnv && matchesSearch;
  });

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
      case 'failure':
        return <XCircle className="w-4 h-4 text-rose-400" />;
      case 'in_progress':
        return <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />;
      default:
        return <Clock className="w-4 h-4 text-slate-400" />;
    }
  };

  const getCommitUrl = (sha: string) => {
    if (!repoUrl) return null;
    return `${repoUrl.replace(/\/$/, '')}/commit/${sha}`;
  };

  return (
    <div className="rounded-2xl border border-surface-800 bg-surface-900/40 p-5 shadow-sm">
      {/* Table Filters Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
          <span>Deployment History</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-surface-800 text-slate-400 border border-surface-700 font-mono">
            {filteredDeployments.length}
          </span>
        </h3>

        <div className="flex items-center gap-2">
          {/* Search Box */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="Search commit, branch, author..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-1.5 rounded-xl bg-surface-950/80 border border-surface-800 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500 transition-colors w-48 sm:w-60"
            />
          </div>

          {/* Environment Filter */}
          <select
            value={selectedEnv}
            onChange={(e) => setSelectedEnv(e.target.value)}
            className="px-3 py-1.5 rounded-xl bg-surface-950/80 border border-surface-800 text-xs text-slate-300 focus:outline-none focus:border-brand-500 transition-colors"
          >
            <option value="all">All Envs</option>
            <option value="production">Production</option>
            <option value="staging">Staging</option>
            <option value="testing">Testing</option>
            <option value="development">Development</option>
          </select>
        </div>
      </div>

      {/* Table Surface */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-surface-800/80 text-slate-400 font-medium">
              <th className="pb-3 pl-2">Status</th>
              <th className="pb-3">Environment</th>
              <th className="pb-3">Commit & Message</th>
              <th className="pb-3">Branch</th>
              <th className="pb-3">Author</th>
              <th className="pb-3">Duration</th>
              <th className="pb-3">Age</th>
              <th className="pb-3 pr-2 text-right">Links</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-800/50">
            {filteredDeployments.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-slate-500">
                  No deployments matching current filters.
                </td>
              </tr>
            ) : (
              filteredDeployments.map((d) => {
                const commitUrl = getCommitUrl(d.commit_sha);
                return (
                  <tr key={d.id} className="hover:bg-surface-800/30 transition-colors">
                    <td className="py-3 pl-2">
                      <div className="flex items-center gap-1.5">
                        {getStatusIcon(d.status)}
                        <span className="font-mono uppercase text-[11px] font-semibold text-slate-300">
                          {d.status}
                        </span>
                      </div>
                    </td>

                    <td className="py-3">
                      <EnvironmentBadge environment={d.environment} />
                    </td>

                    <td className="py-3 max-w-[240px]">
                      <div className="flex items-center gap-1.5">
                        {commitUrl ? (
                          <a
                            href={commitUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="font-mono font-medium text-brand-400 hover:text-brand-300 hover:underline flex items-center gap-0.5"
                          >
                            {d.short_commit_sha}
                            <ExternalLink className="w-2.5 h-2.5 opacity-60" />
                          </a>
                        ) : (
                          <span className="font-mono text-slate-300">{d.short_commit_sha}</span>
                        )}
                        <span className="truncate text-slate-400" title={d.commit_message || ''}>
                          {d.commit_message || 'Deploy'}
                        </span>
                      </div>
                    </td>

                    <td className="py-3">
                      <div className="flex items-center gap-1 text-slate-300 font-mono">
                        <GitBranch className="w-3 h-3 text-slate-500" />
                        <span className="truncate max-w-[120px]">{d.branch}</span>
                      </div>
                    </td>

                    <td className="py-3 text-slate-300">{d.author || 'CI'}</td>

                    <td className="py-3 font-mono text-slate-400">
                      {d.duration_seconds > 0 ? `${d.duration_seconds}s` : '--'}
                    </td>

                    <td className="py-3 text-slate-400">
                      {formatDistanceToNow(parseISO(d.created_at), { addSuffix: true })}
                    </td>

                    <td className="py-3 pr-2 text-right">
                      {d.pipeline_url && (
                        <a
                          href={d.pipeline_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-800 hover:bg-surface-700 text-slate-300 hover:text-white transition-colors text-[11px]"
                        >
                          CI Run
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
