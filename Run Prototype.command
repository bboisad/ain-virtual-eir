#!/bin/bash
# Double-click to start the AIN Virtual EIR prototype at http://localhost:8501 (close this window to stop it).
cd "$(dirname "$0")"
if command -v streamlit >/dev/null 2>&1; then
  streamlit run app.py --server.port 8501 --server.headless true
else
  python3 -m streamlit run app.py --server.port 8501 --server.headless true || {
    echo "Streamlit not found, installing..."; python3 -m pip install --user -r requirements.txt && python3 -m streamlit run app.py --server.port 8501 --server.headless true; }
fi
