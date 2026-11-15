import React from 'react';
import { Activity, ShieldCheck, Radio, LogOut, User as UserIcon } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useWebSocket } from '../hooks/useWebSocket';

interface NavbarProps {
  currentTab: 'projects' | 'incidents' | 'deployments';
  onTabChange: (tab: 'projects' | 'incidents' | 'deployments') => void;
  activeIncidentsCount?: number;
}

export const Navbar: React.FC<NavbarProps> = ({ currentTab, onTabChange, activeIncidentsCount = 0 }) => {
  const { user, logout } = useAuth();
  const { connectionState } = useWebSocket();

  const getConnectionBadge = () => {
    switch (connectionState) {
      case 'CONNECTED':
        return {
          label: 'LIVE SYNC',
          color: 'bg-emerald-500',
          ping: 'bg-emerald-400',
        };
      case 'CONNECTING':
        return {
          label: 'CONNECTING',
          color: 'bg-amber-500',
          ping: 'bg-amber-400',
        };
      case 'RECONNECTING':
        return {
          label: 'RECONNECTING',
          color: 'bg-rose-500',
          ping: 'bg-rose-400',
        };
      case 'DISCONNECTED':
      default:
        return {
          label: 'OFFLINE',
          color: 'bg-slate-500',
          ping: null,
        };
    }
  };

  const badge = getConnectionBadge();

  return (
    <header className="sticky top-0 z-40 w-full border-b border-surface-800 bg-surface-950/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2.5 cursor-pointer" onClick={() => onTabChange('projects')}>
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-400 flex items-center justify-center shadow-lg shadow-brand-500/20">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-white flex items-center gap-1.5">
                PulseOps
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-brand-500/20 text-brand-300 border border-brand-500/30">
                  v1.0
                </span>
              </span>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center gap-1">
            <button
              onClick={() => onTabChange('projects')}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                currentTab === 'projects'
                  ? 'bg-surface-800 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-surface-900'
              }`}
            >
              Projects
            </button>
            <button
              onClick={() => onTabChange('incidents')}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 ${
                currentTab === 'incidents'
                  ? 'bg-surface-800 text-white shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-surface-900'
              }`}
            >
              Incidents
              {activeIncidentsCount > 0 && (
                <span className="w-5 h-5 rounded-full bg-rose-500/20 border border-rose-500/40 text-rose-400 text-xs flex items-center justify-center font-bold">
                  {activeIncidentsCount}
                </span>
              )}
            </button>
          </nav>
        </div>

        {/* Status indicator & User Menu */}
        <div className="flex items-center gap-4">
          {/* Real-time WebSocket connection badge */}
          <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full border border-surface-800 bg-surface-900/60 text-xs text-slate-300">
            <span className="relative flex h-2 w-2">
              {badge.ping && (
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${badge.ping} opacity-75`} />
              )}
              <span className={`relative inline-flex rounded-full h-2 w-2 ${badge.color}`} />
            </span>
            <span className="font-mono text-[11px]">{badge.label}</span>
          </div>

          {/* User info */}
          {user && (
            <div className="flex items-center gap-3 pl-2 border-l border-surface-800">
              <div className="text-right hidden sm:block">
                <div className="text-xs font-medium text-slate-200">{user.email}</div>
                <div className="text-[10px] uppercase font-mono text-brand-400">{user.role}</div>
              </div>
              <button
                onClick={logout}
                title="Log out"
                className="p-2 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-surface-800 transition-colors"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
