import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  LayoutDashboard,
  FileText,
  PlusCircle,
  Calendar,
  Handshake,
  LogOut,
  Menu,
  X,
  Scale,
  User,
  ChevronDown,
} from 'lucide-react';

const PERFIL_LABELS = {
  PARTE: 'Parte',
  ADVOGADO: 'Advogado',
  SECRETARIA: 'Secretaria CEJUSC',
  CONCILIADOR: 'Conciliador',
  MEDIADOR: 'Mediador',
  JUIZ_COORDENADOR: 'Juiz Coordenador',
  MP: 'Ministerio Publico',
};

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { to: '/reclamacoes', icon: FileText, label: 'Reclamacoes' },
    ...(user?.perfil === 'PARTE'
      ? [{ to: '/reclamacoes/nova', icon: PlusCircle, label: 'Nova Reclamacao' }]
      : []),
    { to: '/sessoes', icon: Calendar, label: 'Sessoes' },
    { to: '/acordos', icon: Handshake, label: 'Acordos' },
  ];

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <div className="flex h-screen bg-navy-50">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 transform bg-navy-800 transition-transform duration-200 ease-in-out lg:relative lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex h-full flex-col">
          {/* Logo */}
          <div className="flex items-center gap-3 px-6 py-5 border-b border-navy-700">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600">
              <Scale className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white tracking-tight">Juizo</h1>
              <p className="text-[10px] text-navy-400 uppercase tracking-widest">CEJUSC-Pre</p>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="ml-auto lg:hidden text-navy-400 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive(item.to)
                    ? 'bg-blue-600/20 text-blue-400'
                    : 'text-navy-300 hover:bg-navy-700 hover:text-white'
                }`}
              >
                <item.icon className="h-5 w-5 shrink-0" />
                {item.label}
              </Link>
            ))}
          </nav>

          {/* User section at bottom */}
          <div className="border-t border-navy-700 p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-navy-600">
                <User className="h-4 w-4 text-navy-300" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">
                  {user?.nome || 'Usuario'}
                </p>
                <p className="text-xs text-navy-400 truncate">
                  {PERFIL_LABELS[user?.perfil] || user?.perfil}
                </p>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Header */}
        <header className="sticky top-0 z-20 flex items-center gap-4 bg-white border-b border-navy-200 px-4 py-3 lg:px-6">
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden text-navy-600 hover:text-navy-900"
          >
            <Menu className="h-6 w-6" />
          </button>

          <div className="flex-1" />

          {/* User dropdown */}
          <div className="relative">
            <button
              onClick={() => setUserMenuOpen(!userMenuOpen)}
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-navy-600 hover:bg-navy-100 transition-colors"
            >
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-navy-100">
                <User className="h-3.5 w-3.5 text-navy-600" />
              </div>
              <span className="hidden sm:block font-medium">{user?.nome}</span>
              <ChevronDown className="h-4 w-4" />
            </button>

            {userMenuOpen && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setUserMenuOpen(false)}
                />
                <div className="absolute right-0 z-20 mt-1 w-56 rounded-lg bg-white border border-navy-200 shadow-lg py-1">
                  <div className="px-4 py-2 border-b border-navy-100">
                    <p className="text-sm font-medium text-navy-900">{user?.nome}</p>
                    <p className="text-xs text-navy-500">{user?.email}</p>
                    <span className="mt-1 inline-block rounded-full bg-navy-100 px-2 py-0.5 text-[10px] font-medium text-navy-600 uppercase">
                      {PERFIL_LABELS[user?.perfil] || user?.perfil}
                    </span>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="flex w-full items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                  >
                    <LogOut className="h-4 w-4" />
                    Sair
                  </button>
                </div>
              </>
            )}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
