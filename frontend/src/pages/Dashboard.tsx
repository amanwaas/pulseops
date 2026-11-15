import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Plus, Search, Filter, Activity, Server, AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import { ProjectSummaryCard, Incident } from '../api/types';
import { ProjectCard } from '../components/ProjectCard';
import { IncidentBanner } from '../components/IncidentBanner';
import { useAuth } from '../hooks/useAuth';

interface DashboardProps {
  onSelectProject: (projectId: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({ onSelectProject }) => {
  const { isAdmin } = useAuth();
  const [search, setSearch] = useState('');
  const [selectedEnv, setSelectedEnv] = useState<string>('all');
  const [showCreateModal, setShowCreateModal] = useState(false);

  // New Project Form State
  const [newName, setNewName] = useState('');
  const [newSlug, setNewSlug] = useState('');
  const [newRepo, setNewRepo] = useState('');
  const [newProvider, setNewProvider] = useState<'github' | 'gitlab'>('github');

  // React Query with auto-refresh every 30s as safety net alongside WebSockets
  const {
    data: projects = [],
    isLoading: isProjectsLoading,
    refetch: refetchProjects,
    isRefetching,
  } = useQuery<ProjectSummaryCard[]>({
    queryKey: ['overview-cards'],
    queryFn: () => api.projects.getOverviewCards(),
    refetchInterval: 30000,
  });

  const { data: openIncidents = [], refetch: refetchIncidents } = useQuery<Incident[]>({
    queryKey: ['incidents', 'open'],
    queryFn: () => api.incidents.list({ status: 'open' }),
    refetchInterval: 15000,
  });

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.projects.create({
        name: newName,
        slug: newSlug || newName.toLowerCase().replace(/[^a-z0-9]/g, '-'),
        repo_url: newRepo,
        provider: newProvider,
      });
      setShowCreateModal(false);
      setNewName('');
      setNewSlug('');
      setNewRepo('');
      refetchProjects();
    } catch (err) {
      console.error('Failed to create project', err);
    }
  };

  // Filter projects by search and environment
  const filteredProjects = projects.filter((p) => {
    const matchesSearch =
      search === '' ||
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.slug.toLowerCase().includes(search.toLowerCase()) ||
      p.repo_url.toLowerCase().includes(search.toLowerCase());

    const matchesEnv =
      selectedEnv === 'all' ||
      p.environments.some((env) => env.toLowerCase() === selectedEnv.toLowerCase());

    return matchesSearch && matchesEnv;
  });

  // Global Metric Calculations
  const totalProjects = projects.length;
  const operationalCount = projects.filter((p) => p.overall_health === 'UP').length;
  const criticalCount = projects.filter((p) => p.overall_health === 'DOWN').length;
  const systemUptimePct = totalProjects > 0 ? Math.round((operationalCount / totalProjects) * 100) : 100;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Active Incidents Banner */}
      <IncidentBanner incidents={openIncidents} onResolved={() => refetchIncidents()} />

      {/* Hero Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl border border-surface-800 bg-surface-900/40 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-slate-400">Total Monitored Projects</div>
            <div className="text-2xl font-bold font-mono text-white mt-1">{totalProjects}</div>
            <div className="text-[11px] text-slate-500 mt-1">Multi-Environment Services</div>
          </div>
          <div className="p-3 rounded-xl bg-surface-800 text-brand-400">
            <Server className="w-6 h-6" />
          </div>
        </div>

        <div className="p-5 rounded-2xl border border-surface-800 bg-surface-900/40 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-slate-400">System Availability</div>
            <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">{systemUptimePct}%</div>
            <div className="text-[11px] text-slate-500 mt-1">
              {operationalCount} of {totalProjects} Operational
            </div>
          </div>
          <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-400">
            <CheckCircle className="w-6 h-6" />
          </div>
        </div>

        <div className="p-5 rounded-2xl border border-surface-800 bg-surface-900/40 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-slate-400">Active Incidents</div>
            <div className={`text-2xl font-bold font-mono mt-1 ${criticalCount > 0 ? 'text-rose-400' : 'text-slate-200'}`}>
              {openIncidents.length}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">Requires Attention</div>
          </div>
          <div className={`p-3 rounded-xl ${criticalCount > 0 ? 'bg-rose-500/10 text-rose-400' : 'bg-surface-800 text-slate-400'}`}>
            <AlertTriangle className="w-6 h-6" />
          </div>
        </div>

        <div className="p-5 rounded-2xl border border-surface-800 bg-surface-900/40 shadow-sm flex items-center justify-between">
          <div>
            <div className="text-xs font-medium text-slate-400">Telemetry Stream</div>
            <div className="text-2xl font-bold font-mono text-indigo-400 mt-1">Real-time</div>
            <div className="text-[11px] text-slate-500 mt-1">WebSocket + Neon Postgres</div>
          </div>
          <div className="p-3 rounded-xl bg-indigo-500/10 text-indigo-400">
            <Activity className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Control Bar: Search, Filters, Refresh, Add Project */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex flex-1 items-center gap-3 max-w-lg">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              placeholder="Filter projects by name, slug, or repo..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 rounded-xl bg-surface-900 border border-surface-800 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500 transition-colors"
            />
          </div>

          <select
            value={selectedEnv}
            onChange={(e) => setSelectedEnv(e.target.value)}
            className="px-3 py-2 rounded-xl bg-surface-900 border border-surface-800 text-xs text-slate-300 focus:outline-none focus:border-brand-500 transition-colors"
          >
            <option value="all">All Environments</option>
            <option value="production">Production</option>
            <option value="staging">Staging</option>
            <option value="testing">Testing</option>
            <option value="development">Development</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => refetchProjects()}
            title="Refresh now"
            className="p-2 rounded-xl bg-surface-900 border border-surface-800 text-slate-400 hover:text-white hover:bg-surface-800 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${isRefetching ? 'animate-spin text-brand-400' : ''}`} />
          </button>

          {isAdmin && (
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold flex items-center gap-2 transition-all shadow-lg shadow-brand-600/20"
            >
              <Plus className="w-4 h-4" />
              New Project
            </button>
          )}
        </div>
      </div>

      {/* Projects Grid: Single Pane of Glass */}
      {isProjectsLoading ? (
        <div className="py-20 text-center font-mono text-sm text-slate-500">
          Loading project health metrics...
        </div>
      ) : filteredProjects.length === 0 ? (
        <div className="py-20 text-center rounded-2xl border border-surface-800 bg-surface-900/20 space-y-2">
          <Server className="w-10 h-10 text-slate-600 mx-auto" />
          <h3 className="text-base font-semibold text-slate-300">No projects found</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            {search ? 'No projects match your filter criteria.' : 'Get started by creating your first monitored project.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredProjects.map((p) => (
            <ProjectCard
              key={p.id}
              project={p}
              onClick={() => onSelectProject(p.id)}
            />
          ))}
        </div>
      )}

      {/* New Project Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-surface-800 bg-surface-900 p-6 shadow-2xl space-y-4">
            <h2 className="text-base font-bold text-white">Register New Monitored Project</h2>
            <form onSubmit={handleCreateProject} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Project Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Order Processing Service"
                  value={newName}
                  onChange={(e) => {
                    setNewName(e.target.value);
                    if (!newSlug) {
                      setNewSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]/g, '-'));
                    }
                  }}
                  className="w-full px-3 py-2 rounded-xl bg-surface-950 border border-surface-800 text-xs text-slate-200"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Slug Identifier</label>
                <input
                  type="text"
                  required
                  placeholder="order-processing-service"
                  value={newSlug}
                  onChange={(e) => setNewSlug(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-surface-950 border border-surface-800 text-xs font-mono text-slate-200"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">CI/CD Provider</label>
                <select
                  value={newProvider}
                  onChange={(e: any) => setNewProvider(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-surface-950 border border-surface-800 text-xs text-slate-200"
                >
                  <option value="github">GitHub Actions</option>
                  <option value="gitlab">GitLab CI/CD</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Repository URL</label>
                <input
                  type="url"
                  required
                  placeholder="https://github.com/myorg/order-processing"
                  value={newRepo}
                  onChange={(e) => setNewRepo(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-surface-950 border border-surface-800 text-xs text-slate-200"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3.5 py-2 rounded-xl text-xs text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-semibold"
                >
                  Create Project
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
