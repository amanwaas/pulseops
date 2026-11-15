import React from 'react';
import { GitBranch, GitCommit, ArrowUpRight, Clock, AlertCircle } from 'lucide-react';
import { ProjectSummaryCard } from '../api/types';
import { StatusPill } from './StatusPill';
import { EnvironmentBadge } from './EnvironmentBadge';
import { formatDistanceToNow } from 'date-fns';

interface ProjectCardProps {
  project: ProjectSummaryCard;
  onClick: () => void;
}

export const ProjectCard: React.FC<ProjectCardProps> = ({ project, onClick }) => {
  const getDeploymentStatusBadge = (status: string) => {
    switch (status) {
      case 'success':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'failure':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
      case 'in_progress':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/20 animate-pulse';
      case 'cancelled':
        return 'bg-slate-500/10 text-slate-400 border-slate-500/20';
      default:
        return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    }
  };

  return (
    <div
      onClick={onClick}
      className="group relative rounded-2xl border border-surface-800 bg-surface-900/40 p-5 hover:bg-surface-900/80 hover:border-surface-700 transition-all duration-200 cursor-pointer shadow-sm hover:shadow-xl hover:shadow-black/40 flex flex-col justify-between"
    >
      <div>
        {/* Top Header: Title, Provider, Health Status */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs px-2 py-0.5 rounded font-mono uppercase tracking-wider bg-surface-800 text-slate-400 border border-surface-700">
                {project.provider}
              </span>
              <h3 className="text-base font-semibold text-slate-100 group-hover:text-brand-400 transition-colors flex items-center gap-1.5">
                {project.name}
                <ArrowUpRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity text-brand-400" />
              </h3>
            </div>
            <p className="text-xs font-mono text-slate-500 mt-1 truncate max-w-[220px]">
              {project.slug}
            </p>
          </div>

          <StatusPill status={project.overall_health} size="sm" />
        </div>

        {/* Latency & Incidents Metric Bar */}
        <div className="grid grid-cols-2 gap-2 my-4 p-2.5 rounded-xl bg-surface-950/60 border border-surface-800/80">
          <div>
            <div className="text-[11px] text-slate-400 font-medium">p95 Latency</div>
            <div className="text-sm font-mono font-bold text-slate-200">
              {project.p95_latency_ms !== null && project.p95_latency_ms !== undefined ? (
                <span className={project.p95_latency_ms > 500 ? 'text-amber-400' : 'text-emerald-400'}>
                  {project.p95_latency_ms} <span className="text-xs font-normal text-slate-500">ms</span>
                </span>
              ) : (
                <span className="text-slate-500">--</span>
              )}
            </div>
          </div>

          <div>
            <div className="text-[11px] text-slate-400 font-medium">Active Incidents</div>
            <div className="text-sm font-mono font-bold">
              {project.active_incidents_count > 0 ? (
                <span className="text-rose-400 flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" />
                  {project.active_incidents_count} Open
                </span>
              ) : (
                <span className="text-emerald-400">0 Active</span>
              )}
            </div>
          </div>
        </div>

        {/* Environments list */}
        <div className="flex flex-wrap gap-1.5 mb-4">
          {project.environments.map((env) => (
            <EnvironmentBadge key={env} environment={env} />
          ))}
        </div>
      </div>

      {/* Footer: Latest Deployment Snapshot */}
      <div className="pt-3 border-t border-surface-800/80">
        {project.latest_deployment ? (
          <div className="flex items-center justify-between text-xs text-slate-400">
            <div className="flex items-center gap-1.5 truncate max-w-[190px]">
              <GitCommit className="w-3.5 h-3.5 text-slate-500 shrink-0" />
              <span className="font-mono text-slate-300 font-medium">
                {project.latest_deployment.commit_sha}
              </span>
              <span className="truncate text-slate-500">
                {project.latest_deployment.commit_message || 'Release'}
              </span>
            </div>

            <span
              className={`px-2 py-0.5 rounded text-[10px] font-mono uppercase font-semibold border ${getDeploymentStatusBadge(
                project.latest_deployment.status
              )}`}
            >
              {project.latest_deployment.status}
            </span>
          </div>
        ) : (
          <div className="text-xs text-slate-500 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" />
            No deployments recorded yet
          </div>
        )}
      </div>
    </div>
  );
};
