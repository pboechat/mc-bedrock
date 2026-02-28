#!/usr/bin/env bash

set -e

MINECRAFT_PORT="${MINECRAFT_PORT:=19132}"
MAPPER_PORT="${MAPPER_PORT:=8100}"

case "${1:-}" in
    on|allow|enable)
        echo "Opening firewall port ${MINECRAFT_PORT}/udp..."
        sudo ufw allow ${MINECRAFT_PORT}/udp
        sudo ufw allow ${MAPPER_PORT}/tcp
        echo "Firewall rule added."
        ;;
    off|deny|disable)
        echo "Closing firewall port ${MINECRAFT_PORT}/udp..."
        sudo ufw delete allow ${MINECRAFT_PORT}/udp
        sudo ufw delete allow ${MAPPER_PORT}/tcp
        echo "Firewall rule removed."
        ;;
    status)
        echo "Checking firewall status for port ${MINECRAFT_PORT}..."
        sudo ufw status | grep ${MINECRAFT_PORT} || echo "No rules found for port ${MINECRAFT_PORT}"
        echo "Checking firewall status for port ${MAPPER_PORT}..."
        sudo ufw status | grep ${MAPPER_PORT} || echo "No rules found for port ${MAPPER_PORT}"
        ;;
    *)
        echo "Usage: $0 {on|off|status} [MINECRAFT_PORT]"
        echo ""
        echo "Commands:"
        echo "  on       - Allow Minecraft port through firewall (aliases: allow, enable)"
        echo "  off      - Remove Minecraft port from firewall (aliases: deny, disable)"
        echo "  status   - Check firewall rules for Minecraft port"
        echo ""
        echo "Environment variables:"
        echo "  MINECRAFT_PORT - Port number (default: 19132)"
        echo "  MAPPER_PORT    - Port number for mapper web server (default: 8100)"
        echo ""
        echo "Examples:"
        echo "  $0 on"
        echo "  MINECRAFT_PORT=25565 $0 on"
        exit 1
        ;;
esac
