#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE bria_mcp;
    CREATE DATABASE bria_dashboard;
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d bria_mcp     -f /migrations/mcp_db.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d bria_dashboard -f /migrations/dashboard_db.sql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d bria_dashboard -f /migrations/exchange_public.sql