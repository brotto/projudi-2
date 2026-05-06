import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import api from '../api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('juizo_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState(() => localStorage.getItem('juizo_token'));
  const [loading, setLoading] = useState(false);

  const isAuthenticated = !!token;

  const login = useCallback(async (email, senha) => {
    setLoading(true);
    try {
      const res = await api.post('/auth/login', { email, senha });
      const { access_token } = res.data;
      localStorage.setItem('juizo_token', access_token);
      setToken(access_token);

      // Fetch user info
      const meRes = await api.get('/auth/me');
      const userData = meRes.data;
      localStorage.setItem('juizo_user', JSON.stringify(userData));
      setUser(userData);
      return { success: true };
    } catch (err) {
      return {
        success: false,
        error: err.response?.data?.detail || 'Erro ao fazer login',
      };
    } finally {
      setLoading(false);
    }
  }, []);

  const register = useCallback(async (nome, email, senha, perfil) => {
    setLoading(true);
    try {
      const res = await api.post('/auth/registrar', { nome, email, senha, perfil });
      const { token: accessToken, usuario } = res.data;
      if (accessToken) {
        localStorage.setItem('juizo_token', accessToken);
        setToken(accessToken);
        localStorage.setItem('juizo_user', JSON.stringify(usuario));
        setUser(usuario);
      }
      return { success: true, data: res.data };
    } catch (err) {
      return {
        success: false,
        error: err.response?.data?.detail || 'Erro ao registrar',
      };
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('juizo_token');
    localStorage.removeItem('juizo_user');
    setToken(null);
    setUser(null);
  }, []);

  // On mount, verify token still valid
  useEffect(() => {
    if (token && !user) {
      api.get('/auth/me')
        .then((res) => {
          setUser(res.data);
          localStorage.setItem('juizo_user', JSON.stringify(res.data));
        })
        .catch(() => {
          logout();
        });
    }
  }, [token, user, logout]);

  return (
    <AuthContext.Provider
      value={{ user, token, isAuthenticated, loading, login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
