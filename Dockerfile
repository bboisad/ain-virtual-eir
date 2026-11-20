FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8501

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --disable-pip-version-check -r requirements.txt \
    && useradd --create-home --uid 10001 eir

COPY --chown=eir:eir . .
USER eir
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8501') + '/_stcore/health', timeout=4).read()"

CMD ["sh", "-c", "exec python -m streamlit run app.py --server.address 0.0.0.0 --server.port \"${PORT:-8501}\" --server.headless true --browser.gatherUsageStats false"]
