#!/bin/bash

# =========================================================
# n00bGame Dune Awakening Web-Admin Shutdown Script
# =========================================================

cd "$(dirname "$0")"

SCREEN_SESSION="${SCREEN_SESSION:-dune-admin-web}"
PID_FILE="${PID_FILE:-webadmin.pid}"
MODE_FILE="${MODE_FILE:-webadmin.mode}"

STOPPED=0

if command -v screen >/dev/null 2>&1 && screen -list | grep -q "[.]${SCREEN_SESSION}"; then
    echo "Stopping screen session: ${SCREEN_SESSION}"
    screen -S "${SCREEN_SESSION}" -X quit
    STOPPED=1
fi

if [ -f "${PID_FILE}" ]; then
    PID="$(cat "${PID_FILE}")"

    if kill -0 "${PID}" 2>/dev/null; then
        echo "Stopping headless web-admin PID: ${PID}"
        kill "${PID}" 2>/dev/null || true

        # Give Flask a few seconds to exit cleanly before forcing the process.
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            if ! kill -0 "${PID}" 2>/dev/null; then
                break
            fi
            sleep 1
        done

        if kill -0 "${PID}" 2>/dev/null; then
            echo "Process did not stop cleanly; forcing PID ${PID}."
            kill -9 "${PID}" 2>/dev/null || true
        fi

        STOPPED=1
    fi

    rm -f "${PID_FILE}"
fi

if [ "${STOPPED}" -eq 0 ]; then
    echo "No tracked web-admin screen session or headless PID was running."
else
    echo "Web-admin stopped."
fi

# Keep webadmin.mode in place so restart.sh can reuse the last launch style.
exit 0
