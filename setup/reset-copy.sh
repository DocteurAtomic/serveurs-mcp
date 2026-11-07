#!/usr/bin/env bash
# Recreates the copy of the database that a module writes to, from the delivered backup, so
# that the reference database PachadataTraining is never written.
# Usage: ./setup/reset-copy.sh m07              recreate PachadataTraining_m07
#        ./setup/reset-copy.sh m07 --if-missing create it only if it does not exist
#        ./setup/reset-copy.sh m07 --drop       drop it
#   With Podman: ENGINE=podman ./setup/reset-copy.sh m07
# A copy takes a few seconds and about 1.5 GB of disk once its log is shrunk.
set -euo pipefail
cd "$(dirname "$0")/.."
engine=${ENGINE:-docker}
c=mcpcourse
case "${1:-}" in m[0-9][0-9]) ;; *) echo "usage: $0 mNN [--if-missing|--drop]" >&2; exit 2;; esac
db=PachadataTraining_$1
sql() { $engine exec -i "$@" $c /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -b -I; }
exists=$($engine exec $c /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -C -h -1 -W \
    -Q "SET NOCOUNT ON; SELECT COUNT(*) FROM sys.databases WHERE name = N'$db'")
case "${2:-}" in
    --drop)
        if [ "$exists" = 1 ]; then
            echo "ALTER DATABASE [$db] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [$db];" | sql
            echo "Dropped $db."
        fi
        exit 0;;
    --if-missing)
        if [ "$exists" = 1 ]; then echo "$db already exists: kept."; exit 0; fi;;
    "") ;;
    *) echo "usage: $0 mNN [--if-missing|--drop]" >&2; exit 2;;
esac
echo "EXEC master.dbo.restore_training @db = N'$db';" | sql
# The restored log keeps the 1.2 GB of the original; the copy needs a few megabytes.
echo "USE [$db]; DBCC SHRINKFILE (N'PachadataTraining_log', 64) WITH NO_INFOMSGS;" | sql >/dev/null
DB=$db sql -e DB < setup/mcp-schema.sql
echo "Recreated $db."
