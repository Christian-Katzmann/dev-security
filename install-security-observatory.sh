#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
OBS_HOME="${SECURITY_OBSERVATORY_HOME:-${HOME}/.security-observatory}"

log() {
  printf '[security-observatory] %s\n' "$*"
}

have() {
  command -v "$1" >/dev/null 2>&1
}

ensure_dirs() {
  mkdir -p "${BIN_DIR}" "${OBS_HOME}/reports" "${OBS_HOME}/db" "${OBS_HOME}/cache" "${OBS_HOME}/repos" "${OBS_HOME}/logs"
}

install_brew_formula() {
  local formula="$1"
  local binary="${2:-$1}"
  if have "${binary}"; then
    log "${binary} already installed: $(command -v "${binary}")"
    return
  fi
  if ! have brew; then
    log "Homebrew is required for ${formula} on macOS. Install Homebrew, then rerun this script."
    return 1
  fi
  if brew list --formula "${formula}" >/dev/null 2>&1; then
    log "${formula} is installed but ${binary} is not on PATH; running brew link."
    brew link "${formula}" >/dev/null 2>&1 || true
  else
    log "Installing ${formula} with Homebrew."
    brew install "${formula}"
  fi
}

install_uv_tool() {
  local package="$1"
  local binary="$2"
  if have "${binary}"; then
    log "${binary} already installed: $(command -v "${binary}")"
    return
  fi
  if ! have uv; then
    log "uv is required to install ${package}. Install uv, then rerun this script."
    return 1
  fi
  log "Installing ${package} with uv tool."
  uv tool install "${package}"
}

write_cli_wrapper() {
  local wrapper="${BIN_DIR}/security-scan"
cat >"${wrapper}" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${ROOT_DIR}/src:\${PYTHONPATH:-}"
exec python3 -m security_observatory.cli "\$@"
EOF
  chmod +x "${wrapper}"
  log "Installed CLI wrapper: ${wrapper}"
}

build_dashboard() {
  if [ ! -d "${ROOT_DIR}/dashboard-ui" ]; then
    return
  fi
  if ! have npm; then
    log "npm not found; using the checked-in dashboard build."
    return
  fi
  log "Building dashboard assets."
  (cd "${ROOT_DIR}/dashboard-ui" && npm install && npm run build)
}

validate() {
  log "Validation:"
  for binary in security-scan npm semgrep gitleaks trufflehog trivy osv-scanner syft grype checkov medusa; do
    if have "${binary}"; then
      printf '  %-18s %s\n' "${binary}" "$(command -v "${binary}")"
    else
      printf '  %-18s %s\n' "${binary}" "missing"
    fi
  done
}

main() {
  ensure_dirs
  log "Using observatory home: ${OBS_HOME}"

  install_brew_formula semgrep semgrep
  install_brew_formula gitleaks gitleaks
  install_brew_formula trufflehog trufflehog
  install_brew_formula trivy trivy
  install_brew_formula osv-scanner osv-scanner
  install_brew_formula syft syft
  install_brew_formula grype grype
  install_uv_tool checkov checkov
  install_uv_tool medusa-security medusa
  build_dashboard
  write_cli_wrapper
  validate

  log "Done. If ${BIN_DIR} is not on PATH, add it to your shell profile."
}

main "$@"
