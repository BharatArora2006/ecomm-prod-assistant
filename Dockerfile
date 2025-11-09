FROM python:3.11-slim

WORKDIR /app

# Install dependencies and git in one clean layer
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency files first for better caching
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application
COPY . .

# Environment variables
ENV PYTHONPATH=/app
ENV ENV=production
# (optional) preload any missing API keys safely in runtime via Docker run or env file

# Expose the FastAPI port
EXPOSE 8000

# Use supervisord to manage both processes cleanly
RUN pip install supervisor

# Add supervisord config
RUN echo '[supervisord]\nnodaemon=true\n\n[program:mcp_server]\ncommand=python prod_assistant/mcp_servers/product_search_server.py\nautostart=true\nautorestart=true\n\n[program:uvicorn]\ncommand=uvicorn prod_assistant.router.main:app --host 0.0.0.0 --port 8000 --workers 2\nautostart=true\nautorestart=true' > /etc/supervisord.conf

CMD ["supervisord", "-c", "/etc/supervisord.conf"]
