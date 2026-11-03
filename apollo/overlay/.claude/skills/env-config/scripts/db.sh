#!/usr/bin/env bash
# Thin wrapper around Db.java: finds a MySQL driver in ~/.m2 and runs the single-file program.
# Usage: db.sh <env> <database> [--write --confirm] [--max-rows N] ("<sql>" | -f file.sql)
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JAR="$(ls -1 "$HOME"/.m2/repository/com/mysql/mysql-connector-j/*/mysql-connector-j-*[0-9].jar 2>/dev/null | sort -V | tail -1)"
[ -n "$JAR" ] || { echo "no mysql-connector-j in ~/.m2" >&2; exit 1; }
JAVA_BIN="$(command -v java)"
exec "$JAVA_BIN" -cp "$JAR" "$DIR/Db.java" "$@" 2> >(grep -v '^Picked up JAVA_TOOL_OPTIONS' >&2)
