#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "[setup-local-env] [${GREEN}INFO${NC}] $*"
}

log_warn() {
    echo -e "[setup-local-env] [${YELLOW}WARN${NC}] $*"
}

log_error() {
    echo -e "[setup-local-env] [${RED}ERROR${NC}] $*"
}

on_error() {
    local exit_code=$?
    local line_no="${BASH_LINENO[0]:-?}"
    local source_file="${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}"
    log_error "Command failed (exit ${exit_code}) at ${source_file}:${line_no}: ${BASH_COMMAND}"
    exit "$exit_code"
}

trap 'on_error' ERR

# Check if running on Ubuntu
check_ubuntu() {
    if [[ ! -f /etc/os-release ]]; then
        log_error "Cannot detect OS - /etc/os-release not found"
        exit 1
    fi

    source /etc/os-release
    if [[ "$ID" != "ubuntu" ]]; then
        log_error "This script is designed for Ubuntu. Detected OS: $ID"
        log_warn "You may need to adapt package names for your distribution."
        exit 1
    fi

    log_info "Detected Ubuntu $VERSION_ID"
}

run_installation() {
    local install_script="$SCRIPT_DIR/install-deps.sh"
    local bluemap_version="${1:-5.16}"
    local bluemap_dir="$HOME/.local/bluemap"
    local cmake_dir="$HOME/.local/cmake"
    local work_base_dir="$HOME/.local/bluemap-mapper"
    local venv_dir="$SCRIPT_DIR/.venv"
    
    if [[ ! -f "$install_script" ]]; then
        log_error "Installation script not found: $install_script"
        exit 1
    fi
    
    log_info "Running shared installation script..."
    log_info "BlueMap version: $bluemap_version"
    log_info "BlueMap directory: $bluemap_dir"
    log_info "CMake directory: $cmake_dir"
    log_info "Work directory: $work_base_dir"
    log_info "Python venv directory: $venv_dir"
    
    # Set VENV_DIR and CMAKE_DIR in environment before calling install-deps.sh
    VENV_DIR="$venv_dir" CMAKE_DIR="$cmake_dir" bash "$install_script" "$bluemap_version" true "$bluemap_dir" "$work_base_dir"
    
    log_info "Installation complete"
    log_info "BlueMap CLI installed at: $bluemap_dir/BlueMap-cli.jar"
    log_info "CMake installed at: $cmake_dir"
    log_info "Work directories created at: $work_base_dir/"
    log_info "Python venv created at: $venv_dir/"
}

# Main execution
main() {
    log_info "=== Mapper Local Environment Setup ==="
    log_info "This script will install system dependencies and set up BlueMap locally"
    echo

    check_ubuntu
    
    log_info "This script requires sudo access to install system packages"
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Setup cancelled"
        exit 0
    fi

    local bluemap_version="${1:-5.16}"
    run_installation "$bluemap_version"

    echo
    log_info "=== Setup Complete ==="
    log_info "Environment configured for local development:"
    log_info "  - System dependencies installed"
    log_info "  - CMake >= 4.1 installed at: $HOME/.local/cmake"
    log_info "  - BlueMap CLI at: $HOME/.local/bluemap/BlueMap-cli.jar"
    log_info "  - Output directory: $REPO_ROOT/mapper-output/"
    log_info "  - Python venv at: $SCRIPT_DIR/.venv/"
    log_info ""
    log_info "To use the environment:"
    log_info "  1. Activate virtual environment:"
    log_info "     source $SCRIPT_DIR/.venv/bin/activate"
    log_info "  2. Ensure CMake is first in PATH for local shells:"
    log_info "     export PATH=$HOME/.local/cmake/bin:\$PATH"
    log_info ""
    log_info "  3. Run the mapper:"
    log_info "     python $REPO_ROOT/mapper/mapper.py \\"
    log_info "       --bedrock-world-dir $REPO_ROOT/data/worlds/world \\"
    log_info "       --output-path $REPO_ROOT/mapper-output \\"
    log_info "       --config-dir $HOME/.config/bluemap \\"
    log_info "       --bluemap-jar $HOME/.local/bluemap/BlueMap-cli.jar"
    echo
}

main "$@"
