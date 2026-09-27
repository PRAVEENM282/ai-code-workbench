ARG PYTHON_IMAGE
ARG NODE_IMAGE
FROM ${NODE_IMAGE} AS node_runtime
FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node_runtime /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/.flake8 ./backend/.flake8
COPY backend/src ./backend/src
COPY backend/package.json ./package.json
COPY backend/package-lock.json ./package-lock.json
RUN python -m pip install --no-cache-dir './backend[analysis]' \
    && npm ci --ignore-scripts
ENV PATH="/app/node_modules/.bin:${PATH}"

COPY settings.yaml ./settings.yaml
COPY config ./config
COPY feature-flags ./feature-flags
COPY prompts ./prompts
COPY prompt-templates ./prompt-templates
COPY backend/alembic.ini ./backend/alembic.ini
COPY backend/alembic ./backend/alembic

RUN groupadd --system workbench \
    && useradd --system --gid workbench --home-dir /app --no-create-home workbench \
    && install -d -o workbench -g workbench /tmp/workbench-analysis

USER workbench
WORKDIR /app/backend
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn workbench.main:app --host ${WORKBENCH_SERVICE__HOST} --port ${WORKBENCH_SERVICE__PORT}"]
