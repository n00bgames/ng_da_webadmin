#!/usr/bin/env python3
"""
Easy Dune Admin
Panel version: 0.7.0-beta
RedBlink stack compatibility target: v1.3.2

Small launcher for the Flask/Socket.IO application. The 0.7.0-beta refactor moves
configuration, helpers, and route registrations out of this file so future
admin tools can grow without turning app.py back into a monolith.
"""

from eda_core import app, socketio  # shared Flask and Socket.IO objects
import eda_routes  # noqa: F401 - importing registers routes and socket handlers


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=8088,
        allow_unsafe_werkzeug=True,
    )
