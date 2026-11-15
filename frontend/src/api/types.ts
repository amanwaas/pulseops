export type Environment = 'development' | 'testing' | 'staging' | 'production';
export type HealthStatus = 'UP' | 'DOWN' | 'DEGRADED' | 'UNKNOWN';
export type DeploymentStatus = 'queued' | 'in_progress' | 'success' | 'failure' | 'cancelled';
export type UserRole = 'admin' | 'developer' | 'viewer';
export type AlertChannel = 'slack' | 'teams' | 'email' | 'webhook';

export interface User {
  id: string;
  email: string;
  role: UserRole;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ProjectSummaryCard {
  id: string;
  name: string;
  slug: string;
  repo_url: string;
  provider: 'github' | 'gitlab';
  environments: Environment[];
  latest_deployment?: {
    id: string;
    environment: Environment;
    commit_sha: string;
    commit_message?: string;
    status: DeploymentStatus;
    duration_seconds: number;
    created_at: string;
  };
  overall_health: HealthStatus;
  p95_latency_ms?: number;
  active_incidents_count: number;
  updated_at: string;
}

export interface ProjectDetail {
  id: string;
  name: string;
  slug: string;
  repo_url: string;
  provider: 'github' | 'gitlab';
  webhook_url: string;
  masked_secret: string;
  created_at: string;
  updated_at: string;
}

export interface Deployment {
  id: string;
  project_id: string;
  environment: Environment;
  commit_sha: string;
  short_commit_sha: string;
  commit_message?: string;
  branch: string;
  author?: string;
  status: DeploymentStatus;
  duration_seconds: number;
  pipeline_id?: string;
  pipeline_url?: string;
  created_at: string;
}

export interface HealthTarget {
  id: string;
  project_id: string;
  environment: Environment;
  endpoint_url: string;
  check_interval_seconds: number;
  timeout_seconds: number;
  is_active: boolean;
  consecutive_failures: number;
  last_status: HealthStatus;
  last_checked_at?: string;
  created_at: string;
}

export interface LatencyPoint {
  timestamp: string;
  latency_ms: number;
  is_up: boolean;
  status_code?: number;
}

export interface DeploymentAnnotation {
  timestamp: string;
  environment: Environment;
  commit_sha: string;
  short_sha: string;
  author?: string;
  status: DeploymentStatus;
  duration_seconds: number;
}

export interface LatencyAndTimelineResponse {
  target_id: string;
  environment: Environment;
  p95_latency_ms: number;
  avg_latency_ms: number;
  uptime_percentage: number;
  points: LatencyPoint[];
  deployments: DeploymentAnnotation[];
}

export interface Incident {
  id: string;
  target_id: string;
  project_name?: string;
  environment?: string;
  endpoint_url?: string;
  started_at: string;
  resolved_at?: string;
  status: 'open' | 'resolved';
  failure_reason: string;
  consecutive_failures: number;
}

export interface AlertConfig {
  id: string;
  project_id: string;
  channel_type: AlertChannel;
  masked_destination: string;
  notify_on_deployment_fail: boolean;
  notify_on_health_fail: boolean;
  created_at: string;
}
