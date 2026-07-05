FROM node:20-bookworm-slim AS web

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY relayguard ./relayguard
COPY apps ./apps
COPY workers ./workers
COPY infra/aws/lambda_worker/certs /app/certs

RUN python3 -m pip install --no-cache-dir --break-system-packages .

COPY apps/web/package.json apps/web/package-lock.json ./apps/web/
WORKDIR /app/apps/web
RUN npm ci

COPY apps/web ./ 
RUN npm run build

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0

WORKDIR /app/apps/web
CMD ["sh", "-c", "exec npx next start -p ${PORT:-3000}"]
