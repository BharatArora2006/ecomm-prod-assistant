import uvicorn
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Note: Assumes AgenticRAG class is defined in this module path
from workflow.agentic_workflow_with_mcp_websearch import AgenticRAG

# Global variable to hold the initialized agent instance
rag_agent: AgenticRAG | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events for the application.
    Initializes the RAG agent asynchronously once at startup.
    """
    global rag_agent
    rag_agent = AgenticRAG()
    # Asynchronously initialize all components of the agent (like MCP client, DB)
    print("--- RAG Agent initializing asynchronously ---")
    await rag_agent.async_init()
    print("--- RAG Agent startup complete ---")
    yield
    # Cleanup on shutdown
    print("--- RAG Agent shutting down ---")
    await rag_agent.async_shutdown()

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- FastAPI Endpoints ----------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@app.post("/get")
async def chat(msg: str = Form(...)):
    """Call the Agentic RAG workflow and AWAIT the result."""
    global rag_agent
    
    if rag_agent is None:
        return HTMLResponse("Error: Agent is not initialized.", status_code=500)

    # FIX: Added the crucial 'await' keyword here
    answer = await rag_agent.run(msg)
    
    print(f"Agentic Response: {answer}")
    
    # Assuming the frontend expects a simple string response for display
    return HTMLResponse(content=answer)

# If you were running this file directly via 'python router.main.py'
if __name__ == "__main__":
    uvicorn.run("router.main:app", host="0.0.0.0", port=8003, reload=True)
