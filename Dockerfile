FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY environment/requirements-web.txt environment/requirements-web.txt
COPY environment/requirements-web.lock.txt environment/requirements-web.lock.txt
RUN python -m pip install --requirement environment/requirements-web.lock.txt

RUN useradd --create-home --uid 10001 webapp

COPY --chown=webapp:webapp .streamlit .streamlit
COPY --chown=webapp:webapp app app
COPY --chown=webapp:webapp config config
COPY --chown=webapp:webapp data/boundaries/zhaling_eling_watershed_hybas6_v1.geojson data/boundaries/zhaling_eling_watershed_hybas6_v1.geojson
COPY --chown=webapp:webapp data/processed/zhaling_eling_yearly_stats.csv data/processed/zhaling_eling_yearly_stats.csv
COPY --chown=webapp:webapp data/processed/zhaling_eling_subbasin_yearly_stats.csv data/processed/zhaling_eling_subbasin_yearly_stats.csv
COPY --chown=webapp:webapp scripts/deployment_preflight.py scripts/deployment_preflight.py
COPY --chown=webapp:webapp scripts/check_streamlit_health.py scripts/check_streamlit_health.py

RUN python scripts/deployment_preflight.py

USER webapp
EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "scripts/check_streamlit_health.py", "--attempts", "1", "--timeout", "3"]

ENTRYPOINT ["python", "-m", "streamlit", "run", "app/streamlit_app.py"]
CMD ["--server.address=0.0.0.0", "--server.port=8501", "--server.fileWatcherType=none"]
