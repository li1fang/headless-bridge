#!/bin/bash

# rget (Resilient Get)
# A zero-dependency Bash utility for resilient file downloading in constrained environments.
# Philosophy: Non-interactive, event-driven, stateful self-healing across Dynamic → History → Fallback.
#
# Allowed tools: curl OR wget, sha256sum OR shasum, grep/sed/awk/cat.
# Banned: jq, python, node, external binaries.
#
# Exit codes: 0 success, 1 failure.
# Logs: stderr only.

# ==========================
# Configuration & Constants
# ==========================
STATE_FILE_DEFAULT="${HOME}/.rget.state"
STATE_FILE="${RGET_STATE_FILE:-$STATE_FILE_DEFAULT}"

# ==========================
# Logging Helpers (stderr)
# ==========================
timestamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { # level msg
  printf '%s [%s] %s\n' "$(timestamp)" "$1" "$2" 1>&2
}
die() { log "ERROR" "$1"; exit 1; }

# ==========================
# Tool Detection
# ==========================
cmd_available() { command -v "$1" >/dev/null 2>&1; }

detect_downloader() {
  if cmd_available curl; then DOWNLOADER="curl"; return 0; fi
  if cmd_available wget; then DOWNLOADER="wget"; return 0; fi
  die "No downloader found. Install curl or wget."
}

detect_hasher() {
  if cmd_available sha256sum; then HASHER="sha256sum"; return 0; fi
  if cmd_available shasum; then HASHER="shasum"; return 0; fi
  HASHER=""
}

# ==========================
# Hash Utilities
# ==========================
compute_sha256() { # file → sha256 hex
  local f="$1"
  if [ -z "$HASHER" ]; then return 1; fi
  if [ "$HASHER" = "sha256sum" ]; then
    sha256sum "$f" | awk '{print $1}'
  else
    shasum -a 256 "$f" | awk '{print $1}'
  fi
}

verify_hash() { # file expected → 0 ok / 1 bad
  local f="$1" exp="$2"
  if [ -z "$exp" ]; then return 0; fi
  if [ -z "$HASHER" ]; then
    log "WARN" "Hash requested but no hasher available; skipping verification"
    return 0
  fi
  local got
  got="$(compute_sha256 "$f")" || return 1
  if [ "$got" = "$exp" ]; then return 0; else
    log "ERROR" "Hash mismatch: expected=$exp got=$got"
    return 1
  fi
}

# ==========================
# State Management
# ==========================
ensure_state_file() {
  mkdir -p "$(dirname "$STATE_FILE")" || die "Cannot create state directory: $(dirname "$STATE_FILE")"
  if [ ! -f "$STATE_FILE" ]; then
    : > "$STATE_FILE" || die "Cannot create state file: $STATE_FILE"
  fi
}

read_state() { # name → url or empty
  local name="$1"
  [ -f "$STATE_FILE" ] || { echo ""; return 0; }
  grep -E "^${name}=" "$STATE_FILE" | head -n1 | sed -E "s/^${name}=//"
}

write_state() { # name url
  local name="$1" url="$2"
  ensure_state_file
  # Robust update: rewrite entire file with awk
  tmp="${STATE_FILE}.tmp.$$"
  awk -v name="$name" -v url="$url" '
    BEGIN{found=0}
    $0 ~ ("^"name"="){print name"="url; found=1; next}
    {print}
    END{if(!found) print name"="url}
  ' "$STATE_FILE" > "$tmp" || die "Failed preparing state update"
  mv "$tmp" "$STATE_FILE" || die "Failed updating state"
}

# ==========================
# Download Implementation
# ==========================
download() { # url dest → 0/1
  local url="$1" dest="$2"
  mkdir -p "$(dirname "$dest")" || die "Cannot create directory: $(dirname "$dest")"
  if [ "$DOWNLOADER" = "curl" ]; then
    # -f fail on HTTP errors, -S show errors, -L follow redirects, retries, timeouts
    curl -fsSL "$url" -o "$dest" --retry 5 --retry-delay 1 --retry-connrefused --connect-timeout 5
  else
    # wget equivalent with non-interactive flags
    wget -q "$url" -O "$dest" --tries=5 --waitretry=1 --timeout=5 --no-verbose
  fi
}

# ==========================
# Idempotency
# ==========================
idempotent_skip_if_hash_matches() {
  local path="$1" expected="$2"
  if [ -n "$expected" ] && [ -f "$path" ]; then
    if [ -n "$HASHER" ]; then
      local ok
      ok="$(compute_sha256 "$path")"
      if [ "$ok" = "$expected" ]; then
        log "INFO" "Target already exists and hash matches; skipping"
        exit 0
      fi
    else
      log "WARN" "Target exists but no hasher; cannot verify idempotency"
    fi
  fi
}

# ==========================
# Argument Parsing
# ==========================
NAME=""
DYNAMIC_CMD=""
FALLBACK_URL=""
MANUAL_URL=""
EXPECTED_HASH=""
TARGET_PATH=""

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --name)
        NAME="$2"; shift 2;;
      --dynamic-cmd)
        DYNAMIC_CMD="$2"; shift 2;;
      --fallback-url)
        FALLBACK_URL="$2"; shift 2;;
      --state-file)
        STATE_FILE="$2"; shift 2;;
      --manual-url)
        MANUAL_URL="$2"; shift 2;;
      --hash)
        EXPECTED_HASH="$2"; shift 2;;
      --)
        shift; break;;
      -*)
        die "Unknown option: $1";;
      *)
        # First non-option is TARGET_PATH
        if [ -z "$TARGET_PATH" ]; then TARGET_PATH="$1"; shift; else die "Unexpected argument: $1"; fi;;
    esac
  done
  # Remaining non-option as TARGET_PATH if not set
  if [ -z "$TARGET_PATH" ] && [ $# -gt 0 ]; then TARGET_PATH="$1"; fi

  [ -n "$NAME" ] || die "--name is required"
  [ -n "$TARGET_PATH" ] || die "TARGET_PATH is required"
}

# ==========================
# Strategies
# ==========================
strategy_manual() {
  local url="$MANUAL_URL"
  [ -n "$url" ] || return 1
  log "INFO" "Manual override: attempting $url"
  if download "$url" "$TARGET_PATH"; then
    if verify_hash "$TARGET_PATH" "$EXPECTED_HASH"; then
      write_state "$NAME" "$url"
      log "INFO" "Manual download succeeded"
      return 0
    else
      rm -f "$TARGET_PATH"
      log "WARN" "Manual download failed hash verification"
      return 1
    fi
  else
    log "WARN" "Manual download failed"
    return 1
  fi
}

strategy_dynamic() {
  [ -n "$DYNAMIC_CMD" ] || return 1
  log "INFO" "Dynamic resolution: executing command"
  # Execute user-supplied pipeline to yield a URL (single line)
  local url
  url="$(eval "$DYNAMIC_CMD" 2>/dev/null | head -n1 | tr -d '\r')"
  if [ -z "$url" ]; then
    log "WARN" "Dynamic command returned empty URL"
    return 1
  fi
  log "INFO" "Dynamic resolved URL: $url"
  if download "$url" "$TARGET_PATH"; then
    if verify_hash "$TARGET_PATH" "$EXPECTED_HASH"; then
      write_state "$NAME" "$url"
      log "INFO" "Dynamic download succeeded"
      return 0
    else
      rm -f "$TARGET_PATH"
      log "WARN" "Dynamic download failed hash verification"
      return 1
    fi
  else
    log "WARN" "Dynamic download failed"
    return 1
  fi
}

strategy_history() {
  local url
  url="$(read_state "$NAME")"
  [ -n "$url" ] || { log "INFO" "No history for name=$NAME"; return 1; }
  log "INFO" "History replay: attempting $url"
  if download "$url" "$TARGET_PATH"; then
    if verify_hash "$TARGET_PATH" "$EXPECTED_HASH"; then
      # Keep state pointing to same working URL
      write_state "$NAME" "$url"
      log "INFO" "History download succeeded"
      return 0
    else
      rm -f "$TARGET_PATH"
      log "WARN" "History download failed hash verification"
      return 1
    fi
  else
    log "WARN" "History download failed"
    return 1
  fi
}

strategy_fallback() {
  local url="$FALLBACK_URL"
  [ -n "$url" ] || { log "INFO" "No fallback URL provided"; return 1; }
  log "INFO" "Fallback: attempting $url"
  if download "$url" "$TARGET_PATH"; then
    if verify_hash "$TARGET_PATH" "$EXPECTED_HASH"; then
      write_state "$NAME" "$url"
      log "INFO" "Fallback download succeeded"
      return 0
    else
      rm -f "$TARGET_PATH"
      log "WARN" "Fallback download failed hash verification"
      return 1
    fi
  else
    log "WARN" "Fallback download failed"
    return 1
  fi
}

# ==========================
# Main
# ==========================
main() {
  parse_args "$@"
  detect_downloader
  detect_hasher
  idempotent_skip_if_hash_matches "$TARGET_PATH" "$EXPECTED_HASH"

  if [ -n "$MANUAL_URL" ]; then
    strategy_manual && exit 0 || exit 1
  fi

  if strategy_dynamic; then exit 0; fi
  if strategy_history; then exit 0; fi
  if strategy_fallback; then exit 0; fi

  die "All strategies failed"
}

main "$@"