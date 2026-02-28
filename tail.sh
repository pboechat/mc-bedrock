#!/usr/bin/env bash

set -e

case "${1:-}" in
    mc-bedrock)
         shift
         docker logs -f mc-bedrock "$@"
         ;;
    mc-map)
        shift
        docker logs -f mc-map "$@"
        ;;
    *)
        echo "Usage: $0 {mc-bedrock|mc-map} [additional docker logs args]"
        echo ""
        echo "Commands:"
        echo "  mc-bedrock    - Tail logs for Minecraft Bedrock server"
        echo "  mc-map        - Tail logs for Minecraft Map server"
        exit 1
        ;;
esac
