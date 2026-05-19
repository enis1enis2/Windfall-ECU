FROM node:22-slim AS builder
WORKDIR /build
COPY package*.json build.sh ./
RUN npm ci --omit=optional
COPY static/js/ ./static/js/
COPY static/css/ ./static/css/
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=builder /build/static/js/windfall.min.js static/js/windfall.min.js
COPY --from=builder /build/static/css/style.min.css static/css/style.min.css
RUN mkdir -p servers backups
EXPOSE 8080
CMD ["python", "app.py"]
