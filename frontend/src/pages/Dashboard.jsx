import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api';
import EstadoBadge from '../components/EstadoBadge';
import {
  FileText,
  Calendar,
  Handshake,
  Clock,
  TrendingUp,
  AlertCircle,
  ArrowRight,
  Scale,
} from 'lucide-react';

const ESTADOS_ATIVOS = [
  'SOLICITACAO_RECEBIDA', 'TRIAGEM', 'VERIFICACAO_CUSTAS', 'ANALISE_GRATUIDADE',
  'CADASTRADO', 'SESSAO_AGENDADA', 'NOTIFICACOES_ENVIADAS', 'SESSAO_CONDUZIDA',
  'SESSAO_CONTINUADA', 'ACORDO_REDIGIDO', 'AGUARDANDO_MP', 'CONCLUSO_JUIZ', 'HOMOLOGADO',
];

const ESTADOS_ARQUIVADOS = [
  'ARQUIVADO_ACORDO', 'ARQUIVADO_SEM_ACORDO', 'ARQUIVADO_AUSENCIA',
  'ARQUIVADO_FALTA_CUSTAS', 'ARQUIVADO_INCOMPETENTE', 'ARQUIVADO_IRREGULAR',
];

export default function Dashboard() {
  const { user } = useAuth();
  const [reclamacoes, setReclamacoes] = useState([]);
  const [sessoes, setSessoes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [recRes, sesRes] = await Promise.all([
          api.get('/reclamacoes/').catch(() => ({ data: [] })),
          api.get('/sessoes/').catch(() => ({ data: [] })),
        ]);
        setReclamacoes(Array.isArray(recRes.data) ? recRes.data : []);
        setSessoes(Array.isArray(sesRes.data) ? sesRes.data : []);
      } catch (err) {
        setError('Erro ao carregar dados do dashboard');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Compute stats
  const totalReclamacoes = reclamacoes.length;
  const ativas = reclamacoes.filter((r) => ESTADOS_ATIVOS.includes(r.estado_atual));
  const arquivadas = reclamacoes.filter((r) => ESTADOS_ARQUIVADOS.includes(r.estado_atual));
  const comAcordo = reclamacoes.filter((r) => r.estado_atual === 'ARQUIVADO_ACORDO');
  const sessoesAgendadas = sessoes.filter((s) => s.status === 'AGENDADA' || !s.resultado);

  // Group active by estado
  const estadoCount = {};
  ativas.forEach((r) => {
    estadoCount[r.estado_atual] = (estadoCount[r.estado_atual] || 0) + 1;
  });

  const recentReclamacoes = [...reclamacoes]
    .sort((a, b) => new Date(b.criado_em || b.created_at || 0) - new Date(a.criado_em || a.created_at || 0))
    .slice(0, 5);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 animate-spin rounded-full border-3 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-navy-900">Dashboard</h1>
        <p className="text-sm text-navy-500 mt-1">
          Bem-vindo, {user?.nome}. Visao geral do CEJUSC-Pre.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Stats cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl bg-white p-5 border border-navy-200 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
              <FileText className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-navy-900">{totalReclamacoes}</p>
              <p className="text-xs text-navy-500">Total Reclamacoes</p>
            </div>
          </div>
        </div>

        <div className="rounded-xl bg-white p-5 border border-navy-200 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-50">
              <TrendingUp className="h-5 w-5 text-indigo-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-navy-900">{ativas.length}</p>
              <p className="text-xs text-navy-500">Em Andamento</p>
            </div>
          </div>
        </div>

        <div className="rounded-xl bg-white p-5 border border-navy-200 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50">
              <Handshake className="h-5 w-5 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-navy-900">{comAcordo.length}</p>
              <p className="text-xs text-navy-500">Acordos</p>
            </div>
          </div>
        </div>

        <div className="rounded-xl bg-white p-5 border border-navy-200 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-50">
              <Calendar className="h-5 w-5 text-purple-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-navy-900">{sessoesAgendadas.length}</p>
              <p className="text-xs text-navy-500">Sessoes Agendadas</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active states breakdown */}
        <div className="rounded-xl bg-white border border-navy-200 shadow-sm">
          <div className="flex items-center justify-between px-5 py-4 border-b border-navy-100">
            <h2 className="text-sm font-semibold text-navy-900">Distribuicao por Estado</h2>
            <Scale className="h-4 w-4 text-navy-400" />
          </div>
          <div className="p-5 space-y-3">
            {Object.keys(estadoCount).length === 0 ? (
              <p className="text-sm text-navy-500 text-center py-4">
                Nenhuma reclamacao ativa
              </p>
            ) : (
              Object.entries(estadoCount)
                .sort((a, b) => b[1] - a[1])
                .map(([estado, count]) => (
                  <div key={estado} className="flex items-center justify-between">
                    <EstadoBadge estado={estado} size="sm" />
                    <span className="text-sm font-semibold text-navy-700">{count}</span>
                  </div>
                ))
            )}
          </div>
        </div>

        {/* Recent reclamacoes */}
        <div className="rounded-xl bg-white border border-navy-200 shadow-sm">
          <div className="flex items-center justify-between px-5 py-4 border-b border-navy-100">
            <h2 className="text-sm font-semibold text-navy-900">Reclamacoes Recentes</h2>
            <Link
              to="/reclamacoes"
              className="text-xs font-medium text-blue-600 hover:text-blue-700 inline-flex items-center gap-1"
            >
              Ver todas <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="divide-y divide-navy-100">
            {recentReclamacoes.length === 0 ? (
              <p className="text-sm text-navy-500 text-center py-8">
                Nenhuma reclamacao registrada
              </p>
            ) : (
              recentReclamacoes.map((rec) => (
                <Link
                  key={rec.id}
                  to={`/reclamacoes/${rec.id}`}
                  className="flex items-center justify-between px-5 py-3 hover:bg-navy-50 transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-navy-900 truncate">
                      {rec.numero_procedimento || `Reclamacao #${rec.id?.slice(0, 8)}`}
                    </p>
                    <p className="text-xs text-navy-500 mt-0.5 truncate">
                      {rec.reclamante?.nome || 'Reclamante'} vs {rec.reclamado?.nome || 'Reclamado'}
                    </p>
                  </div>
                  <EstadoBadge estado={rec.estado_atual} size="sm" />
                </Link>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Role-specific hints */}
      {user?.perfil === 'PARTE' && (
        <div className="rounded-xl bg-blue-50 border border-blue-200 p-5">
          <div className="flex items-start gap-3">
            <Clock className="h-5 w-5 text-blue-600 mt-0.5" />
            <div>
              <h3 className="text-sm font-semibold text-blue-900">Dica</h3>
              <p className="text-sm text-blue-700 mt-1">
                Para abrir uma nova reclamacao, acesse o menu{' '}
                <Link to="/reclamacoes/nova" className="font-medium underline">
                  Nova Reclamacao
                </Link>{' '}
                na barra lateral.
              </p>
            </div>
          </div>
        </div>
      )}

      {user?.perfil === 'SECRETARIA' && (
        <div className="rounded-xl bg-yellow-50 border border-yellow-200 p-5">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-yellow-600 mt-0.5" />
            <div>
              <h3 className="text-sm font-semibold text-yellow-900">Pendencias</h3>
              <p className="text-sm text-yellow-700 mt-1">
                {estadoCount['SOLICITACAO_RECEBIDA'] || 0} reclamacoes aguardando triagem.{' '}
                {estadoCount['CADASTRADO'] || 0} reclamacoes aguardando agendamento de sessao.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
