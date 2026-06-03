#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
.venv-flask/bin/python app.py
