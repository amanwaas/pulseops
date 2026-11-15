import React, { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { Navbar } from './components/Navbar';
import { Dashboard } from './pages/Dashboard';
import { ProjectDetail } from './pages/ProjectDetail';
import { IncidentsPage } from './pages/IncidentsPage';
import { LoginPage } from './pages/LoginPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 10000,
    },
  },
});

const AppContent: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  const [currentTab, setCurrentTab] = useState<'projects' | 'incidents' | 'deployments'>('projects');
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-surface-950 flex items-center justify-center font-mono text-xs text-slate-500">
        Initializing PulseOps Session...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <div className="min-h-screen bg-surface-950 text-slate-100 flex flex-col">
      <Navbar
        currentTab={currentTab}
        onTabChange={(tab) => {
          setCurrentTab(tab);
          setSelectedProjectId(null);
        }}
      />

      <main className="flex-1">
        {selectedProjectId ? (
          <ProjectDetail
            projectId={selectedProjectId}
            onBack={() => setSelectedProjectId(null)}
          />
        ) : currentTab === 'projects' ? (
          <Dashboard onSelectProject={(id) => setSelectedProjectId(id)} />
        ) : (
          <IncidentsPage />
        )}
      </main>

      <footer className="border-t border-surface-900 py-6 text-center text-xs text-slate-500 font-mono">
        PulseOps Platform • High-Frequency Uptime & CI/CD Release Telemetry • Neon Postgres 16
      </footer>
    </div>
  );
};

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
