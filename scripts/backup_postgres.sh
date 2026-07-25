#!/bin/bash
# Backup do banco de preços (Postgres self-hosted na VPS -- não tem backup
# automático como um serviço gerenciado, então isso cobre essa lacuna).
#
# Uso (na VPS, dentro do container ou com pg_dump instalado localmente):
#   ./scripts/backup_postgres.sh
#
# Agendar via cron (fora do Kestra, pra não depender dele) ou como uma
# tarefa do próprio Kestra mais pra frente -- ex, todo dia às 3h:
#   0 3 * * * /caminho/do/projeto/scripts/backup_postgres.sh >> /var/log/backup_precos.log 2>&1
set -euo pipefail

DIR_BACKUP="${DIR_BACKUP:-/var/backups/price-crawler}"
DIAS_RETENCAO="${DIAS_RETENCAO:-14}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_DB="${POSTGRES_DB:-precos}"
POSTGRES_USER="${POSTGRES_USER:-crawler}"
# POSTGRES_PASSWORD vem do ambiente (ou de um .pgpass) -- não hardcode aqui

mkdir -p "$DIR_BACKUP"

ARQUIVO="$DIR_BACKUP/precos_$(date +%Y%m%d_%H%M%S).dump"

pg_dump --host="$POSTGRES_HOST" --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" \
    --format=custom --file="$ARQUIVO"

echo "Backup salvo em $ARQUIVO"

# remove backups mais antigos que DIAS_RETENCAO
find "$DIR_BACKUP" -name "precos_*.dump" -mtime "+$DIAS_RETENCAO" -delete

echo "Backups com mais de $DIAS_RETENCAO dias removidos."
