import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import api from '../api';
import EstadoBadge from '../components/EstadoBadge';
import { FileText, Search, Plus, Eye, AlertCircle, Filter } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

export default function Reclamacoes() {
  const { user } = useAuth();
  const [reclamacoes, setReclamacoes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterEstado, setFilterEstado] = useState('');

  useEffect(() => {
    const fetchReclamacoes = async () => {
      try {
        const res = await api.get('/reclamacoes/');
        setReclamacoes(Array.isArray(res.data) ? res.data : []);
      } catch (err) {
        setError('Erro ao carregar reclamacoes');
      } finally {
        setLoading(false);
      }
    };
    fetchReclamacoes();
  }, []);

  const filtered = reclamacoes.filter((r) => {
    const matchSearch =
      !searchTerm ||
      (r.numero_procedimento || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.reclamante?.nome || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.reclamado?.nome || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.id || '').toLowerCase().includes(searchTerm.toLowerCase());
    const matchEstado = !filterEstado || r.estado_atual === filterEstado;
    return matchSearch && matchEstado;
  });

  const uniqueEstados = [...new Set(reclamacoes.map((r) => r.estado_atual))].sort();

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
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-navy-900">Reclamacoes</h1>
          <p className="text-sm text-navy-500 mt-1">
            {reclamacoes.length} reclamacao(oes) registrada(s)
          </p>
        </div>
        {user?.perfil === 'PARTE' && (
          <Link
            to="/reclamacoes/nova"
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Nova Reclamacao
          </Link>
        )}
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-navy-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Buscar por nome, numero, ID..."
            className="w-full rounded-lg border border-navy-300 bg-white pl-10 pr-4 py-2.5 text-sm text-navy-900 placeholder:text-navy-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-navy-400" />
          <select
            value={filterEstado}
            onChange={(e) => setFilterEstado(e.target.value)}
            className="rounded-lg border border-navy-300 bg-white pl-10 pr-8 py-2.5 text-sm text-navy-900 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none appearance-none min-w-[200px]"
          >
            <option value="">Todos os estados</option>
            {uniqueEstados.map((e) => (
              <option key={e} value={e}>{e.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl bg-white border border-navy-200 shadow-sm overflow-hidden">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-4">
            <FileText className="h-12 w-12 text-navy-300 mb-3" />
            <p className="text-sm font-medium text-navy-700">Nenhuma reclamacao encontrada</p>
            <p className="text-xs text-navy-500 mt-1">
              {searchTerm || filterEstado ? 'Tente ajustar os filtros' : 'Nenhuma reclamacao registrada ainda'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-navy-100 bg-navy-50">
                  <th className="px-5 py-3 text-left text-xs font-semibold text-navy-600 uppercase tracking-wider">
                    Numero / ID
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-navy-600 uppercase tracking-wider">
                    Reclamante
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-navy-600 uppercase tracking-wider">
                    Reclamado
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-navy-600 uppercase tracking-wider">
                    Modalidade
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-navy-600 uppercase tracking-wider">
                    Estado
                  </th>
                  <th className="px-5 py-3 text-left text-xs font-semibold text-navy-600 uppercase tracking-wider">
                    Valor
                  </th>
                  <th className="px-5 py-3 text-right text-xs font-semibold text-navy-600 uppercase tracking-wider">
                    Acoes
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-100">
                {filtered.map((rec) => (
                  <tr key={rec.id} className="hover:bg-navy-50 transition-colors">
                    <td className="px-5 py-3.5">
                      <p className="text-sm font-medium text-navy-900">
                        {rec.numero_procedimento || '---'}
                      </p>
                      <p className="text-xs text-navy-400 font-mono">
                        {rec.id?.slice(0, 8)}...
                      </p>
                    </td>
                    <td className="px-5 py-3.5">
                      <p className="text-sm text-navy-900">
                        {rec.reclamante?.nome || '---'}
                      </p>
                    </td>
                    <td className="px-5 py-3.5">
                      <p className="text-sm text-navy-900">
                        {rec.reclamado?.nome || '---'}
                      </p>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="text-sm text-navy-600">
                        {rec.modalidade || '---'}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <EstadoBadge estado={rec.estado_atual} size="sm" />
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="text-sm text-navy-900">
                        {rec.valor_causa
                          ? `R$ ${Number(rec.valor_causa).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
                          : '---'}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <Link
                        to={`/reclamacoes/${rec.id}`}
                        className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-50 transition-colors"
                      >
                        <Eye className="h-3.5 w-3.5" />
                        Ver
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
