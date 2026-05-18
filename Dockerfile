FROM node:22-slim AS builder
WORKDIR /build
COPY package*.json ./
RUN npm ci --omit=optional
COPY static/js/ ./static/js/
COPY static/css/ ./static/css/
RUN node -e "
const b = require('esbuild');
const f = require('fs');
const files = ['app.js','terminal.js','filemanager.js','backups.js','import.js','download.js','plugins.js'];
const s = files.map(x => f.readFileSync('static/js/'+x,'utf8')).join('\n');
f.writeFileSync('static/js/windfall.min.js', b.transformSync(s,{minify:true,keepNames:true,target:'es2022'}).code);
"
RUN node -e "
const c = require('csso');
const f = require('fs');
const css = f.readFileSync('static/css/style.css','utf8');
f.writeFileSync('static/css/style.min.css', c.minify(css).css);
"

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
RUN mkdir -p servers backups && echo '{}' > package.json
EXPOSE 8080
CMD ["python", "app.py"]
