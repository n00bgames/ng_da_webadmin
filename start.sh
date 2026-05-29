#!/bin/bash

# =========================================================
# n00bGame Dune Awakening Web-Admin Startup Script
# =========================================================

cd "$(dirname "$0")"

SCREEN_SESSION="${SCREEN_SESSION:-dune-admin-web}"
PID_FILE="${PID_FILE:-webadmin.pid}"
MODE_FILE="${MODE_FILE:-webadmin.mode}"
LOG_FILE="${LOG_FILE:-logs/webadmin.log}"

if [ ! -d "venv" ]; then
    echo
    echo "ERROR: Python virtual environment not found."
    echo
    echo "Run:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    echo
    exit 1
fi

source venv/bin/activate

export ENABLE_HOST_COMMAND_RUNNER=1
export ENABLE_STACK_INSTALLER=1
export ENABLE_HOST_SHELL=1

# Optional custom RedBlink install directory
# export REDBLINK_INSTALL_DIR=/home/%CHANGEME%/dune-awakening-selfhost-docker

# Run in the foreground by default so first-time setup errors are visible.
# For unattended/headless use, run:
#   ./start.sh --headless
# or:
#   HEADLESS=1 ./start.sh
#
# Headless mode writes output to logs/webadmin.log and stores the process ID in
# webadmin.pid so server admins can confirm or stop the running web-admin later.
#
# If GNU screen is installed, this is usually the friendlier admin workflow:
#   ./start.sh --screen
#   screen -r dune-admin-web
#
# Detach from screen with Ctrl+A, then D.
if [ "$1" = "--screen" ]; then
    if ! command -v screen >/dev/null 2>&1; then
        echo "ERROR: screen is not installed."
        echo "Install it with your distro package manager, or use ./start.sh --headless."
        exit 1
    fi

    if screen -list | grep -q "[.]${SCREEN_SESSION}"; then
        echo "Screen session ${SCREEN_SESSION} already exists."
        echo "Reattach with: screen -r ${SCREEN_SESSION}"
        exit 0
    fi

    screen -dmS "${SCREEN_SESSION}" bash -lc "cd \"$(pwd)\" && source venv/bin/activate && python3 app.py"
    echo "screen" > "${MODE_FILE}"
    echo "Web-admin started in detached screen session: ${SCREEN_SESSION}"
    echo "Reattach with: screen -r ${SCREEN_SESSION}"
    exit 0
fi

if [ "$1" = "--headless" ] || [ "${HEADLESS:-0}" = "1" ]; then
    mkdir -p logs

    if [ -f "${PID_FILE}" ] && kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
        echo "Web-admin already appears to be running with PID $(cat "${PID_FILE}")."
        exit 0
    fi

    nohup python3 app.py >> "${LOG_FILE}" 2>&1 &
    echo $! > "${PID_FILE}"
    echo "headless" > "${MODE_FILE}"

    echo "Web-admin started headless with PID $(cat "${PID_FILE}")."
    echo "Log file: ${LOG_FILE}"
    exit 0
fi

python3 app.py
