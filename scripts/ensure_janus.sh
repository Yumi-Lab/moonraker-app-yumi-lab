#!/bin/bash
#
# Ensure Janus WebRTC Gateway is available.
# - Bookworm (Debian 12): janus is in apt → install normally
# - Trixie (Debian 13)+: janus removed from apt → download pre-built .deb
#   from moonraker-yumi-lab GitHub Releases
#

set -e

JANUS_GITHUB_REPO="Yumi-Lab/moonraker-yumi-lab"

# Source colors and helpers if available
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
if [ -f "${SCRIPT_DIR}/funcs.sh" ]; then
    . "${SCRIPT_DIR}/funcs.sh"
else
    report_status() { echo ">>> $*"; }
    yellow=""
    default=""
fi

get_debian_version() {
    if [ -f /etc/debian_version ]; then
        cat /etc/debian_version | cut -d'.' -f1
    else
        echo "0"
    fi
}

get_arch() {
    dpkg --print-architecture 2>/dev/null || echo "unknown"
}

# Find the latest janus .deb URL from GitHub Releases matching arch
find_janus_deb_url() {
    local arch="$1"
    # Search releases with tag pattern janus-*-trixie-<arch>
    curl -sf "https://api.github.com/repos/${JANUS_GITHUB_REPO}/releases" | \
        python3 -c "
import sys, json
try:
    releases = json.load(sys.stdin)
    for r in releases:
        tag = r.get('tag_name', '')
        if 'janus' in tag and 'trixie' in tag and '${arch}' in tag:
            for asset in r.get('assets', []):
                if asset['name'].endswith('.deb'):
                    print(asset['browser_download_url'])
                    sys.exit(0)
    sys.exit(1)
except Exception:
    sys.exit(1)
" 2>/dev/null
}

ensure_janus() {
    # Already installed?
    if command -v janus &>/dev/null; then
        report_status "Janus is already installed: $(which janus)"
        setup_janus_config
        setup_janus_service
        return 0
    fi

    # Available via apt? (Bookworm and older)
    # apt-cache show returns 0 even for virtual/unavailable packages on Trixie
    # Use apt-cache policy and check for an actual installation candidate
    if apt-cache policy janus 2>/dev/null | grep -q "Candidate:" && \
       ! apt-cache policy janus 2>/dev/null | grep -q "Candidate: (none)"; then
        report_status "Installing Janus from apt..."
        sudo apt-get install -y janus
        setup_janus_config
        setup_janus_service
        return 0
    fi

    # Not in apt — need pre-built .deb (Trixie+)
    local debian_ver
    debian_ver=$(get_debian_version)
    local arch
    arch=$(get_arch)

    report_status "Janus not available via apt (Debian ${debian_ver}, ${arch})."
    report_status "Downloading pre-built .deb from GitHub Releases..."

    local deb_url
    deb_url=$(find_janus_deb_url "${arch}")

    if [ -z "${deb_url}" ]; then
        echo "${yellow}WARNING: No pre-built Janus .deb found for ${arch} on Trixie.${default}"
        echo "${yellow}WebRTC streaming will not be available.${default}"
        echo "${yellow}You can build it manually: https://github.com/${JANUS_GITHUB_REPO}/actions${default}"
        return 1
    fi

    local tmp_deb="/tmp/janus-gateway_${arch}.deb"
    report_status "Downloading: ${deb_url}"
    curl -L -o "${tmp_deb}" "${deb_url}"

    report_status "Installing Janus .deb..."
    sudo dpkg -i "${tmp_deb}" || true
    # Fix any missing dependencies
    sudo apt-get install -f -y
    rm -f "${tmp_deb}"

    if command -v janus &>/dev/null; then
        report_status "Janus installed successfully: $(janus --version 2>&1 | head -1)"
        setup_janus_config
        setup_janus_service
    else
        echo "${yellow}WARNING: Janus installation may have failed. Check errors above.${default}"
        return 1
    fi
}

setup_janus_config() {
    # Create /etc/janus config from .sample files if not already present
    local sample_dir="/usr/etc/janus"
    local config_dir="/etc/janus"

    if [ ! -d "${sample_dir}" ]; then
        report_status "No Janus sample configs found, skipping config setup."
        return 0
    fi

    if [ -d "${config_dir}" ] && [ "$(ls -A ${config_dir} 2>/dev/null)" ]; then
        report_status "Janus config already exists in ${config_dir}, skipping."
        return 0
    fi

    report_status "Setting up Janus configuration..."
    sudo mkdir -p "${config_dir}"
    for sample in "${sample_dir}"/*.jcfg.sample; do
        [ -f "${sample}" ] || continue
        local dest="${config_dir}/$(basename "${sample}" .sample)"
        if [ ! -f "${dest}" ]; then
            sudo cp "${sample}" "${dest}"
        fi
    done
    report_status "Janus config files deployed to ${config_dir}"
}

setup_janus_service() {
    # Create systemd service for Janus if not already present
    if [ -f /etc/systemd/system/janus.service ]; then
        report_status "Janus systemd service already exists."
        return 0
    fi

    report_status "Creating Janus systemd service..."
    sudo tee /etc/systemd/system/janus.service > /dev/null <<'SVCEOF'
[Unit]
Description=Janus WebRTC Gateway
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/janus -o -F /etc/janus
Restart=on-failure
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
SVCEOF

    sudo systemctl enable janus.service
    # In chroot (build), systemd is not running — skip daemon-reload and start
    if [ "$(stat -c %d:%i /)" != "$(stat -c %d:%i /proc/1/root/.)" ] 2>/dev/null; then
        report_status "Chroot detected — skipping janus service start (will start on boot)."
    else
        sudo systemctl daemon-reload
        sudo systemctl start janus.service
        report_status "Janus service created and started."
    fi
}

# Run if called directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    ensure_janus
fi
