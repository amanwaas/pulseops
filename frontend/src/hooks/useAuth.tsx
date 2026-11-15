import { useState, useEffect, createContext, useContext, ReactNode } from 'react';
import { User, AuthResponse } from '../api/types';
import { api } from '../api/client';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, pass: string) => Promise<void>;
  register: (email: string, pass: string, role?: string) => Promise<void>;
  logout: () => void;
  isAdmin: boolean;
  isDeveloper: boolean;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem('pulseops_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('pulseops_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const verifyToken = async () => {
      if (token) {
        try {
          const me = await api.auth.getMe();
          setUser(me);
          localStorage.setItem('pulseops_user', JSON.stringify(me));
        } catch (e) {
          logout();
        }
      }
      setIsLoading(false);
    };
    verifyToken();
  }, [token]);

  const login = async (email: string, pass: string) => {
    const res: AuthResponse = await api.auth.login(email, pass);
    setToken(res.access_token);
    setUser(res.user);
    localStorage.setItem('pulseops_token', res.access_token);
    localStorage.setItem('pulseops_user', JSON.stringify(res.user));
  };

  const register = async (email: string, pass: string, role = 'developer') => {
    await api.auth.register(email, pass, role);
    await login(email, pass);
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('pulseops_token');
    localStorage.removeItem('pulseops_user');
  };

  const isAdmin = user?.role === 'admin';
  const isDeveloper = user?.role === 'admin' || user?.role === 'developer';
  const isAuthenticated = !!token && !!user;

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        register,
        logout,
        isAdmin,
        isDeveloper,
        isAuthenticated,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
