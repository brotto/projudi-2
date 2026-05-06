const ESTADO_CONFIG = {
  SOLICITACAO_RECEBIDA: {
    label: 'Solicitacao Recebida',
    bg: 'bg-gray-100',
    text: 'text-gray-700',
    dot: 'bg-gray-400',
  },
  TRIAGEM: {
    label: 'Triagem',
    bg: 'bg-yellow-50',
    text: 'text-yellow-800',
    dot: 'bg-yellow-400',
  },
  VERIFICACAO_CUSTAS: {
    label: 'Verificacao de Custas',
    bg: 'bg-yellow-50',
    text: 'text-yellow-800',
    dot: 'bg-yellow-400',
  },
  ANALISE_GRATUIDADE: {
    label: 'Analise de Gratuidade',
    bg: 'bg-yellow-50',
    text: 'text-yellow-800',
    dot: 'bg-yellow-400',
  },
  CADASTRADO: {
    label: 'Cadastrado',
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    dot: 'bg-blue-400',
  },
  SESSAO_AGENDADA: {
    label: 'Sessao Agendada',
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    dot: 'bg-blue-400',
  },
  NOTIFICACOES_ENVIADAS: {
    label: 'Notificacoes Enviadas',
    bg: 'bg-blue-50',
    text: 'text-blue-700',
    dot: 'bg-blue-400',
  },
  SESSAO_CONDUZIDA: {
    label: 'Sessao Conduzida',
    bg: 'bg-indigo-50',
    text: 'text-indigo-700',
    dot: 'bg-indigo-400',
  },
  SESSAO_CONTINUADA: {
    label: 'Sessao Continuada',
    bg: 'bg-indigo-50',
    text: 'text-indigo-700',
    dot: 'bg-indigo-400',
  },
  ACORDO_REDIGIDO: {
    label: 'Acordo Redigido',
    bg: 'bg-purple-50',
    text: 'text-purple-700',
    dot: 'bg-purple-400',
  },
  AGUARDANDO_MP: {
    label: 'Aguardando MP',
    bg: 'bg-purple-50',
    text: 'text-purple-700',
    dot: 'bg-purple-400',
  },
  CONCLUSO_JUIZ: {
    label: 'Concluso ao Juiz',
    bg: 'bg-purple-50',
    text: 'text-purple-700',
    dot: 'bg-purple-400',
  },
  HOMOLOGADO: {
    label: 'Homologado',
    bg: 'bg-green-50',
    text: 'text-green-700',
    dot: 'bg-green-500',
  },
  ARQUIVADO_ACORDO: {
    label: 'Arquivado (Acordo)',
    bg: 'bg-emerald-50',
    text: 'text-emerald-700',
    dot: 'bg-emerald-500',
  },
  ARQUIVADO_SEM_ACORDO: {
    label: 'Arquivado (Sem Acordo)',
    bg: 'bg-red-50',
    text: 'text-red-700',
    dot: 'bg-red-400',
  },
  ARQUIVADO_AUSENCIA: {
    label: 'Arquivado (Ausencia)',
    bg: 'bg-red-50',
    text: 'text-red-700',
    dot: 'bg-red-400',
  },
  ARQUIVADO_FALTA_CUSTAS: {
    label: 'Arquivado (Falta Custas)',
    bg: 'bg-red-50',
    text: 'text-red-700',
    dot: 'bg-red-400',
  },
  ARQUIVADO_INCOMPETENTE: {
    label: 'Arquivado (Incompetente)',
    bg: 'bg-red-50',
    text: 'text-red-700',
    dot: 'bg-red-400',
  },
  ARQUIVADO_IRREGULAR: {
    label: 'Arquivado (Irregular)',
    bg: 'bg-red-50',
    text: 'text-red-700',
    dot: 'bg-red-400',
  },
};

export function getEstadoConfig(estado) {
  return ESTADO_CONFIG[estado] || {
    label: estado,
    bg: 'bg-gray-100',
    text: 'text-gray-600',
    dot: 'bg-gray-400',
  };
}

export default function EstadoBadge({ estado, size = 'md' }) {
  const config = getEstadoConfig(estado);
  const sizeClasses = size === 'sm'
    ? 'text-xs px-2 py-0.5'
    : 'text-sm px-2.5 py-1';

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium ${config.bg} ${config.text} ${sizeClasses}`}
    >
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  );
}
