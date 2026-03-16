#!/bin/bash
# wait-for-it.sh — Aguarda um host:porta ficar disponível
# Uso: ./wait-for-it.sh host:port [-t timeout] [-- command]

set -e

HOST=""
PORT=""
TIMEOUT=30
CMD=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        *:* )
            HOST="${1%%:*}"
            PORT="${1##*:}"
            shift
            ;;
        -t)
            TIMEOUT="$2"
            shift 2
            ;;
        --)
            shift
            CMD="$*"
            break
            ;;
        *)
            shift
            ;;
    esac
done

if [ -z "$HOST" ] || [ -z "$PORT" ]; then
    echo "Usage: $0 host:port [-t timeout] [-- command]"
    exit 1
fi

echo "Waiting for $HOST:$PORT (timeout: ${TIMEOUT}s)..."

for i in $(seq 1 "$TIMEOUT"); do
    if nc -z "$HOST" "$PORT" 2>/dev/null; then
        echo "$HOST:$PORT is available after ${i}s"
        if [ -n "$CMD" ]; then
            exec $CMD
        fi
        exit 0
    fi
    sleep 1
done

echo "Timeout waiting for $HOST:$PORT"
exit 1
