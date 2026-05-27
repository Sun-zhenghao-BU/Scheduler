FROM node:24-alpine AS web

WORKDIR /web
ARG NPM_REGISTRY=https://registry.npmmirror.com

COPY src/web/package*.json ./
RUN node --version \
    && npm --version \
    && npm config set registry "$NPM_REGISTRY" \
    && npm config set workspaces false \
    && npm config set include-workspace-root false \
    && npm config set fetch-retries 5 \
    && npm config set fetch-retry-mintimeout 20000 \
    && npm config set fetch-retry-maxtimeout 120000 \
    && npm ci --workspaces=false --registry="$NPM_REGISTRY"

COPY src/web/ ./
RUN npm run build --workspaces=false

FROM python:3.13-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

COPY pyproject.toml README.md ./
COPY src/scheduler_automation ./src/scheduler_automation
RUN pip install --no-cache-dir -i "$PIP_INDEX_URL" -e ".[server]"

COPY --from=web /web/dist ./static

EXPOSE 80

CMD ["uvicorn", "scheduler_automation.api.app:app", "--host", "0.0.0.0", "--port", "80"]
