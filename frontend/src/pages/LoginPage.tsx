import React, { useState } from 'react';
import { Activity, ShieldCheck, Lock, Mail, ArrowRight, AlertCircle, UserPlus, LogIn } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

export const LoginPage: React.FC = () => {
  const { login, register } = useAuth();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      if (isRegister) {
        await register(email, password);
      } else {
        await login(email, password);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Authentication failed. Please check your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-950 flex flex-col justify-center items-center px-4 sm:px-6 lg:px-8 py-12 relative overflow-hidden">
      {/* Background Ambient Glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-brand-600/10 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md space-y-8 relative z-10">
        {/* Brand Header */}
        <div className="text-center">
          <div className="inline-flex w-12 h-12 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-400 items-center justify-center shadow-xl shadow-brand-500/20 mb-3">
            <Activity className="w-7 h-7 text-white" />
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-white">
            {isRegister ? 'Create PulseOps Account' : 'Sign in to PulseOps'}
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Deployment & Application Health Monitoring Platform
          </p>
        </div>

        {/* Auth Card */}
        <div className="rounded-3xl border border-surface-800 bg-surface-900/60 p-7 shadow-2xl backdrop-blur-xl space-y-5">
          {/* Mode Switcher Tabs */}
          <div className="grid grid-cols-2 p-1 rounded-xl bg-surface-950 border border-surface-800 text-xs">
            <button
              type="button"
              onClick={() => {
                setIsRegister(false);
                setError(null);
              }}
              className={`py-2 rounded-lg font-medium transition-colors flex items-center justify-center gap-1.5 ${
                !isRegister ? 'bg-surface-800 text-white shadow-sm' : 'text-slate-400 hover:text-white'
              }`}
            >
              <LogIn className="w-3.5 h-3.5" />
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setIsRegister(true);
                setError(null);
              }}
              className={`py-2 rounded-lg font-medium transition-colors flex items-center justify-center gap-1.5 ${
                isRegister ? 'bg-surface-800 text-white shadow-sm' : 'text-slate-400 hover:text-white'
              }`}
            >
              <UserPlus className="w-3.5 h-3.5" />
              Register
            </button>
          </div>

          {error && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Work Email</label>
              <div className="relative">
                <Mail className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="email"
                  required
                  placeholder="admin@yourdomain.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-surface-950 border border-surface-800 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-brand-500 transition-colors"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  type="password"
                  required
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-surface-950 border border-surface-800 text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-brand-500 transition-colors"
                />
              </div>
              {isRegister && (
                <p className="text-[11px] text-slate-500 mt-1">Minimum 8 characters.</p>
              )}
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white font-medium text-sm flex items-center justify-center gap-2 transition-all shadow-lg shadow-brand-600/30 disabled:opacity-50 mt-2"
            >
              {isLoading
                ? isRegister
                  ? 'Creating Account...'
                  : 'Signing in...'
                : isRegister
                ? 'Create Account'
                : 'Sign In to Dashboard'}
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          {isRegister && (
            <p className="text-[11px] text-center text-slate-400">
              The first account created automatically receives <span className="text-brand-400 font-semibold">Admin</span> privileges.
            </p>
          )}
        </div>

        {/* Security Footer Notice */}
        <div className="text-center text-xs text-slate-500 flex items-center justify-center gap-1.5">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Encrypted with AES-256-GCM & Neon PostgreSQL 16</span>
        </div>
      </div>
    </div>
  );
};
