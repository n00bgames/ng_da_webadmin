#!/bin/bash

# =========================================================
# n00bGame Dune Awakening Web-Admin Startup Script
# =========================================================

cd "$(dirname "$0")"

# Activate Python virtual environment
source venv/bin/activate

# =========================================================
# Infrastructure Feature Flags
# =========================================================

export ENABLE_HOST_COMMAND_RUNNER=1
export ENABLE_STACK_INSTALLER=1
export ENABLE_HOST_SHELL=1

# Optional custom RedBlink install directory
# Uncomment and modify if desired.
#
# export REDBLINK_INSTALL_DIR=/home/%CHANGEME%/dune-awakening-selfhost-docker

# =========================================================
# Launch Web Admin
# =========================================================

python app.py
