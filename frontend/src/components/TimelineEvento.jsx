import { Clock, User, ArrowRight } from 'lucide-react';
import EstadoBadge from './EstadoBadge';

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function TimelineEvento({ eventos }) {
  if (!eventos || eventos.length === 0) {
    return (
      <div className="text-center py-8 text-navy-500">
        Nenhum evento registrado.
      </div>
    );
  }

  return (
    <div className="flow-root">
      <ul className="-mb-8">
        {eventos.map((evento, idx) => (
          <li key={evento.id || idx}>
            <div className="relative pb-8">
              {idx < eventos.length - 1 && (
                <span
                  className="absolute top-5 left-5 -ml-px h-full w-0.5 bg-navy-200"
                  aria-hidden="true"
                />
              )}
              <div className="relative flex items-start space-x-3">
                <div className="relative">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-navy-100 ring-4 ring-white">
                    <ArrowRight className="h-4 w-4 text-navy-600" />
                  </div>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <EstadoBadge estado={evento.tipo} size="sm" />
                    {evento.estado_destino && evento.estado_destino !== evento.tipo && (
                      <>
                        <ArrowRight className="h-3 w-3 text-navy-400" />
                        <EstadoBadge estado={evento.estado_destino} size="sm" />
                      </>
                    )}
                  </div>
                  <div className="mt-1.5 flex items-center gap-3 text-xs text-navy-500">
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatDate(evento.timestamp)}
                    </span>
                    {evento.ator_tipo && (
                      <span className="inline-flex items-center gap-1">
                        <User className="h-3 w-3" />
                        {evento.ator_tipo}
                      </span>
                    )}
                  </div>
                  {evento.payload && Object.keys(evento.payload).length > 0 && (
                    <div className="mt-2 rounded-md bg-navy-50 p-2 text-xs text-navy-600">
                      {Object.entries(evento.payload).map(([key, value]) => (
                        <div key={key}>
                          <span className="font-medium">{key}:</span>{' '}
                          {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
