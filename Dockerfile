FROM python:3.11-slim

# 1. 升级 Node.js 到 20.x (修复警告)
RUN apt-get update && apt-get install -y curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# 2. 安装官方 Codex CLI
RUN npm install -g @openai/codex

# 3. 配置 CLI
RUN mkdir -p /root/.codex && \
    printf 'preferred_auth_method = "apikey"\n' > /root/.codex/config.toml

# 4. Python 依赖
RUN pip install --no-cache-dir fastapi uvicorn pydantic requests

# 5. 注入代码 (修正这里的文件名匹配)
COPY core /app/core
COPY adapters /app/adapters
COPY main.py /app/main.py

WORKDIR /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
