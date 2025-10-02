FROM python:3.11-slim

WORKDIR /app

# install git
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml ./
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

ENV PYTHONPATH=/app

# run both MCP server and FastAPI properly
CMD ["bash", "-c", "python prod_assistant/mcp_servers/product_search_server.py & exec uvicorn prod_assistant.router.main:app --host 0.0.0.0 --port 8000 --workers 2"]
