#!/bin/bash

# =========================================================
# Easy Dune Admin Restart Script
# =========================================================

cd "$(dirname "$0")"

SCREEN_SESSION="${SCREEN_SESSION:-dune-admin-web}"
PID_FILE="${PID_FILE:-webadmin.pid}"
MODE_FILE="${MODE_FILE:-webadmin.mode}"

REQUESTED_MODE="$1"
START_MODE=""

if [ "${REQUESTED_MODE}" = "--screen" ] || [ "${REQUESTED_MODE}" = "screen" ]; then
    START_MODE="--screen"
elif [ "${REQUESTED_MODE}" = "--headless" ] || [ "${REQUESTED_MODE}" = "headless" ]; then
    START_MODE="--headless"
elif command -v screen >/dev/null 2>&1 && screen -list | grep -q "[.]${SCREEN_SESSION}"; then
    START_MODE="--screen"
elif [ -f "${PID_FILE}" ] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
    START_MODE="--headless"
elif [ -f "${MODE_FILE}" ]; then
    LAST_MODE="$(cat "${MODE_FILE}")"
    if [ "${LAST_MODE}" = "screen" ]; then
        START_MODE="--screen"
    elif [ "${LAST_MODE}" = "headless" ]; then
        START_MODE="--headless"
    fi
fi

# If nothing is running and no last mode is known, prefer a daemon-style start.
if [ -z "${START_MODE}" ]; then
    START_MODE="--headless"
fi

echo "Restarting web-admin using mode: ${START_MODE}"
"$(dirname "$0")/shutdown.sh"
sleep 1
"$(dirname "$0")/start.sh" "${START_MODE}"
