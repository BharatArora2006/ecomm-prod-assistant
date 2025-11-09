FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Copy all source files first (so editable installs work)
COPY . .

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Set envs
ENV PYTHONPATH=/app
ENV ENV=production

EXPOSE 8000

RUN pip install supervisor

RUN echo '[supervisord]\nnodaemon=true\n\n[program:mcp_server]\ncommand=python prod_assistant/mcp_servers/product_search_server.py\nautostart=true\nautorestart=true\n\n[program:uvicorn]\ncommand=uvicorn prod_assistant.router.main:app --host 0.0.0.0 --port 8000 --workers 2\nautostart=true\nautorestart=true' > /etc/supervisord.conf

CMD ["supervisord", "-c", "/etc/supervisord.conf"]
