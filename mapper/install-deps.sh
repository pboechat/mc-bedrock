#!/usr/bin/env bash
set -Eeuo pipefail

# Parameters
BLUEMAP_VERSION="${1:-5.16}"
USE_SUDO="${2:-true}"
BLUEMAP_DIR="${3:-/opt/bluemap}"
WORK_BASE_DIR="${4:-.}"
VENV_DIR="${VENV_DIR:-}"  # Optional: if set, use this venv; otherwise use global pip
CMAKE_DIR="${CMAKE_DIR:-/opt/cmake}"
CMAKE_VERSION="${CMAKE_VERSION:-4.1.0}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "[install-deps] [${GREEN}INFO${NC}] $*"
}

log_error() {
    echo -e "[install-deps] [${RED}ERROR${NC}] $*"
}

log_warning() {
    echo -e "[install-deps] [${YELLOW}WARNING${NC}] $*"
}

on_error() {
    local exit_code=$?
    local line_no="${BASH_LINENO[0]:-?}"
    local source_file="${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}"
    log_error "Command failed (exit ${exit_code}) at ${source_file}:${line_no}: ${BASH_COMMAND}"
    exit "$exit_code"
}

trap 'on_error' ERR

# Determine apt-get prefix
if [[ "$USE_SUDO" == "true" ]]; then
    APT_CMD="sudo apt-get"
else
    APT_CMD="apt-get"
fi

install_system_deps() {
    log_info "Installing system dependencies..."
    
    local packages=(
        curl
        wget
        ca-certificates
        git
        openjdk-21-jre-headless
        ninja-build
        python3-pip
        python3-dev
        build-essential
        libffi-dev
        zlib1g-dev
    )

    $APT_CMD update
    $APT_CMD install -y --no-install-recommends "${packages[@]}"
    
    if [[ "$USE_SUDO" == "false" ]]; then
        rm -rf /var/lib/apt/lists/*
    fi
    
    log_info "System dependencies installed"
}

add_to_path_once() {
    local dir="$1"
    case ":$PATH:" in
        *":$dir:"*) 
            log_info "Directory $dir already in PATH"
            ;;
        *) 
            PATH="$dir:$PATH"
            log_info "Added $dir to PATH"
            ;;
    esac
}

download_bluemap() {
    log_info "Downloading BlueMap CLI version ${BLUEMAP_VERSION}..."
    
    mkdir -p "$BLUEMAP_DIR"
    wget -O "$BLUEMAP_DIR/BlueMap-cli.jar" \
        "https://github.com/BlueMap-Minecraft/BlueMap/releases/download/v${BLUEMAP_VERSION}/BlueMap-${BLUEMAP_VERSION}-cli.jar"
    
    log_info "BlueMap CLI downloaded to $BLUEMAP_DIR/BlueMap-cli.jar"
}

create_directories() {
    log_info "Creating necessary directories at $WORK_BASE_DIR..."
    mkdir -p "$WORK_BASE_DIR" "$BLUEMAP_DIR/config"
    log_info "Directories created"
}

upgrade_pip() {
    log_info "Upgrading pip..."
    python3 -m pip install --upgrade pip
    log_info "Pip upgraded"
}

install_modern_cmake() {
    log_info "Installing CMake ${CMAKE_VERSION} from official GitHub releases..."

    local uname_arch
    uname_arch="$(uname -m)"

    local cmake_arch
    case "$uname_arch" in
        x86_64|amd64)
            cmake_arch="x86_64"
            ;;
        aarch64|arm64)
            cmake_arch="aarch64"
            ;;
        *)
            log_error "Unsupported architecture for prebuilt CMake binaries: ${uname_arch}"
            exit 1
            ;;
    esac

    local release_base="cmake-${CMAKE_VERSION}-linux-${cmake_arch}"
    local download_url="https://github.com/Kitware/CMake/releases/download/v${CMAKE_VERSION}/${release_base}.tar.gz"
    local tmp_root
    tmp_root="$(mktemp -d)"

    if [[ "$CMAKE_DIR" == "/" || "$CMAKE_DIR" == "." ]]; then
        log_error "Refusing to install CMake into unsafe CMAKE_DIR: ${CMAKE_DIR}"
        exit 1
    fi

    log_info "Downloading: ${download_url}"
    wget -O "${tmp_root}/${release_base}.tar.gz" "${download_url}"

    mkdir -p "$CMAKE_DIR"
    tar -xzf "${tmp_root}/${release_base}.tar.gz" -C "$tmp_root"

    # Replace destination with extracted CMake content
    rm -rf "${CMAKE_DIR:?}"/*
    cp -a "${tmp_root}/${release_base}/." "$CMAKE_DIR/"
    rm -rf "$tmp_root"

    local cmake_version="$($CMAKE_DIR/bin/cmake --version | head -n1)"
    if [[ "$cmake_version" != *"${CMAKE_VERSION}"* ]]; then
        log_error "CMake version mismatch after installation: expected ${CMAKE_VERSION}, got ${cmake_version}"
        exit 1
    fi

    log_info "CMake installed at: $CMAKE_DIR"
    log_info "Using CMake: $($CMAKE_DIR/bin/cmake --version | head -n1)"
}

install_binary_python_dep() {
    local package="$1"
    local timeout_seconds="${2:-0}"  # Default timeout of 0 seconds (no timeout)
    log_info "Installing binary Python package: $package"
    # Build dep from source to ensure C extensions are included (binary wheel doesn't include C extensions on all systems)
    # Timeout after ${timeout_seconds} seconds in case build takes abnormally long
    log_info "Installing $package (includes C extensions, timeout: ${timeout_seconds} seconds)..."
    if timeout "$timeout_seconds" python3 -m pip install --no-cache-dir --no-binary="$package" "$package"; then
        log_info "$package installed successfully"
    else
        local exit_code=$?
        if [[ $exit_code -eq 124 ]]; then
            log_error "$package installation timed out after ${timeout_seconds} seconds (exit code: 124)"
            exit 1
        else
            log_error "$package installation failed with exit code: $exit_code"
            return $exit_code
        fi
    fi
}

install_python_deps() {
    log_info "Installing Python dependencies for Bedrock conversion..."
    
    # First ensure we have compatible numpy version (amulet needs <2.0)
    log_info "Installing numpy<2 for compatibility..."
    python3 -m pip install "numpy<2"
    
    install_binary_python_dep "amulet-nbt" 300
    install_binary_python_dep "amulet-leveldb" 300
    install_binary_python_dep "amulet-rocksdb"  # no timeout for rocksdb since it can be very slow to build
    install_binary_python_dep "amulet-core" 300

    log_info "Python dependencies installed"
}

setup_venv() {
    local venv_dir="${1:-}"

    if [[ -z "$venv_dir" ]]; then
        log_error "No VENV_DIR provided"
        exit 1
    fi

    if [[ -d "$venv_dir" ]]; then
        log_info "Virtual environment already exists at $venv_dir"
        read -p "Recreate it? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Removing existing virtual environment..."
            rm -rf "$venv_dir"
        else
            return 0
        fi
    fi

    log_info "Creating Python virtual environment at $venv_dir..."
    python3 -m venv "$venv_dir"
    log_info "Virtual environment created at $venv_dir"
}

install_system_deps
download_bluemap
create_directories

if [[ -n "$VENV_DIR" ]]; then
    setup_venv "${VENV_DIR}"

    log_info "Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
fi

upgrade_pip
install_modern_cmake
add_to_path_once "$CMAKE_DIR/bin"
install_python_deps

log_info "Installation complete"