import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import api from '../api';
import {
  Handshake,
  Plus,
  AlertCircle,
  CheckCircle,
  X,
  FileText,
  Gavel,
  ShieldCheck,
  Eye,
} from 'lucide-react';

export default function Acordos() {
  const { user } = useAuth();
  const [acordos, setAcordos] = useState([]);
  const [reclamacoes, setReclamacoes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');
  const [formLoading, setFormLoading] = useState(false);

  // New agreement form
  const [showForm, setShowForm] = useState(false);
  const [newAcordo, setNewAcordo] = useState({
    reclamacao_id: '',
    termos: '',
    valor: '',
    prazo_cumprimento: '',
    menores_envolvidos: false,
  });

  // Parecer MP form
  const [showParecerForm, setShowParecerForm] = useState(null);
  const [parecer, setParecer] = useState({
    parecer: 'FAVORAVEL',
    fundamentacao: '',
  });

  // Detail view
  const [selectedAcordo, setSelectedAcordo] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [recRes] = await Promise.all([
          api.get('/reclamacoes/').catch(() => ({ data: [] })),
        ]);
        setReclamacoes(Array.isArray(recRes.data) ? recRes.data : []);

        // Acordos might come from reclamacoes data or separate endpoint
        // Try to get from the list endpoint
        const acordosList = [];
        const recs = Array.isArray(recRes.data) ? recRes.data : [];
        for (const rec of recs) {
          if (['ACORDO_REDIGIDO', 'AGUARDANDO_MP', 'CONCLUSO_JUIZ', 'HOMOLOGADO', 'ARQUIVADO_ACORDO'].includes(rec.estado_atual)) {
            acordosList.push(rec);
          }
        }
        setAcordos(acordosList);
      } catch {
        setError('Erro ao carregar dados');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleCreateAcordo = async (e) => {
    e.preventDefault();
    setFormLoading(true);
    setError('');
    try {
      const payload = {
        reclamacao_id: newAcordo.reclamacao_id,
        termos: newAcordo.termos,
        valor: newAcordo.valor ? parseFloat(newAcordo.valor) : undefined,
        prazo_cumprimento: newAcordo.prazo_cumprimento || undefined,
        menores_envolvidos: newAcordo.menores_envolvidos,
      };
      await api.post('/acordos/', payload);
      setSuccessMsg('Acordo registrado com sucesso!');
      setShowForm(false);
      setNewAcordo({ reclamacao_id: '', termos: '', valor: '', prazo_cumprimento: '', menores_envolvidos: false });
      // Refresh
      const recRes = await api.get('/reclamacoes/');
      const recs = Array.isArray(recRes.data) ? recRes.data : [];
      setReclamacoes(recs);
      setAcordos(recs.filter((r) =>
        ['ACORDO_REDIGIDO', 'AGUARDANDO_MP', 'CONCLUSO_JUIZ', 'HOMOLOGADO', 'ARQUIVADO_ACORDO'].includes(r.estado_atual)
      ));
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Erro ao criar acordo');
    } finally {
      setFormLoading(false);
    }
  };

  const handleParecerMP = async (acordoId) => {
    setFormLoading(true);
    setError('');
    try {
      await api.post(`/acordos/${acordoId}/parecer-mp`, parecer);
      setSuccessMsg('Parecer do MP registrado com sucesso!');
      setShowParecerForm(null);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Erro ao registrar parecer');
    } finally {
      setFormLoading(false);
    }
  };

  const handleHomologar = async (acordoId) => {
    setFormLoading(true);
    setError('');
    try {
      await api.post(`/acordos/${acordoId}/homologar`);
      setSuccessMsg('Acordo homologado com sucesso!');
      // Refresh
      const recRes = await api.get('/reclamacoes/');
      const recs = Array.isArray(recRes.data) ? recRes.data : [];
      setReclamacoes(recs);
      setAcordos(recs.filter((r) =>
        ['ACORDO_REDIGIDO', 'AGUARDANDO_MP', 'CONCLUSO_JUIZ', 'HOMOLOGADO', 'ARQUIVADO_ACORDO'].includes(r.estado_atual)
      ));
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Erro ao homologar acordo');
    } finally {
      setFormLoading(false);
    }
  };

  const handleViewAcordo = async (acordoId) => {
    try {
      const res = await api.get(`/acordos/${acordoId}`);
      setSelectedAcordo(res.data);
    } catch {
      setError('Erro ao carregar detalhes do acordo');
    }
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
          <h1 className="text-2xl font-bold text-navy-900">Acordos</h1>
          <p className="text-sm text-navy-500 mt-1">
            Gerenciar acordos, pareceres do MP e homologacoes
          </p>
        </div>
        {(user?.perfil === 'CONCILIADOR' || user?.perfil === 'MEDIADOR' || user?.perfil === 'SECRETARIA') && (
          <button
            onClick={() => setShowForm(!showForm)}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Novo Acordo
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

      {/* New agreement form */}
      {showForm && (
        <div className="rounded-xl bg-white border border-navy-200 shadow-sm p-6">
          <h2 className="text-base font-semibold text-navy-900 mb-4">Registrar Novo Acordo</h2>
          <form onSubmit={handleCreateAcordo} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-navy-700 mb-1.5">Reclamacao</label>
                <select
                  value={newAcordo.reclamacao_id}
                  onChange={(e) => setNewAcordo({ ...newAcordo, reclamacao_id: e.target.value })}
                  required
                  className={inputClass}
                >
                  <option value="">Selecione...</option>
                  {reclamacoes
                    .filter((r) => ['SESSAO_CONDUZIDA', 'SESSAO_CONTINUADA'].includes(r.estado_atual))
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.numero_procedimento || r.id.slice(0, 8)} - {r.reclamante?.nome || 'Reclamante'}
                      </option>
                    ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-navy-700 mb-1.5">Valor do Acordo (R$)</label>
                <input
                  type="number"
                  step="0.01"
                  value={newAcordo.valor}
                  onChange={(e) => setNewAcordo({ ...newAcordo, valor: e.target.value })}
                  className={inputClass}
                  placeholder="0,00"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-navy-700 mb-1.5">Termos do Acordo</label>
              <textarea
                value={newAcordo.termos}
                onChange={(e) => setNewAcordo({ ...newAcordo, termos: e.target.value })}
                required
                rows={4}
                className={inputClass}
                placeholder="Descreva os termos do acordo..."
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-navy-700 mb-1.5">Prazo de Cumprimento</label>
                <input
                  type="date"
                  value={newAcordo.prazo_cumprimento}
                  onChange={(e) => setNewAcordo({ ...newAcordo, prazo_cumprimento: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-2 pb-2.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={newAcordo.menores_envolvidos}
                    onChange={(e) => setNewAcordo({ ...newAcordo, menores_envolvidos: e.target.checked })}
                    className="h-4 w-4 rounded border-navy-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span className="text-sm text-navy-700">Envolve menores/incapazes</span>
                </label>
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
                Registrar Acordo
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Acordos list */}
      <div className="rounded-xl bg-white border border-navy-200 shadow-sm overflow-hidden">
        {acordos.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-4">
            <Handshake className="h-12 w-12 text-navy-300 mb-3" />
            <p className="text-sm font-medium text-navy-700">Nenhum acordo registrado</p>
            <p className="text-xs text-navy-500 mt-1">
              Acordos aparecem apos sessoes de conciliacao bem-sucedidas
            </p>
          </div>
        ) : (
          <div className="divide-y divide-navy-100">
            {acordos.map((acordo) => (
              <div key={acordo.id} className="p-5 hover:bg-navy-50 transition-colors">
                <div className="flex items-start justify-between flex-wrap gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-navy-900">
                        {acordo.numero_procedimento || `#${acordo.id?.slice(0, 8)}`}
                      </span>
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        acordo.estado_atual === 'ARQUIVADO_ACORDO'
                          ? 'bg-emerald-50 text-emerald-700'
                          : acordo.estado_atual === 'HOMOLOGADO'
                          ? 'bg-green-50 text-green-700'
                          : 'bg-purple-50 text-purple-700'
                      }`}>
                        {acordo.estado_atual?.replace(/_/g, ' ')}
                      </span>
                    </div>
                    <p className="text-xs text-navy-500">
                      {acordo.reclamante?.nome || 'Reclamante'} vs {acordo.reclamado?.nome || 'Reclamado'}
                    </p>
                    {acordo.valor_causa && (
                      <p className="text-xs text-navy-600">
                        Valor: R$ {Number(acordo.valor_causa).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    <button
                      onClick={() => handleViewAcordo(acordo.id)}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-navy-200 px-3 py-1.5 text-xs font-medium text-navy-700 hover:bg-navy-50 transition-colors"
                    >
                      <Eye className="h-3.5 w-3.5" />
                      Detalhes
                    </button>

                    {acordo.estado_atual === 'AGUARDANDO_MP' && user?.perfil === 'MP' && (
                      <button
                        onClick={() => setShowParecerForm(acordo.id)}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-purple-50 border border-purple-200 px-3 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-100 transition-colors"
                      >
                        <ShieldCheck className="h-3.5 w-3.5" />
                        Parecer MP
                      </button>
                    )}

                    {acordo.estado_atual === 'CONCLUSO_JUIZ' && user?.perfil === 'JUIZ_COORDENADOR' && (
                      <button
                        onClick={() => handleHomologar(acordo.id)}
                        disabled={formLoading}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-green-50 border border-green-200 px-3 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100 transition-colors disabled:opacity-50"
                      >
                        <Gavel className="h-3.5 w-3.5" />
                        Homologar
                      </button>
                    )}
                  </div>
                </div>

                {/* Parecer MP form */}
                {showParecerForm === acordo.id && (
                  <div className="mt-4 rounded-lg bg-purple-50 p-4">
                    <h4 className="text-sm font-semibold text-purple-900 mb-3">Parecer do Ministerio Publico</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-medium text-navy-700 mb-1">Parecer</label>
                        <select
                          value={parecer.parecer}
                          onChange={(e) => setParecer({ ...parecer, parecer: e.target.value })}
                          className={inputClass}
                        >
                          <option value="FAVORAVEL">Favoravel</option>
                          <option value="DESFAVORAVEL">Desfavoravel</option>
                          <option value="COM_RESSALVAS">Com Ressalvas</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-navy-700 mb-1">Fundamentacao</label>
                        <input
                          type="text"
                          value={parecer.fundamentacao}
                          onChange={(e) => setParecer({ ...parecer, fundamentacao: e.target.value })}
                          required
                          className={inputClass}
                          placeholder="Fundamentacao do parecer..."
                        />
                      </div>
                    </div>
                    <div className="flex justify-end gap-2 mt-3">
                      <button
                        onClick={() => setShowParecerForm(null)}
                        className="rounded-lg px-3 py-1.5 text-xs font-medium text-navy-600 hover:bg-navy-100"
                      >
                        Cancelar
                      </button>
                      <button
                        onClick={() => handleParecerMP(acordo.id)}
                        disabled={formLoading}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-purple-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-purple-700 disabled:opacity-50"
                      >
                        Registrar Parecer
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Acordo detail modal */}
      {selectedAcordo && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 p-6 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-navy-900">Detalhes do Acordo</h3>
              <button onClick={() => setSelectedAcordo(null)} className="text-navy-400 hover:text-navy-600">
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-3 text-sm">
              {Object.entries(selectedAcordo).map(([key, value]) => (
                <div key={key} className="flex justify-between border-b border-navy-100 pb-2">
                  <span className="text-navy-500">{key.replace(/_/g, ' ')}</span>
                  <span className="font-medium text-navy-900 text-right max-w-[60%]">
                    {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value ?? '---')}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
