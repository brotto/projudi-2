# Sistema Juízo · CEJUSC Pré · agent service
# Uvicorn + FastAPI servindo as rotas do agente IA + monorepo cejusc-pre.
#
# Build context: este Dockerfile espera ser construído com o contexto na raiz
# do monorepo `Projudi 2.o/`. EasyPanel faz isso automaticamente quando o
# build_path é configurado para apontar a raiz do repo + dockerfile=cejusc-pre/Dockerfile.

FROM python:3.12-slim AS base

# System deps para pdfplumber (libpoppler is bundled in pdfminer.six;
# we still need build-essential for some wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 1) deps primeiro pra cache eficiente
COPY cejusc-pre/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# 2) código + bundle de templates do Vault
COPY cejusc-pre/ /app/cejusc-pre/

# Em produção, o vault_bundle versionado serve como fonte de templates.
# JUIZO_VAULT_PATH aponta pra ele. JUIZO_LLM_PROVIDER=openrouter (default).
ENV JUIZO_VAULT_PATH=/app/cejusc-pre/vault_bundle \
    PYTHONPATH=/app/cejusc-pre

WORKDIR /app/cejusc-pre

# Healthcheck — Easypanel monitora isso pra detectar serviço derrubado
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/agent/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
