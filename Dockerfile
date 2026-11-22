FROM node:22-bookworm-slim AS ui
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends python3 make g++ && rm -rf /var/lib/apt/lists/*
COPY tui/package*.json ./
RUN npm ci
COPY tui/src ./src
COPY tui/tsconfig.json ./
RUN npm run build && npm prune --omit=dev

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 libstdc++6 && rm -rf /var/lib/apt/lists/*
COPY --from=ui /usr/local/bin/node /usr/local/bin/node
COPY --from=ui /build/node_modules ./tui/node_modules
COPY --from=ui /build/dist ./tui/dist
COPY tui/package.json ./tui/
COPY pyproject.toml uv.lock rules.yaml ./
COPY core ./core
RUN pip install --no-cache-dir uv==0.13.9 && uv sync --locked --no-dev --no-editable
ENV PATH="/app/.venv/bin:${PATH}"
COPY scripts/generate_logs.py ./scripts/
COPY scripts/demo.sh ./scripts/
CMD ["sh", "scripts/demo.sh"]
