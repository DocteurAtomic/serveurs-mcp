#!/usr/bin/env bash
# Sets up the lab: writes .env with random passwords if it is missing, downloads and checks
# the PachadataTraining backup, starts SQL Server, restores the reference database, creates
# the accounts pacha_app and mcp_reader and the Mcp schema, then the module copies.
# Usage: ./setup/install.sh
#   With Podman: COMPOSE="podman compose" ENGINE=podman ./setup/install.sh
# Running it again is safe: an existing .env, backup or database is kept.
set -euo pipefail
cd "$(dirname "$0")/.."
compose=${COMPOSE:-docker compose}
engine=${ENGINE:-docker}
c=mcpcourse

# 1. The passwords. They live in .env only (ignored by git), never in a committed file.
pw() { printf '%s-Aa1' "$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20)"; }
if [ ! -f .env ]; then
    # The server connects as mcp_reader, the account of module 8 on.
    reader=$(pw)
    umask 077
    sed -e "s/^MSSQL_SA_PASSWORD=.*/MSSQL_SA_PASSWORD=$(pw)/" \
        -e "s/^PACHA_APP_PASSWORD=.*/PACHA_APP_PASSWORD=$(pw)/" \
        -e "s/^MCP_READER_PASSWORD=.*/MCP_READER_PASSWORD=$reader/" \
        -e "s/^PACHA_SQL_PASSWORD=.*/PACHA_SQL_PASSWORD=$reader/" \
        .env.example > .env
    umask 022
    echo "Wrote .env with new random passwords."
fi
set -a; . ./.env; set +a

# 2. The backup, checked against its SHA-256.
mkdir -p setup/backup
bak=PachadataTraining-2026-10.bak
url='https://files.pachadata.com/public/api/raw?hash=tAsyC50c6kfVadBp3zc6TQ&file=/PachadataTraining/SqlServer/PachadataTraining-2026-10.bak'
sum=1d05970d8e0576cd0c57bddba64c2ba8a583845ad4744adeb75d2ea4a3f7d44e
if [ ! -f "setup/backup/$bak" ]; then
    echo "Downloading $bak (626 MB)..."
    curl -fL --retry 3 -o "setup/backup/$bak.part" "$url"
    mv "setup/backup/$bak.part" "setup/backup/$bak"
fi
if command -v sha256sum >/dev/null; then got=$(sha256sum "setup/backup/$bak" | cut -d' ' -f1)
else got=$(shasum -a 256 "setup/backup/$bak" | cut -d' ' -f1); fi
if [ "$got" != "$sum" ]; then
    echo "Checksum mismatch for setup/backup/$bak: delete it and run this script again." >&2
    exit 1
fi

# 3. SQL Server. The wait loop does not rely on "compose up --wait", which podman-compose lacks.
$compose up -d
sql() { $engine exec -i "$@" $c /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -b -I; }
echo -n "Waiting for SQL Server"
for _ in $(seq 1 60); do
    if $engine exec $c /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -l 2 -Q "SELECT 1" >/dev/null 2>&1; then
        echo " ready."; break
    fi
    echo -n "."; sleep 3
done
$engine exec $c /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -l 5 -b -Q "SELECT 1" >/dev/null

# 4. The reference database, then the accounts and the Mcp schema, then the module copies.
$engine exec -u 0 $c mkdir -p /var/opt/mssql/backup
if ! $engine exec $c test -f /var/opt/mssql/backup/$bak; then
    $engine cp "setup/backup/$bak" $c:/var/opt/mssql/backup/$bak
    $engine exec -u 0 $c chown mssql /var/opt/mssql/backup/$bak
fi
sql < setup/restore.sql
# The passwords reach sqlcmd as environment variables, which it reads as scripting
# variables: they never appear on a command line.
sql -e PACHA_APP_PASSWORD -e MCP_READER_PASSWORD < setup/accounts.sql
DB=PachadataTraining sql -e DB < setup/mcp-schema.sql
for m in m07 m09; do ENGINE=$engine ./setup/reset-copy.sh "$m" --if-missing; done
echo "Lab ready: SQL Server on 127.0.0.1,${SQLPORT:-14733}, database PachadataTraining."
