#!/bin/sh
set -eu
app_password=$(cat /run/secrets/app_password)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=app_password="$app_password" <<'SQL'
CREATE ROLE pqm_app LOGIN PASSWORD :'app_password';
GRANT CONNECT ON DATABASE pqm TO pqm_app;
GRANT USAGE, CREATE ON SCHEMA public TO pqm_app;
SQL
