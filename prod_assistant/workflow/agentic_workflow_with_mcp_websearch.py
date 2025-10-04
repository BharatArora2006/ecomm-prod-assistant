from typing import Annotated, Sequence, TypedDict, Literal
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

# Note: Assuming these imports are available in your environment
from prompt_library.prompts import PROMPT_REGISTRY, PromptType
from retriever.retrieval import Retriever
from utils.model_loader import ModelLoader
from evaluation.ragas_eval import evaluate_context_precision, evaluate_response_relevancy
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio

class AgenticRAG:
    """Agentic RAG pipeline using LangGraph + MCP (Retriever + WebSearch)."""

    class AgentState(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]

    # ---------- Initialization (Synchronous) ----------
    def __init__(self):
        self.retriever_obj = Retriever()
        self.model_loader = ModelLoader()
        self.llm = self.model_loader.load_llm()
        self.checkpointer = MemorySaver()
        self.mcp_tools = [] # Initialize placeholder for tools loaded later

        # Initialize MCP client synchronously, but do not load tools yet
        self.mcp_client = MultiServerMCPClient(
            {
                "hybrid_search": {
                    "transport": "streamable_http",
                    "url": "http://localhost:8000/mcp"
                }
            }
        )

        # Build and compile workflow
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile(checkpointer=self.checkpointer)

    # ---------- Async Lifecycle Methods (Called by FastAPI Lifespan) ----------

    async def async_init(self):
        """Asynchronously load MCP tools using the Uvicorn/FastAPI event loop."""
        print("AgenticRAG: Loading MCP tools asynchronously...")
        try:
            # We move the tool loading logic here, which must be awaited
            self.mcp_tools = await self.mcp_client.get_tools()
            print("AgenticRAG: MCP tools loaded successfully.")
        except Exception as e:
            print(f"Warning: Failed to load MCP tools — {e}")
            self.mcp_tools = []
    
    async def async_shutdown(self):
        """Gracefully shut down connections (e.g., the MCP client)."""
        print("AgenticRAG: Shutting down MCP client.")
        if self.mcp_client and hasattr(self.mcp_client, 'close'):
            try:
                # Assuming the MCP client has an async close method
                await self.mcp_client.close()
            except Exception as e:
                 print(f"Warning: Error during MCP client shutdown — {e}")

    # ---------- Nodes ----------
    def _ai_assistant(self, state: AgentState):
        print("--- CALL ASSISTANT ---")
        messages = state["messages"]
        last_message = messages[-1].content

        if any(word in last_message.lower() for word in ["price", "review", "product"]):
            return {"messages": [HumanMessage(content="TOOL: retriever")]}
        else:
            prompt = ChatPromptTemplate.from_template(
                "You are a helpful assistant. Answer the user directly.\n\nQuestion: {question}\nAnswer:"
            )
            chain = prompt | self.llm | StrOutputParser()
            response = chain.invoke({"question": last_message}) or "I'm not sure about that."
            return {"messages": [HumanMessage(content=response)]}

    async def _vector_retriever(self, state: AgentState):
        print("--- RETRIEVER (MCP) ---")
        query = state["messages"][-1].content

        # Look for the product info tool in the loaded tools
        tool = next((t for t in self.mcp_tools if t.name == "get_product_info"), None)
        if not tool:
            return {"messages": [HumanMessage(content="Retriever tool not found in MCP client. Initialization might have failed.")]}

        try:
            result = await tool.ainvoke({"query": query})
            context = result or "No relevant product data found."
        except Exception as e:
            context = f"Error invoking retriever: {e}"

        return {"messages": [HumanMessage(content=context)]}

    async def _web_search(self, state: AgentState):
        print("--- WEB SEARCH (MCP) ---")
        query = state["messages"][-1].content
        
        # Look for the web search tool in the loaded tools
        tool = next((t for t in self.mcp_tools if t.name == "web_search"), None)
        if not tool:
            return {"messages": [HumanMessage(content="Web search tool not found in MCP client. Initialization might have failed.")]}
            
        result = await tool.ainvoke({"query": query})
        context = result if result else "No data from web"
        return {"messages": [HumanMessage(content=context)]}


    def _grade_documents(self, state: AgentState) -> Literal["generator", "rewriter"]:
        print("--- GRADER ---")
        question = state["messages"][0].content
        docs = state["messages"][-1].content

        prompt = PromptTemplate(
            template="""You are a grader. Question: {question}\nDocs: {docs}\n
            Are docs relevant to the question? Answer yes or no.""",
            input_variables=["question", "docs"],
        )
        chain = prompt | self.llm | StrOutputParser()
        score = chain.invoke({"question": question, "docs": docs}) or ""
        return "generator" if "yes" in score.lower() else "rewriter"

    def _generate(self, state: AgentState):
        print("--- GENERATE ---")
        question = state["messages"][0].content
        docs = state["messages"][-1].content

        prompt = ChatPromptTemplate.from_template(
            PROMPT_REGISTRY[PromptType.PRODUCT_BOT].template
        )
        chain = prompt | self.llm | StrOutputParser()

        try:
            response = chain.invoke({"context": docs, "question": question}) or "No response generated."
        except Exception as e:
            response = f"Error generating response: {e}"

        return {"messages": [HumanMessage(content=response)]}

    def _rewrite(self, state: AgentState):
        print("--- REWRITE ---")
        question = state["messages"][0].content

        prompt = ChatPromptTemplate.from_template(
            "Rewrite this user query to make it more clear and specific for a search engine. "
            "Do NOT answer the query. Only rewrite it.\n\nQuery: {question}\nRewritten Query:"
        )
        chain = prompt | self.llm | StrOutputParser()

        try:
            new_q = chain.invoke({"question": question}).strip()
        except Exception as e:
            new_q = f"Error rewriting query: {e}"

        return {"messages": [HumanMessage(content=new_q)]}

    # ---------- Build Workflow ----------
    def _build_workflow(self):
        workflow = StateGraph(self.AgentState)
        workflow.add_node("Assistant", self._ai_assistant)
        workflow.add_node("Retriever", self._vector_retriever)
        workflow.add_node("Generator", self._generate)
        workflow.add_node("Rewriter", self._rewrite)
        workflow.add_node("WebSearch", self._web_search)

        # Workflow edges
        workflow.add_edge(START, "Assistant")
        workflow.add_conditional_edges(
            "Assistant",
            lambda state: "Retriever" if "TOOL" in state["messages"][-1].content else END,
            {"Retriever": "Retriever", END: END},
        )
        workflow.add_conditional_edges(
            "Retriever",
            self._grade_documents,
            {"generator": "Generator", "rewriter": "Rewriter"},
        )
        workflow.add_edge("Generator", END)
        workflow.add_edge("Rewriter", "WebSearch")
        workflow.add_edge("WebSearch", "Generator")

        return workflow

    # ---------- Public Run ----------
    async def run(self, query: str, thread_id: str = "default_thread") -> str:
        """Run the workflow for a given query and return the final answer."""
        result = await self.app.ainvoke(
            {"messages": [HumanMessage(content=query)]},
            config={"configurable": {"thread_id": thread_id}}
        )
        return result["messages"][-1].content

# ---------- Standalone Test (Fix: Now using asyncio.run correctly) ----------
if __name__ == "__main__":
    async def main_test():
        rag_agent = AgenticRAG()
        # Initialize the agent asynchronously before running
        await rag_agent.async_init() 
        answer = await rag_agent.run("What is the price of iPhone 16?")
        print("\nFinal Answer:\n", answer)
        await rag_agent.async_shutdown()

    # Run the asynchronous test function
    asyncio.run(main_test())
