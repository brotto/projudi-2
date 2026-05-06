import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Scale, UserPlus, AlertCircle, CheckCircle } from 'lucide-react';

const PERFIS = [
  { value: 'PARTE', label: 'Parte (Solicitante)' },
  { value: 'ADVOGADO', label: 'Advogado' },
  { value: 'SECRETARIA', label: 'Secretaria CEJUSC' },
  { value: 'CONCILIADOR', label: 'Conciliador' },
  { value: 'MEDIADOR', label: 'Mediador' },
  { value: 'JUIZ_COORDENADOR', label: 'Juiz Coordenador' },
  { value: 'MP', label: 'Ministerio Publico' },
];

export default function Registro() {
  const [nome, setNome] = useState('');
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [perfil, setPerfil] = useState('PARTE');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const { register, loading } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const result = await register(nome, email, senha, perfil);
    if (result.success) {
      setSuccess(true);
      setTimeout(() => navigate('/'), 1500);
    } else {
      setError(result.error);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-navy-50 px-4 py-8">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-navy-800">
            <Scale className="h-7 w-7 text-blue-400" />
          </div>
          <h1 className="text-2xl font-bold text-navy-900">Juizo</h1>
          <p className="mt-1 text-sm text-navy-500">Cadastro de novo usuario</p>
        </div>

        {/* Form card */}
        <div className="rounded-xl bg-white p-8 shadow-sm border border-navy-200">
          <h2 className="text-lg font-semibold text-navy-900 mb-1">Criar Conta</h2>
          <p className="text-sm text-navy-500 mb-6">
            Preencha os dados para se registrar
          </p>

          {success && (
            <div className="mb-4 flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 p-3 text-sm text-green-700">
              <CheckCircle className="h-4 w-4 shrink-0" />
              Conta criada com sucesso! Redirecionando...
            </div>
          )}

          {error && (
            <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {typeof error === 'string' ? error : JSON.stringify(error)}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-navy-700 mb-1.5">
                Nome completo
              </label>
              <input
                type="text"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                required
                placeholder="Seu nome completo"
                className="w-full rounded-lg border border-navy-300 bg-white px-3.5 py-2.5 text-sm text-navy-900 placeholder:text-navy-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-navy-700 mb-1.5">
                E-mail
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="seu@email.com"
                className="w-full rounded-lg border border-navy-300 bg-white px-3.5 py-2.5 text-sm text-navy-900 placeholder:text-navy-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-navy-700 mb-1.5">
                Senha
              </label>
              <input
                type="password"
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                required
                minLength={6}
                placeholder="Minimo 6 caracteres"
                className="w-full rounded-lg border border-navy-300 bg-white px-3.5 py-2.5 text-sm text-navy-900 placeholder:text-navy-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-navy-700 mb-1.5">
                Perfil
              </label>
              <select
                value={perfil}
                onChange={(e) => setPerfil(e.target.value)}
                className="w-full rounded-lg border border-navy-300 bg-white px-3.5 py-2.5 text-sm text-navy-900 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none transition-colors"
              >
                {PERFIS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="submit"
              disabled={loading || success}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 focus:ring-2 focus:ring-blue-500/20 focus:outline-none transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
              ) : (
                <UserPlus className="h-4 w-4" />
              )}
              Criar Conta
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-navy-500">
            Ja possui conta?{' '}
            <Link to="/login" className="font-medium text-blue-600 hover:text-blue-700">
              Fazer login
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
