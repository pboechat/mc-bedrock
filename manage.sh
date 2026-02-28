#!/usr/bin/env bash

set -e

# Configurable timeouts (in seconds)
SAVE_HOLD_WAIT=${SAVE_HOLD_WAIT:=2}
SHUTDOWN_GRACE_PERIOD=${SHUTDOWN_GRACE_PERIOD:=3}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

case "${1:-}" in
    start)
        shift
        echo "Starting Minecraft Bedrock server..."
        docker compose up -d "$@"
        ;;
    stop)
        echo "Stopping Minecraft Bedrock server..."
        if docker ps --filter "name=mc-bedrock" --filter "status=running" -q | grep -q .; then
            echo "Saving world..."
            docker exec mc-bedrock send-command save hold
            sleep "$SAVE_HOLD_WAIT"
            docker exec mc-bedrock send-command save resume
            echo "Waiting for server to shut down gracefully..."
            sleep "$SHUTDOWN_GRACE_PERIOD"
        fi
        docker compose down
        ;;
    restart)
        shift
        echo "Restarting Minecraft Bedrock server..."
        if docker ps --filter "name=mc-bedrock" --filter "status=running" -q | grep -q .; then
            echo "Saving world..."
            docker exec mc-bedrock send-command save hold
            sleep "$SAVE_HOLD_WAIT"
            docker exec mc-bedrock send-command save resume
            echo "Waiting for server to shut down gracefully..."
            sleep "$SHUTDOWN_GRACE_PERIOD"
        fi
        docker compose down
        docker compose up -d "$@"
        ;;
    status)
        docker compose ps
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status} [additional docker compose args]"
        echo ""
        echo "Commands:"
        echo "  start    - Start the server"
        echo "  stop     - Stop the server"
        echo "  restart  - Restart the server"
        echo "  status   - Show service status"
        exit 1
        ;;
esac
