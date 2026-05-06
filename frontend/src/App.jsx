import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './components/Layout';
import Login from './pages/Login';
import Registro from './pages/Registro';
import Dashboard from './pages/Dashboard';
import Reclamacoes from './pages/Reclamacoes';
import NovaReclamacao from './pages/NovaReclamacao';
import ReclamacaoDetalhe from './pages/ReclamacaoDetalhe';
import Sessoes from './pages/Sessoes';
import Acordos from './pages/Acordos';

function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/registro" element={<Registro />} />

      {/* Protected routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout>
              <Dashboard />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/reclamacoes"
        element={
          <ProtectedRoute>
            <Layout>
              <Reclamacoes />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/reclamacoes/nova"
        element={
          <ProtectedRoute>
            <Layout>
              <NovaReclamacao />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/reclamacoes/:id"
        element={
          <ProtectedRoute>
            <Layout>
              <ReclamacaoDetalhe />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/sessoes"
        element={
          <ProtectedRoute>
            <Layout>
              <Sessoes />
            </Layout>
          </ProtectedRoute>
        }
      />
      <Route
        path="/acordos"
        element={
          <ProtectedRoute>
            <Layout>
              <Acordos />
            </Layout>
          </ProtectedRoute>
        }
      />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
