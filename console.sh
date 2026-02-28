#!/usr/bin/env bash

set -e

case "${1:-}" in
    mc-bedrock)
         shift
         docker attach mc-bedrock "$@"
         ;;
    mc-map)
        shift
        docker attach mc-map "$@"
        ;;
    *)
        echo "Usage: $0 {mc-bedrock|mc-map} [additional docker attach args]"
        echo ""
        echo "Commands:"
        echo "  mc-bedrock    - Attach to Minecraft Bedrock server container"
        echo "  mc-map        - Attach to Minecraft Map server container"
        exit 1
        ;;
esac
