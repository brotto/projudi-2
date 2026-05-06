import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api';
import EstadoBadge from '../components/EstadoBadge';
import TimelineEvento from '../components/TimelineEvento';
import TransicaoButton from '../components/TransicaoButton';
import {
  ArrowLeft,
  AlertCircle,
  FileText,
  User,
  Mail,
  Phone,
  MapPin,
  Clock,
  Download,
  History,
  Zap,
  CheckCircle,
} from 'lucide-react';

// All FSM states in order for the visual FSM
const FSM_STATES = [
  'SOLICITACAO_RECEBIDA',
  'TRIAGEM',
  'VERIFICACAO_CUSTAS',
  'ANALISE_GRATUIDADE',
  'CADASTRADO',
  'SESSAO_AGENDADA',
  'NOTIFICACOES_ENVIADAS',
  'SESSAO_CONDUZIDA',
  'SESSAO_CONTINUADA',
  'ACORDO_REDIGIDO',
  'AGUARDANDO_MP',
  'CONCLUSO_JUIZ',
  'HOMOLOGADO',
  'ARQUIVADO_ACORDO',
  'ARQUIVADO_SEM_ACORDO',
  'ARQUIVADO_AUSENCIA',
  'ARQUIVADO_FALTA_CUSTAS',
  'ARQUIVADO_INCOMPETENTE',
  'ARQUIVADO_IRREGULAR',
];

function FSMVisualization({ currentState, validTransitions }) {
  const currentIdx = FSM_STATES.indexOf(currentState);

  const getStateStyle = (state) => {
    if (state === currentState) {
      return 'ring-2 ring-blue-500 bg-blue-100 text-blue-800 font-semibold';
    }
    const stateIdx = FSM_STATES.indexOf(state);
    if (stateIdx < currentIdx && !state.startsWith('ARQUIVADO')) {
      return 'bg-green-50 text-green-700 opacity-60';
    }
    if (validTransitions?.includes(state)) {
      return 'ring-2 ring-amber-400 bg-amber-50 text-amber-800 animate-pulse';
    }
    if (state.startsWith('ARQUIVADO')) {
      return 'bg-navy-50 text-navy-400';
    }
    return 'bg-navy-50 text-navy-400';
  };

  const mainFlow = FSM_STATES.filter((s) => !s.startsWith('ARQUIVADO'));
  const terminals = FSM_STATES.filter((s) => s.startsWith('ARQUIVADO'));

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-navy-700 flex items-center gap-2">
        <Zap className="h-4 w-4" />
        Fluxo da FSM
      </h3>

      {/* Main flow */}
      <div className="flex flex-wrap gap-2">
        {mainFlow.map((state, idx) => (
          <div key={state} className="flex items-center gap-1">
            <div
              className={`rounded-lg px-2.5 py-1.5 text-[11px] font-medium transition-all ${getStateStyle(state)}`}
              title={state}
            >
              {state.replace(/_/g, ' ')}
            </div>
            {idx < mainFlow.length - 1 && (
              <div className="text-navy-300 text-xs">&rarr;</div>
            )}
          </div>
        ))}
      </div>

      {/* Terminal states */}
      <div>
        <p className="text-xs text-navy-500 mb-2">Estados Terminais:</p>
        <div className="flex flex-wrap gap-2">
          {terminals.map((state) => (
            <div
              key={state}
              className={`rounded-lg px-2.5 py-1.5 text-[11px] font-medium transition-all ${getStateStyle(state)}`}
              title={state}
            >
              {state.replace(/_/g, ' ')}
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-4 text-[10px] text-navy-500">
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded bg-blue-100 ring-1 ring-blue-500" /> Estado atual
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded bg-amber-50 ring-1 ring-amber-400" /> Transicao disponivel
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded bg-green-50" /> Ja percorrido
        </span>
      </div>
    </div>
  );
}

export default function ReclamacaoDetalhe() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [reclamacao, setReclamacao] = useState(null);
  const [estado, setEstado] = useState(null);
  const [historico, setHistorico] = useState([]);
  const [prazos, setPrazos] = useState(null);
  const [loading, setLoading] = useState(true);
  const [transicaoLoading, setTransicaoLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const fetchAll = useCallback(async () => {
    try {
      const [recRes, estRes, histRes] = await Promise.all([
        api.get(`/reclamacoes/${id}`),
        api.get(`/reclamacoes/${id}/estado`),
        api.get(`/reclamacoes/${id}/historico`),
      ]);
      setReclamacao(recRes.data);
      setEstado(estRes.data);
      setHistorico(Array.isArray(histRes.data) ? histRes.data : []);

      // Try to fetch prazos (may not exist for all states)
      try {
        const prazosRes = await api.get(`/automacoes/${id}/prazos`);
        setPrazos(prazosRes.data);
      } catch {
        // prazos endpoint might not be available
      }
    } catch (err) {
      setError('Erro ao carregar reclamacao');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const handleTransicao = async (estadoDestino) => {
    setTransicaoLoading(true);
    setError('');
    setSuccessMsg('');
    try {
      await api.post(`/reclamacoes/${id}/transicao`, {
        estado_destino: estadoDestino,
        ator_id: user?.id || user?.usuario_id || 'system',
        ator_tipo: user?.perfil || 'SECRETARIA',
        payload: {},
      });
      setSuccessMsg(`Transicao para ${estadoDestino.replace(/_/g, ' ')} realizada com sucesso!`);
      await fetchAll();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail) || 'Erro ao executar transicao');
    } finally {
      setTransicaoLoading(false);
    }
  };

  const handleDownload = async (tipo) => {
    try {
      const endpoint = tipo === 'carta' ? 'carta-convite' : 'certidao-negativa';
      const res = await api.get(`/automacoes/${id}/${endpoint}`);
      // Display content or download
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${endpoint}-${id.slice(0, 8)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(`Erro ao gerar ${tipo === 'carta' ? 'carta-convite' : 'certidao negativa'}`);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 animate-spin rounded-full border-3 border-blue-600 border-t-transparent" />
      </div>
    );
  }

  if (!reclamacao) {
    return (
      <div className="text-center py-16">
        <FileText className="h-12 w-12 text-navy-300 mx-auto mb-3" />
        <p className="text-sm text-navy-600">Reclamacao nao encontrada</p>
      </div>
    );
  }

  const rec = reclamacao;
  const validTransitions = estado?.transicoes_validas || [];

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <button
          onClick={() => navigate('/reclamacoes')}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-navy-600 hover:bg-navy-100 transition-colors mt-0.5"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-navy-900">
              {rec.numero_procedimento || `Reclamacao`}
            </h1>
            <EstadoBadge estado={rec.estado_atual} />
          </div>
          <p className="text-xs text-navy-400 font-mono mt-1">ID: {rec.id}</p>
        </div>
      </div>

      {successMsg && (
        <div className="flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 p-3 text-sm text-green-700">
          <CheckCircle className="h-4 w-4 shrink-0" />
          {successMsg}
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* FSM Visualization */}
      <div className="rounded-xl bg-white border border-navy-200 shadow-sm p-5">
        <FSMVisualization
          currentState={rec.estado_atual}
          validTransitions={validTransitions}
        />
      </div>

      {/* Valid Transitions */}
      {validTransitions.length > 0 && (
        <div className="rounded-xl bg-white border border-navy-200 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-navy-700 mb-3">Transicoes Disponiveis</h3>
          <div className="flex flex-wrap gap-2">
            {validTransitions.map((t) => (
              <TransicaoButton
                key={t}
                estadoDestino={t}
                onConfirm={handleTransicao}
                loading={transicaoLoading}
              />
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Reclamante */}
        <div className="rounded-xl bg-white border border-navy-200 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-navy-900 mb-3 flex items-center gap-2">
            <User className="h-4 w-4 text-blue-600" />
            Reclamante
          </h3>
          <div className="space-y-2 text-sm">
            <p className="font-medium text-navy-900">{rec.reclamante?.nome}</p>
            <p className="text-navy-600 font-mono text-xs">{rec.reclamante?.cpf_cnpj}</p>
            {rec.reclamante?.email && (
              <p className="flex items-center gap-2 text-navy-600">
                <Mail className="h-3.5 w-3.5 text-navy-400" />
                {rec.reclamante.email}
              </p>
            )}
            {rec.reclamante?.telefone && (
              <p className="flex items-center gap-2 text-navy-600">
                <Phone className="h-3.5 w-3.5 text-navy-400" />
                {rec.reclamante.telefone}
              </p>
            )}
            {rec.reclamante?.endereco && (
              <p className="flex items-start gap-2 text-navy-600">
                <MapPin className="h-3.5 w-3.5 text-navy-400 mt-0.5" />
                <span>
                  {rec.reclamante.endereco.logradouro}, {rec.reclamante.endereco.numero}
                  {rec.reclamante.endereco.complemento && ` - ${rec.reclamante.endereco.complemento}`}
                  <br />
                  {rec.reclamante.endereco.bairro}, {rec.reclamante.endereco.cidade}/{rec.reclamante.endereco.uf}
                  <br />
                  CEP: {rec.reclamante.endereco.cep}
                </span>
              </p>
            )}
          </div>
        </div>

        {/* Reclamado */}
        <div className="rounded-xl bg-white border border-navy-200 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-navy-900 mb-3 flex items-center gap-2">
            <User className="h-4 w-4 text-red-500" />
            Reclamado
          </h3>
          <div className="space-y-2 text-sm">
            <p className="font-medium text-navy-900">{rec.reclamado?.nome}</p>
            <p className="text-navy-600 font-mono text-xs">{rec.reclamado?.cpf_cnpj}</p>
            {rec.reclamado?.email && (
              <p className="flex items-center gap-2 text-navy-600">
                <Mail className="h-3.5 w-3.5 text-navy-400" />
                {rec.reclamado.email}
              </p>
            )}
            {rec.reclamado?.telefone && (
              <p className="flex items-center gap-2 text-navy-600">
                <Phone className="h-3.5 w-3.5 text-navy-400" />
                {rec.reclamado.telefone}
              </p>
            )}
            {rec.reclamado?.endereco && (
              <p className="flex items-start gap-2 text-navy-600">
                <MapPin className="h-3.5 w-3.5 text-navy-400 mt-0.5" />
                <span>
                  {rec.reclamado.endereco.logradouro}, {rec.reclamado.endereco.numero}
                  {rec.reclamado.endereco.complemento && ` - ${rec.reclamado.endereco.complemento}`}
                  <br />
                  {rec.reclamado.endereco.bairro}, {rec.reclamado.endereco.cidade}/{rec.reclamado.endereco.uf}
                  <br />
                  CEP: {rec.reclamado.endereco.cep}
                </span>
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="rounded-xl bg-white border border-navy-200 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-navy-900 mb-3 flex items-center gap-2">
          <FileText className="h-4 w-4 text-navy-600" />
          Detalhes da Reclamacao
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-navy-500">Modalidade</p>
            <p className="font-medium text-navy-900">{rec.modalidade || '---'}</p>
          </div>
          <div>
            <p className="text-navy-500">Valor da Causa</p>
            <p className="font-medium text-navy-900">
              {rec.valor_causa
                ? `R$ ${Number(rec.valor_causa).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
                : '---'}
            </p>
          </div>
          <div>
            <p className="text-navy-500">Gratuidade</p>
            <p className="font-medium text-navy-900">{rec.opcao_gratuidade ? 'Sim' : 'Nao'}</p>
          </div>
        </div>
        {rec.fatos && (
          <div className="mt-4">
            <p className="text-sm text-navy-500 mb-1">Fatos</p>
            <p className="text-sm text-navy-900 bg-navy-50 rounded-lg p-3">{rec.fatos}</p>
          </div>
        )}
        {rec.pedidos && rec.pedidos.length > 0 && (
          <div className="mt-4">
            <p className="text-sm text-navy-500 mb-2">Pedidos</p>
            <div className="space-y-2">
              {rec.pedidos.map((p, idx) => (
                <div key={idx} className="flex items-center justify-between text-sm bg-navy-50 rounded-lg p-3">
                  <span className="text-navy-900">{p.descricao}</span>
                  {p.valor && (
                    <span className="font-medium text-navy-700">
                      R$ {Number(p.valor).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Prazos */}
      {prazos && (
        <div className="rounded-xl bg-white border border-navy-200 shadow-sm p-5">
          <h3 className="text-sm font-semibold text-navy-900 mb-3 flex items-center gap-2">
            <Clock className="h-4 w-4 text-navy-600" />
            Prazos Computados
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
            {Object.entries(prazos).map(([key, value]) => (
              <div key={key} className="flex justify-between bg-navy-50 rounded-lg p-3">
                <span className="text-navy-600">{key.replace(/_/g, ' ')}</span>
                <span className="font-medium text-navy-900">{String(value)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Automation documents */}
      <div className="rounded-xl bg-white border border-navy-200 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-navy-900 mb-3 flex items-center gap-2">
          <Download className="h-4 w-4 text-navy-600" />
          Documentos Automaticos
        </h3>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => handleDownload('carta')}
            className="inline-flex items-center gap-2 rounded-lg border border-navy-200 px-4 py-2 text-sm font-medium text-navy-700 hover:bg-navy-50 transition-colors"
          >
            <Download className="h-4 w-4" />
            Carta-Convite
          </button>
          <button
            onClick={() => handleDownload('certidao')}
            className="inline-flex items-center gap-2 rounded-lg border border-navy-200 px-4 py-2 text-sm font-medium text-navy-700 hover:bg-navy-50 transition-colors"
          >
            <Download className="h-4 w-4" />
            Certidao Negativa
          </button>
        </div>
      </div>

      {/* Event history */}
      <div className="rounded-xl bg-white border border-navy-200 shadow-sm p-5">
        <h3 className="text-sm font-semibold text-navy-900 mb-4 flex items-center gap-2">
          <History className="h-4 w-4 text-navy-600" />
          Historico de Eventos
        </h3>
        <TimelineEvento eventos={historico} />
      </div>
    </div>
  );
}
