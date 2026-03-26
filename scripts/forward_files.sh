#!/bin/sh
# forward_files.sh
# Moves files from the source directory to /mnt/tmp/forward-{random8} and
# transfers them via SCP to a remote server. Designed to run every 5 minutes
# via cron. Files are moved first to prevent duplicate processing.
#
# Usage:
#   forward_files.sh [--dry-run]
#
#   --dry-run  Show what would be done without moving files or running SCP.

# ============================================================
# Options
# ============================================================

DRY_RUN=0
for ARG in "$@"; do
    case "${ARG}" in
        --dry-run) DRY_RUN=1 ;;
        *)
            echo "Unknown option: ${ARG}" >&2
            echo "Usage: $0 [--dry-run]" >&2
            exit 1
            ;;
    esac
done

# ============================================================
# Configuration
# ============================================================

# Source directory
SOURCE_DIR="/var/data/source"

# File pattern to transfer (glob)
FILE_PATTERN="*.csv"

# Base directory for staging / failure
STAGING_BASE="/mnt/tmp"

# SCP destination
SCP_USER="transfer"
SCP_HOST="192.168.1.100"
SCP_DEST_DIR="/data/incoming"
SCP_KEY="/home/transfer/.ssh/id_rsa"
SCP_PORT=22

# Log directory
LOG_DIR="/var/log/kmb"

# ============================================================
# Initialization
# ============================================================

# Generate random 8-character string (lowercase alphanumeric)
RAND=$(cat /dev/urandom | tr -dc 'a-z0-9' | fold -w 8 | head -n 1)
STAGING_DIR="${STAGING_BASE}/forward-${RAND}"

# Log file rotated daily
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/forward_$(date '+%Y%m%d').log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$$] $*" >> "${LOG_FILE}"
}

log "=== START staging_dir=${STAGING_DIR} dry_run=${DRY_RUN} ==="

# ============================================================
# Check for target files
# ============================================================

# shellcheck disable=SC2086
FILE_COUNT=$(find "${SOURCE_DIR}" -maxdepth 1 -name "${FILE_PATTERN}" -type f 2>/dev/null | wc -l)

if [ "${FILE_COUNT}" -eq 0 ]; then
    log "No files to transfer. Skipping."
    log "=== END ==="
    exit 0
fi

log "Files found: ${FILE_COUNT}"

# In dry-run mode, list target files and exit without touching anything
if [ "${DRY_RUN}" -eq 1 ]; then
    log "[DRY-RUN] Would create staging directory: ${STAGING_DIR}"
    find "${SOURCE_DIR}" -maxdepth 1 -name "${FILE_PATTERN}" -type f 2>/dev/null | while read -r FILE_PATH; do
        FILE_NAME=$(basename "${FILE_PATH}")
        log "[DRY-RUN] Would move: ${FILE_PATH} -> ${STAGING_DIR}/${FILE_NAME}"
    done
    log "[DRY-RUN] Would transfer to: ${SCP_USER}@${SCP_HOST}:${SCP_DEST_DIR}"
    log "=== END (dry-run) ==="
    exit 0
fi

# ============================================================
# Create staging directory and move files
# (Moving files first prevents overlap with the next cron run)
# ============================================================

if ! mkdir -p "${STAGING_DIR}"; then
    log "ERROR: Failed to create staging directory: ${STAGING_DIR}"
    exit 1
fi

MOVED=0
MOVE_FAILED=0

for FILE_PATH in "${SOURCE_DIR}"/${FILE_PATTERN}; do
    # Skip if glob did not expand to an actual file
    [ -f "${FILE_PATH}" ] || continue

    FILE_NAME=$(basename "${FILE_PATH}")
    if mv "${FILE_PATH}" "${STAGING_DIR}/${FILE_NAME}"; then
        log "Moved: ${FILE_PATH} -> ${STAGING_DIR}/${FILE_NAME}"
        MOVED=$((MOVED + 1))
    else
        log "ERROR: Failed to move: ${FILE_PATH}"
        MOVE_FAILED=$((MOVE_FAILED + 1))
    fi
done

log "Move complete. moved=${MOVED} failed=${MOVE_FAILED}"

if [ "${MOVED}" -eq 0 ]; then
    log "No files were moved. Skipping SCP."
    rmdir "${STAGING_DIR}" 2>/dev/null
    log "=== END ==="
    exit 0
fi

# ============================================================
# SCP transfer (retry once on failure)
# ============================================================

# Helper function to run SCP and return its exit code
run_scp() {
    scp -i "${SCP_KEY}" \
        -P "${SCP_PORT}" \
        -o StrictHostKeyChecking=no \
        -o BatchMode=yes \
        -o ConnectTimeout=30 \
        "${STAGING_DIR}"/* \
        "${SCP_USER}@${SCP_HOST}:${SCP_DEST_DIR}" 2>&1
}

log "SCP transfer started (attempt 1/2): ${SCP_USER}@${SCP_HOST}:${SCP_DEST_DIR}"
SCP_OUTPUT=$(run_scp)
SCP_EXIT=$?

if [ "${SCP_EXIT}" -ne 0 ]; then
    log "WARNING: SCP transfer failed (attempt 1/2, exit=${SCP_EXIT}) output=${SCP_OUTPUT}"
    log "Retrying SCP transfer (attempt 2/2)..."
    SCP_OUTPUT=$(run_scp)
    SCP_EXIT=$?
fi

if [ "${SCP_EXIT}" -eq 0 ]; then
    log "SCP transfer succeeded"

    # Remove staging directory after successful transfer
    if rm -rf "${STAGING_DIR}"; then
        log "Staging directory removed: ${STAGING_DIR}"
    else
        log "WARNING: Failed to remove staging directory: ${STAGING_DIR}"
    fi
else
    log "ERROR: SCP transfer failed (attempt 2/2, exit=${SCP_EXIT}) output=${SCP_OUTPUT}"

    # Move failed files to /mnt/tmp/failure-{same random string as staging}
    FAILURE_DIR="${STAGING_BASE}/failure-${RAND}"

    if mkdir -p "${FAILURE_DIR}"; then
        log "Moving failed files to: ${FAILURE_DIR}"
        for FAILED_FILE in "${STAGING_DIR}"/*; do
            [ -f "${FAILED_FILE}" ] || continue
            FAILED_NAME=$(basename "${FAILED_FILE}")
            if mv "${FAILED_FILE}" "${FAILURE_DIR}/${FAILED_NAME}"; then
                log "FAILED_FILE: ${FAILED_NAME}"
            else
                log "ERROR: Could not move failed file: ${FAILED_NAME}"
            fi
        done
        rmdir "${STAGING_DIR}" 2>/dev/null
        log "Failed files moved to: ${FAILURE_DIR}"
    else
        log "ERROR: Failed to create failure directory: ${FAILURE_DIR}"
        log "Files remain in staging directory: ${STAGING_DIR}"
    fi

    log "=== END (error) ==="
    exit 1
fi

log "=== END ==="
exit 0
