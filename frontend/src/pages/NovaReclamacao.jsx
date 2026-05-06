import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api';
import { PlusCircle, AlertCircle, CheckCircle, ArrowLeft } from 'lucide-react';

export default function NovaReclamacao() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const [form, setForm] = useState({
    cejusc: 'CEJUSC-CENTRAL',
    // Reclamante
    reclamante_nome: '',
    reclamante_cpf_cnpj: '',
    reclamante_email: '',
    reclamante_telefone: '',
    reclamante_endereco_logradouro: '',
    reclamante_endereco_numero: '',
    reclamante_endereco_complemento: '',
    reclamante_endereco_bairro: '',
    reclamante_endereco_cidade: '',
    reclamante_endereco_uf: 'PR',
    reclamante_endereco_cep: '',
    // Reclamado
    reclamado_nome: '',
    reclamado_cpf_cnpj: '',
    reclamado_email: '',
    reclamado_telefone: '',
    reclamado_endereco_logradouro: '',
    reclamado_endereco_numero: '',
    reclamado_endereco_complemento: '',
    reclamado_endereco_bairro: '',
    reclamado_endereco_cidade: '',
    reclamado_endereco_uf: 'PR',
    reclamado_endereco_cep: '',
    // Reclamacao
    fatos: '',
    pedidos_descricao: '',
    pedidos_valor: '',
    valor_causa: '',
    modalidade: 'CONCILIACAO',
    opcao_gratuidade: false,
  });

  const UFS = [
    'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS',
    'MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC',
    'SP','SE','TO',
  ];

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const payload = {
      cejusc: form.cejusc,
      reclamante: {
        nome: form.reclamante_nome,
        cpf_cnpj: form.reclamante_cpf_cnpj,
        email: form.reclamante_email,
        telefone: form.reclamante_telefone,
        endereco: {
          logradouro: form.reclamante_endereco_logradouro,
          numero: form.reclamante_endereco_numero,
          complemento: form.reclamante_endereco_complemento || null,
          bairro: form.reclamante_endereco_bairro,
          cidade: form.reclamante_endereco_cidade,
          uf: form.reclamante_endereco_uf,
          cep: form.reclamante_endereco_cep,
        },
      },
      reclamado: {
        nome: form.reclamado_nome,
        cpf_cnpj: form.reclamado_cpf_cnpj,
        email: form.reclamado_email,
        telefone: form.reclamado_telefone,
        endereco: {
          logradouro: form.reclamado_endereco_logradouro,
          numero: form.reclamado_endereco_numero,
          complemento: form.reclamado_endereco_complemento || null,
          bairro: form.reclamado_endereco_bairro,
          cidade: form.reclamado_endereco_cidade,
          uf: form.reclamado_endereco_uf,
          cep: form.reclamado_endereco_cep,
        },
      },
      fatos: form.fatos,
      pedidos: [
        {
          descricao: form.pedidos_descricao,
          valor: form.pedidos_valor ? parseFloat(form.pedidos_valor) : null,
        },
      ],
      valor_causa: parseFloat(form.valor_causa),
      modalidade: form.modalidade,
      opcao_gratuidade: form.opcao_gratuidade,
    };

    try {
      const res = await api.post('/reclamacoes/', payload);
      setSuccess(true);
      setTimeout(() => {
        navigate(`/reclamacoes/${res.data.id}`);
      }, 1500);
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail.map((d) => `${d.loc?.join('.')}: ${d.msg}`).join('; '));
      } else if (typeof detail === 'string') {
        setError(detail);
      } else {
        setError('Erro ao criar reclamacao. Verifique os dados e tente novamente.');
      }
    } finally {
      setLoading(false);
    }
  };

  const inputClass =
    'w-full rounded-lg border border-navy-300 bg-white px-3.5 py-2.5 text-sm text-navy-900 placeholder:text-navy-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 focus:outline-none transition-colors';
  const labelClass = 'block text-sm font-medium text-navy-700 mb-1.5';

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/reclamacoes')}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-navy-600 hover:bg-navy-100 transition-colors"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-navy-900">Nova Reclamacao</h1>
          <p className="text-sm text-navy-500 mt-0.5">
            Preencha os dados conforme art. 9 da Res. 403/2023
          </p>
        </div>
      </div>

      {success && (
        <div className="flex items-center gap-2 rounded-lg bg-green-50 border border-green-200 p-4 text-sm text-green-700">
          <CheckCircle className="h-5 w-5 shrink-0" />
          Reclamacao protocolada com sucesso! Redirecionando...
        </div>
      )}

      {error && (
        <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700">
          <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
          <div>{error}</div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* CEJUSC e Modalidade */}
        <div className="rounded-xl bg-white border border-navy-200 shadow-sm p-6">
          <h2 className="text-base font-semibold text-navy-900 mb-4">Dados Gerais</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className={labelClass}>Centro CEJUSC</label>
              <input
                name="cejusc"
                value={form.cejusc}
                onChange={handleChange}
                required
                className={inputClass}
                placeholder="CEJUSC-CENTRAL"
              />
            </div>
            <div>
              <label className={labelClass}>Modalidade</label>
              <select
                name="modalidade"
                value={form.modalidade}
                onChange={handleChange}
                className={inputClass}
              >
                <option value="CONCILIACAO">Conciliacao</option>
                <option value="MEDIACAO">Mediacao</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>Valor da Causa (R$)</label>
              <input
                name="valor_causa"
                type="number"
                step="0.01"
                min="0.01"
                value={form.valor_causa}
                onChange={handleChange}
                required
                className={inputClass}
                placeholder="0,00"
              />
            </div>
          </div>
          <div className="mt-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                name="opcao_gratuidade"
                checked={form.opcao_gratuidade}
                onChange={handleChange}
                className="h-4 w-4 rounded border-navy-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-navy-700">Solicitar gratuidade de justica</span>
            </label>
          </div>
        </div>

        {/* Reclamante */}
        <div className="rounded-xl bg-white border border-navy-200 shadow-sm p-6">
          <h2 className="text-base font-semibold text-navy-900 mb-4">Reclamante (Solicitante)</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Nome completo</label>
              <input name="reclamante_nome" value={form.reclamante_nome} onChange={handleChange} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>CPF / CNPJ</label>
              <input name="reclamante_cpf_cnpj" value={form.reclamante_cpf_cnpj} onChange={handleChange} required className={inputClass} placeholder="000.000.000-00" />
            </div>
            <div>
              <label className={labelClass}>E-mail</label>
              <input name="reclamante_email" type="email" value={form.reclamante_email} onChange={handleChange} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Telefone</label>
              <input name="reclamante_telefone" value={form.reclamante_telefone} onChange={handleChange} required className={inputClass} placeholder="(41) 99999-9999" />
            </div>
          </div>
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="sm:col-span-2">
              <label className={labelClass}>Logradouro</label>
              <input name="reclamante_endereco_logradouro" value={form.reclamante_endereco_logradouro} onChange={handleChange} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Numero</label>
              <input name="reclamante_endereco_numero" value={form.reclamante_endereco_numero} onChange={handleChange} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Complemento</label>
              <input name="reclamante_endereco_complemento" value={form.reclamante_endereco_complemento} onChange={handleChange} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Bairro</label>
              <input name="reclamante_endereco_bairro" value={form.reclamante_endereco_bairro} onChange={handleChange} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Cidade</label>
              <input name="reclamante_endereco_cidade" value={form.reclamante_endereco_cidade} onChange={handleChange} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>UF</label>
              <select name="reclamante_endereco_uf" value={form.reclamante_endereco_uf} onChange={handleChange} className={inputClass}>
                {UFS.map((uf) => <option key={uf} value={uf}>{uf}</option>)}
              </select>
            </div>
            <div>
              <label className={labelClass}>CEP</label>
              <input name="reclamante_endereco_cep" value={form.reclamante_endereco_cep} onChange={handleChange} required className={inputClass} placeholder="00000-000" />
            </div>
          </div>
        </div>

        {/* Reclamado */}
        <div className="rounded-xl bg-white border border-navy-200 shadow-sm p-6">
          <h2 className="text-base font-semibold text-navy-900 mb-4">Reclamado</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Nome completo / Razao Social</label>
              <input name="reclamado_nome" value={form.reclamado_nome} onChange={handleChange} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>CPF / CNPJ</label>
              <input name="reclamado_cpf_cnpj" value={form.reclamado_cpf_cnpj} onChange={handleChange} required className={inputClass} placeholder="000.000.000-00" />
            </div>
            <div>
              <label className={labelClass}>E-mail</label>
              <input name="reclamado_email" type="email" value={form.reclamado_email} onChange={handleChange} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Telefone</label>
              <input name="reclamado_telefone" value={form.reclamado_telefone} onChange={handleChange} required className={inputClass} placeholder="(41) 99999-9999" />
            </div>
          </div>
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="sm:col-span-2">
              <label className={labelClass}>Logradouro</label>
              <input name="reclamado_endereco_logradouro" value={form.reclamado_endereco_logradouro} onChange={handleChange} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Numero</label>
              <input name="reclamado_endereco_numero" value={form.reclamado_endereco_numero} onChange={handleChange} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Complemento</label>
              <input name="reclamado_endereco_complemento" value={form.reclamado_endereco_complemento} onChange={handleChange} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Bairro</label>
              <input name="reclamado_endereco_bairro" value={form.reclamado_endereco_bairro} onChange={handleChange} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Cidade</label>
              <input name="reclamado_endereco_cidade" value={form.reclamado_endereco_cidade} onChange={handleChange} required className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>UF</label>
              <select name="reclamado_endereco_uf" value={form.reclamado_endereco_uf} onChange={handleChange} className={inputClass}>
                {UFS.map((uf) => <option key={uf} value={uf}>{uf}</option>)}
              </select>
            </div>
            <div>
              <label className={labelClass}>CEP</label>
              <input name="reclamado_endereco_cep" value={form.reclamado_endereco_cep} onChange={handleChange} required className={inputClass} placeholder="00000-000" />
            </div>
          </div>
        </div>

        {/* Fatos e Pedidos */}
        <div className="rounded-xl bg-white border border-navy-200 shadow-sm p-6">
          <h2 className="text-base font-semibold text-navy-900 mb-4">Fatos e Pedidos</h2>
          <div className="space-y-4">
            <div>
              <label className={labelClass}>Breve relato dos fatos</label>
              <textarea
                name="fatos"
                value={form.fatos}
                onChange={handleChange}
                required
                rows={4}
                className={inputClass}
                placeholder="Descreva brevemente os fatos que motivam esta reclamacao..."
              />
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className={labelClass}>Descricao do pedido</label>
                <input
                  name="pedidos_descricao"
                  value={form.pedidos_descricao}
                  onChange={handleChange}
                  required
                  className={inputClass}
                  placeholder="Ex: Devolucao de valores"
                />
              </div>
              <div>
                <label className={labelClass}>Valor do pedido (R$)</label>
                <input
                  name="pedidos_valor"
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.pedidos_valor}
                  onChange={handleChange}
                  className={inputClass}
                  placeholder="0,00"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end gap-3">
          <button
            type="button"
            onClick={() => navigate('/reclamacoes')}
            className="rounded-lg px-5 py-2.5 text-sm font-medium text-navy-600 hover:bg-navy-100 transition-colors"
          >
            Cancelar
          </button>
          <button
            type="submit"
            disabled={loading || success}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <PlusCircle className="h-4 w-4" />
            )}
            Protocolar Reclamacao
          </button>
        </div>
      </form>
    </div>
  );
}
