import { useState } from 'react';
import { ArrowRight, X, AlertTriangle } from 'lucide-react';
import { getEstadoConfig } from './EstadoBadge';

export default function TransicaoButton({ estadoDestino, onConfirm, loading }) {
  const [showModal, setShowModal] = useState(false);
  const config = getEstadoConfig(estadoDestino);
  const isArchive = estadoDestino.startsWith('ARQUIVADO');

  return (
    <>
      <button
        onClick={() => setShowModal(true)}
        disabled={loading}
        className={`inline-flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all
          ${isArchive
            ? 'bg-red-50 text-red-700 hover:bg-red-100 border border-red-200'
            : 'bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200'
          }
          disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        <ArrowRight className="h-4 w-4" />
        {config.label}
      </button>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className={`flex h-10 w-10 items-center justify-center rounded-full ${
                isArchive ? 'bg-red-100' : 'bg-blue-100'
              }`}>
                <AlertTriangle className={`h-5 w-5 ${
                  isArchive ? 'text-red-600' : 'text-blue-600'
                }`} />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-navy-900">
                  Confirmar Transicao
                </h3>
                <p className="text-sm text-navy-500">
                  Esta acao nao pode ser desfeita.
                </p>
              </div>
            </div>

            <div className="bg-navy-50 rounded-lg p-4 mb-6">
              <p className="text-sm text-navy-700">
                Deseja mover para o estado:
              </p>
              <p className="text-lg font-semibold text-navy-900 mt-1">
                {config.label}
              </p>
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowModal(false)}
                className="inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-navy-600 hover:bg-navy-100 transition-colors"
              >
                <X className="h-4 w-4" />
                Cancelar
              </button>
              <button
                onClick={() => {
                  setShowModal(false);
                  onConfirm(estadoDestino);
                }}
                disabled={loading}
                className={`inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors
                  ${isArchive
                    ? 'bg-red-600 hover:bg-red-700'
                    : 'bg-blue-600 hover:bg-blue-700'
                  }
                  disabled:opacity-50`}
              >
                <ArrowRight className="h-4 w-4" />
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
