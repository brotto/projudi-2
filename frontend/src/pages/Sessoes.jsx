import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../api';
import EstadoBadge from '../components/EstadoBadge';
import {
  Calendar,
  Plus,
  AlertCircle,
  CheckCircle,
  Clock,
  Users,
  X,
  FileText,
} from 'lucide-react';

export default function Sessoes() {
  const { user } = useAuth();
  const [sessoes, setSessoes] = useState([]);
  const [reclamacoes, setReclamacoes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // New session form
  const [showForm, setShowForm] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [newSessao, setNewSessao] = useState({
    reclamacao_id: '',
    data_hora: '',
    tipo: 'CONCILIACAO',
    local: 'Sala de Audiencias CEJUSC',
    conciliador_id: '',
  });

  // Result form
  const [showResultForm, setShowResultForm] = useState(null);
  const [resultado, setResultado] = useState({
    resultado: 'ACORDO',
    observacoes: '',
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [sesRes, recRes] = await Promise.all([
          api.get('/sessoes/').catch(() => ({ data: [] })),
          api.get('/reclamacoes/').catch(() => ({ data: [] })),
        ]);
        setSessoes(Array.isArray(sesRes.data) ? sesRes.data : []);
        setReclamacoes(Array.isArray(recRes.data) ? recRes.data : []);
      } catch {
        setError('Erro ao carregar sessoes');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleCreateSessao = async (e) => {
    e.preventDefault();
    setFormLoading(true);
    setError('');
    try {
      const payload = {
        reclamacao_id: newSessao.reclamacao_id,
        data_hora: new Date(newSessao.data_hora).toISOString(),
        tipo: newSessao.tipo,
        local: newSessao.local,
        conciliador_id: newSessao.conciliador_id || undefined,
      };
      const res = await api.post('/sessoes/', payload);
      setSessoes((prev) => [res.data, ...prev]);
      setShowForm(false);
      setSuccessMsg('Sessao agendada com sucesso!');
      setNewSessao({ reclamacao_id: '', data_hora: '', tipo: 'CONCILIACAO', local: 'Sala de Audiencias CEJUSC', conciliador_id: '' });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Erro ao criar sessao');
    } finally {
      setFormLoading(false);
    }
  };

  const handleRegistrarResultado = async (sessaoId) => {
    setFormLoading(true);
    setError('');
    try {
      await api.post(`/sessoes/${sessaoId}/resultado`, resultado);
      setSuccessMsg('Resultado da sessao registrado com sucesso!');
      setShowResultForm(null);
      // Refresh
      const sesRes = await api.get('/sessoes/');
      setSessoes(Array.isArray(sesRes.data) ? sesRes.data : []);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Erro ao registrar resultado');
    } finally {
      setFormLoading(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '---';
    return new Date(dateStr).toLocaleDateString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const inputClass =
    'w-full rounded-lg border border-navy-300 bg-white px-3.5 py-2.5 text-sm text-navy-900 placeholder:text-navy-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none transition-colors';

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 animate-spin rounded-full border-3 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-navy-900">Sessoes</h1>
          <p className="text-sm text-navy-500 mt-1">
            Gerenciar sessoes de conciliacao e mediacao
          </p>
        </div>
        {(user?.perfil === 'SECRETARIA' || user?.perfil === 'CONCILIADOR' || user?.perfil === 'MEDIADOR') && (
          <button
            onClick={() => setShowForm(!showForm)}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Agendar Sessao
          </button>
        )}
      </div>

      {successMsg && (
        <div className="flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 p-3 text-sm text-green-700">
          <CheckCircle className="h-4 w-4 shrink-0" />
          {successMsg}
          <button onClick={() => setSuccessMsg('')} className="ml-auto"><X className="h-4 w-4" /></button>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
          <button onClick={() => setError('')} className="ml-auto"><X className="h-4 w-4" /></button>
        </div>
      )}

      {/* New session form */}
      {showForm && (
        <div className="rounded-xl bg-white border border-navy-200 shadow-sm p-6">
          <h2 className="text-base font-semibold text-navy-900 mb-4">Agendar Nova Sessao</h2>
          <form onSubmit={handleCreateSessao} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-navy-700 mb-1.5">Reclamacao</label>
                <select
                  value={newSessao.reclamacao_id}
                  onChange={(e) => setNewSessao({ ...newSessao, reclamacao_id: e.target.value })}
                  required
                  className={inputClass}
                >
                  <option value="">Selecione...</option>
                  {reclamacoes
                    .filter((r) => ['CADASTRADO', 'SESSAO_AGENDADA', 'NOTIFICACOES_ENVIADAS'].includes(r.estado_atual))
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.numero_procedimento || r.id.slice(0, 8)} - {r.reclamante?.nome || 'Reclamante'}
                      </option>
                    ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-700 mb-1.5">Data e Hora</label>
                <input
                  type="datetime-local"
                  value={newSessao.data_hora}
                  onChange={(e) => setNewSessao({ ...newSessao, data_hora: e.target.value })}
                  required
                  className={inputClass}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-700 mb-1.5">Tipo</label>
                <select
                  value={newSessao.tipo}
                  onChange={(e) => setNewSessao({ ...newSessao, tipo: e.target.value })}
                  className={inputClass}
                >
                  <option value="CONCILIACAO">Conciliacao</option>
                  <option value="MEDIACAO">Mediacao</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-700 mb-1.5">Local</label>
                <input
                  type="text"
                  value={newSessao.local}
                  onChange={(e) => setNewSessao({ ...newSessao, local: e.target.value })}
                  className={inputClass}
                />
              </div>
            </div>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="rounded-lg px-4 py-2 text-sm font-medium text-navy-600 hover:bg-navy-100 transition-colors"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={formLoading}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                {formLoading && <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />}
                Agendar
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Sessions list */}
      <div className="rounded-xl bg-white border border-navy-200 shadow-sm overflow-hidden">
        {sessoes.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-4">
            <Calendar className="h-12 w-12 text-navy-300 mb-3" />
            <p className="text-sm font-medium text-navy-700">Nenhuma sessao agendada</p>
          </div>
        ) : (
          <div className="divide-y divide-navy-100">
            {sessoes.map((sessao) => (
              <div key={sessao.id} className="p-5 hover:bg-navy-50 transition-colors">
                <div className="flex items-start justify-between flex-wrap gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-navy-900">
                        Sessao de {sessao.tipo || 'Conciliacao'}
                      </span>
                      {sessao.resultado && (
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          sessao.resultado === 'ACORDO'
                            ? 'bg-green-50 text-green-700'
                            : sessao.resultado === 'SEM_ACORDO'
                            ? 'bg-red-50 text-red-700'
                            : 'bg-yellow-50 text-yellow-700'
                        }`}>
                          {sessao.resultado.replace(/_/g, ' ')}
                        </span>
                      )}
                      {!sessao.resultado && (
                        <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                          Agendada
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-xs text-navy-500">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatDate(sessao.data_hora)}
                      </span>
                      {sessao.local && (
                        <span className="flex items-center gap-1">
                          <Users className="h-3 w-3" />
                          {sessao.local}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-navy-400 font-mono">
                      Reclamacao: {sessao.reclamacao_id?.slice(0, 8)}...
                    </p>
                    {sessao.observacoes && (
                      <p className="text-xs text-navy-600 mt-1">{sessao.observacoes}</p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    {!sessao.resultado && (user?.perfil === 'CONCILIADOR' || user?.perfil === 'MEDIADOR' || user?.perfil === 'SECRETARIA') && (
                      <button
                        onClick={() => setShowResultForm(sessao.id)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-navy-200 px-3 py-1.5 text-xs font-medium text-navy-700 hover:bg-navy-50 transition-colors"
                      >
                        <FileText className="h-3.5 w-3.5" />
                        Registrar Resultado
                      </button>
                    )}
                  </div>
                </div>

                {/* Result form inline */}
                {showResultForm === sessao.id && (
                  <div className="mt-4 rounded-lg bg-navy-50 p-4">
                    <h4 className="text-sm font-semibold text-navy-900 mb-3">Registrar Resultado</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-navy-700 mb-1">Resultado</label>
                        <select
                          value={resultado.resultado}
                          onChange={(e) => setResultado({ ...resultado, resultado: e.target.value })}
                          className={inputClass}
                        >
                          <option value="ACORDO">Acordo</option>
                          <option value="SEM_ACORDO">Sem Acordo</option>
                          <option value="AUSENCIA">Ausencia</option>
                          <option value="CONTINUACAO">Continuacao</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-navy-700 mb-1">Observacoes</label>
                        <input
                          type="text"
                          value={resultado.observacoes}
                          onChange={(e) => setResultado({ ...resultado, observacoes: e.target.value })}
                          className={inputClass}
                          placeholder="Observacoes..."
                        />
                      </div>
                    </div>
                    <div className="flex justify-end gap-2 mt-3">
                      <button
                        onClick={() => setShowResultForm(null)}
                        className="rounded-lg px-3 py-1.5 text-xs font-medium text-navy-600 hover:bg-navy-100"
                      >
                        Cancelar
                      </button>
                      <button
                        onClick={() => handleRegistrarResultado(sessao.id)}
                        disabled={formLoading}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        Registrar
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
