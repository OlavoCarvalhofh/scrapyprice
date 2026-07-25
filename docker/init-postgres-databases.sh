#!/bin/bash
# Roda automaticamente na primeira inicialização do container do Postgres
# (docker-entrypoint-initdb.d) -- cria o banco do Kestra além do banco
# principal de preços (que já vem do POSTGRES_DB no docker-compose.yml).
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE kestra;
    GRANT ALL PRIVILEGES ON DATABASE kestra TO "$POSTGRES_USER";
EOSQL
