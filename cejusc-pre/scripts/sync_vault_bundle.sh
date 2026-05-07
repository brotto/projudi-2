#!/usr/bin/env bash
# Sincroniza templates do Vault Obsidian local para o bundle versionado do repo.
# Use após editar templates em ~/Documents/CEJUSC Pre Vault/ e antes de fazer
# push, para que o container em produção receba a versão atualizada.
#
# Uso: ./scripts/sync_vault_bundle.sh

set -euo pipefail

SRC="${VAULT_SRC:-/Users/alebrotto/Documents/CEJUSC Pre Vault}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DST="$HERE/vault_bundle"

if [ ! -d "$SRC" ]; then
  echo "❌ Vault não encontrado em: $SRC" >&2
  echo "   Defina VAULT_SRC=/caminho/seu/vault e tente novamente." >&2
  exit 1
fi

echo "📋 Sincronizando $SRC → $DST"

mkdir -p "$DST/wiki/templates-rascunho"

# Limpa antes pra remover templates que possam ter sido excluídos no Vault
rm -f "$DST"/*.md
rm -f "$DST/wiki/templates-rascunho/"*.md

# Templates canônicos da raiz (exclui manuais e schema)
find "$SRC" -maxdepth 1 -name "*.md" \
  ! -name "CLAUDE.md" \
  ! -name "MANUAL PRÉ.md" \
  ! -name "Manual de Atendimento – Pré.md" \
  -exec cp {} "$DST/" \;

# Rascunhos
if compgen -G "$SRC/wiki/templates-rascunho/*.md" > /dev/null; then
  cp "$SRC/wiki/templates-rascunho/"*.md "$DST/wiki/templates-rascunho/"
fi

n_canonicos=$(find "$DST" -maxdepth 1 -name "*.md" | wc -l | tr -d ' ')
n_rascunhos=$(find "$DST/wiki/templates-rascunho" -name "*.md" | wc -l | tr -d ' ')

echo "✅ $n_canonicos canônicos · $n_rascunhos rascunhos"
echo "    Lembre de commitar e pushar o repo para o container puxar a atualização."
