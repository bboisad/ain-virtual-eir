#!/bin/bash
# Double-click to start the prototype. Ctrl+C stops it.
set -e
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
  EIR_RUN_PYTHON=.venv/bin/python
elif [ -x ../.venv/bin/python ]; then
  EIR_RUN_PYTHON=../.venv/bin/python
else
  python3 -m venv .venv
  EIR_RUN_PYTHON=.venv/bin/python
fi
if ! "$EIR_RUN_PYTHON" -c 'import streamlit' >/dev/null 2>&1; then
  "$EIR_RUN_PYTHON" -m pip install -r requirements.txt
fi
exec "$EIR_RUN_PYTHON" -m streamlit run app.py --server.port 8501 --server.headless true
