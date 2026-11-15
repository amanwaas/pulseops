import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, ExternalLink, Settings, Bell, Key, RefreshCw, Trash2 } from 'lucide-react';
import { api } from '../api/client';
import {
  ProjectDetail as ProjectDetailType,
  Deployment,
  HealthTarget,
  LatencyAndTimelineResponse,
  AlertConfig,
} from '../api/types';
import { LatencyTimelineChart } from '../components/LatencyTimelineChart';
import { DeploymentTable } from '../components/DeploymentTable';
import { HealthTargetsList } from '../components/HealthTargetsList';
import { WebhookSettingsModal } from '../components/WebhookSettingsModal';
import { AlertConfigModal } from '../components/AlertConfigModal';
import { useAuth } from '../hooks/useAuth';

interface ProjectDetailProps {
  projectId: string;
  onBack: () => void;
}

export const ProjectDetail: React.FC<ProjectDetailProps> = ({ projectId, onBack }) => {
  const { isAdmin } = useAuth();
  const [selectedTargetId, setSelectedTargetId] = useState<string | null>(null);
  const [selectedWindow, setSelectedWindow] = useState<'1h' | '24h' | '7d'>('24h');
  const [isWebhookModalOpen, setIsWebhookModalOpen] = useState(false);
  const [isAlertModalOpen, setIsAlertModalOpen] = useState(false);

  // 1. Fetch Project Details
  const { data: project, refetch: refetchProject } = useQuery<ProjectDetailType>({
    queryKey: ['project', projectId],
    queryFn: () => api.projects.get(projectId),
  });

  // 2. Fetch Health Targets
  const { data: targets = [], refetch: refetchTargets } = useQuery<HealthTarget[]>({
    queryKey: ['health-targets', projectId],
    queryFn: () => api.health.listTargets({ project_id: projectId }),
    refetchInterval: 15000,
  });

  // Automatically select the first target (default to production)
  useEffect(() => {
    if (targets.length > 0 && !selectedTargetId) {
      const prodTarget = targets.find((t) => t.environment === 'production');
      setSelectedTargetId(prodTarget ? prodTarget.id : targets[0].id);
    }
  }, [targets, selectedTargetId]);

  // 3. Fetch Deployments
  const { data: deployments = [], refetch: refetchDeployments } = useQuery<Deployment[]>({
    queryKey: ['deployments', projectId],
    queryFn: () => api.deployments.list({ project_id: projectId, limit: 100 }),
    refetchInterval: 15000,
  });

  // 4. Fetch Latency Timeline & Deployment Annotations for Selected Target
  const {
    data: timelineData,
    isLoading: isTimelineLoading,
    refetch: refetchTimeline,
  } = useQuery<LatencyAndTimelineResponse>({
    queryKey: ['target-timeline', selectedTargetId, selectedWindow],
    queryFn: () => api.health.getTimeline(selectedTargetId!, selectedWindow),
    enabled: !!selectedTargetId,
    refetchInterval: 20000,
  });

  // 5. Fetch Alert Configurations
  const { data: alertConfigs = [], refetch: refetchAlerts } = useQuery<AlertConfig[]>({
    queryKey: ['alerts', projectId],
    queryFn: () => api.alerts.list(projectId),
  });

  const handleDeleteProject = async () => {
    if (!confirm(`Are you sure you want to permanently delete project "${project?.name}"?`)) {
      return;
    }
    try {
      await api.projects.delete(projectId);
      onBack();
    } catch (err) {
      console.error('Failed to delete project', err);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Top Navigation & Project Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-surface-800">
        <div>
          <button
            onClick={onBack}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors mb-3"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to All Projects
          </button>

          <div className="flex items-center gap-3">
            <span className="text-xs px-2 py-0.5 rounded font-mono uppercase tracking-wider bg-surface-800 text-slate-400 border border-surface-700">
              {project?.provider || 'CI/CD'}
            </span>
            <h1 className="text-2xl font-bold text-white tracking-tight">{project?.name || 'Project'}</h1>
            {project?.repo_url && (
              <a
                href={project.repo_url}
                target="_blank"
                rel="noopener noreferrer"
                className="p-1.5 rounded-lg bg-surface-900 hover:bg-surface-800 text-slate-400 hover:text-white transition-colors"
                title="Open Repository"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            )}
          </div>
          <p className="text-xs font-mono text-slate-500 mt-1">ID: {projectId}</p>
        </div>

        {/* Action Buttons: Webhooks, Alerts, Delete */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setIsWebhookModalOpen(true)}
            className="px-3.5 py-2 rounded-xl bg-surface-900 hover:bg-surface-800 border border-surface-800 text-xs font-medium text-slate-200 hover:text-white flex items-center gap-2 transition-colors shadow-sm"
          >
            <Key className="w-3.5 h-3.5 text-amber-400" />
            Webhook Config
          </button>

          <button
            onClick={() => setIsAlertModalOpen(true)}
            className="px-3.5 py-2 rounded-xl bg-surface-900 hover:bg-surface-800 border border-surface-800 text-xs font-medium text-slate-200 hover:text-white flex items-center gap-2 transition-colors shadow-sm"
          >
            <Bell className="w-3.5 h-3.5 text-purple-400" />
            Alert Channels
            {alertConfigs.length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full bg-purple-500/20 text-purple-300 font-mono text-[10px]">
                {alertConfigs.length}
              </span>
            )}
          </button>

          {isAdmin && (
            <button
              onClick={handleDeleteProject}
              className="p-2 rounded-xl bg-surface-900 hover:bg-rose-950/50 border border-surface-800 hover:border-rose-800/60 text-slate-400 hover:text-rose-400 transition-colors"
              title="Delete Project"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Target Monitoring Endpoints */}
      <HealthTargetsList
        targets={targets}
        projectId={projectId}
        onRefresh={() => {
          refetchTargets();
          refetchTimeline();
        }}
        selectedTargetId={selectedTargetId}
        onSelectTarget={(id) => setSelectedTargetId(id)}
      />

      {/* Latency Graph with Overlaid Deployment Annotations */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold text-slate-100">
              Application Latency & Deployment Correlation
            </h3>
            <p className="text-xs text-slate-400">
              Vertical markers overlay deployments on response times, showing immediate impact of code releases.
            </p>
          </div>
          <button
            onClick={() => refetchTimeline()}
            title="Refresh graph"
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-surface-800 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>

        <LatencyTimelineChart
          data={timelineData}
          isLoading={isTimelineLoading}
          selectedWindow={selectedWindow}
          onWindowChange={(w) => setSelectedWindow(w)}
        />
      </div>

      {/* Deployment History Table */}
      <DeploymentTable deployments={deployments} repoUrl={project?.repo_url} />

      {/* Modals */}
      {project && (
        <WebhookSettingsModal
          project={project}
          isOpen={isWebhookModalOpen}
          onClose={() => setIsWebhookModalOpen(false)}
          onSecretRegenerated={() => refetchProject()}
        />
      )}

      {project && (
        <AlertConfigModal
          projectId={projectId}
          projectName={project.name}
          configs={alertConfigs}
          isOpen={isAlertModalOpen}
          onClose={() => setIsAlertModalOpen(false)}
          onRefresh={() => refetchAlerts()}
        />
      )}
    </div>
  );
};
