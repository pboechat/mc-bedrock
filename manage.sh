#!/usr/bin/env bash

set -e

# Configurable timeouts (in seconds)
SAVE_HOLD_WAIT=${SAVE_HOLD_WAIT:=2}
SHUTDOWN_GRACE_PERIOD=${SHUTDOWN_GRACE_PERIOD:=3}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

is_bedrock_running() {
    docker ps --filter "name=mc-bedrock" --filter "status=running" -q | grep -q .
}

exec_bedrock_command() {
    local cmd=("$@")
    local output

    if output="$(docker exec mc-bedrock "${cmd[@]}" 2>&1)"; then
        return 0
    fi

    if [[ "${VERBOSE_SAVE_ERRORS:-false}" == "true" ]] && [[ -n "$output" ]]; then
        echo "$output" >&2
    fi

    return 1
}

save_world_if_running() {
    if ! is_bedrock_running; then
        return 0
    fi

    echo "Saving world..."
    if ! exec_bedrock_command send-command save hold; then
        echo "WARNING: pre-stop save command unavailable; continuing with shutdown"
        return 0
    fi

    sleep "$SAVE_HOLD_WAIT"

    if ! exec_bedrock_command send-command save resume; then
        echo "WARNING: save resume failed; continuing with shutdown"
        return 0
    fi

    echo "Waiting for server to shut down gracefully..."
    sleep "$SHUTDOWN_GRACE_PERIOD"
}

case "${1:-}" in
    start)
        shift
        echo "Starting Minecraft Bedrock server..."
        docker compose up -d "$@"
        ;;
    stop)
        echo "Stopping Minecraft Bedrock server..."
        save_world_if_running
        docker compose down
        ;;
    restart)
        shift
        echo "Restarting Minecraft Bedrock server..."
        save_world_if_running
        docker compose down
        docker compose up -d "$@"
        ;;
    restart-mapper|mapper-restart)
        echo "Restarting mapper service only..."
        docker compose restart mapper
        ;;
    status)
        docker compose ps
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|restart-mapper|mapper-restart|status} [additional docker compose args]"
        echo ""
        echo "Commands:"
        echo "  start    - Start the server"
        echo "  stop     - Stop the server"
        echo "  restart  - Restart the server"
        echo "  restart-mapper (or mapper-restart) - Restart only the mapper service"
        echo "  status   - Show service status"
        exit 1
        ;;
esac
