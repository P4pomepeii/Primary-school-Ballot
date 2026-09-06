FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
ENV NEXT_TELEMETRY_DISABLED=1
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-bookworm AS backend-build
WORKDIR /build/backend
RUN python -m venv /opt/venv
COPY backend/requirements.txt ./
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt
COPY backend/app/ ./app/
COPY backend/tests/ ./tests/
RUN MODEL_PROVIDER=fake /opt/venv/bin/python -m pytest -q

FROM python:3.13-slim-bookworm AS runtime
RUN apt-get update \
    && apt-get install -y --no-install-recommends libstdc++6 tini \
    && rm -rf /var/lib/apt/lists/*
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MODEL_PROVIDER=fake \
    BACKEND_URL=http://127.0.0.1:8000 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
RUN groupadd --gid 10001 schoolfit && useradd --uid 10001 --gid schoolfit --create-home schoolfit
COPY --from=frontend-build /usr/local/bin/node /usr/local/bin/node
RUN node --version
COPY --from=backend-build /opt/venv /opt/venv
WORKDIR /app
COPY --from=backend-build --chown=schoolfit:schoolfit /build/backend/app/ ./backend/app/
COPY --from=frontend-build --chown=schoolfit:schoolfit /build/frontend/.next/standalone/ ./frontend/
COPY --from=frontend-build --chown=schoolfit:schoolfit /build/frontend/.next/static/ ./frontend/.next/static/
COPY --chown=schoolfit:schoolfit deploy/start.sh ./deploy/start.sh
USER schoolfit
EXPOSE 3000
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/bin/bash", "/app/deploy/start.sh"]
