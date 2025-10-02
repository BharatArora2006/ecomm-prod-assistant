# 📦 E-commerce Product Assistant (Hybrid RAG)

This project implements an **Agentic Retrieval-Augmented Generation (RAG)** system for an e-commerce platform. It provides product information from a local vector database (AstraDB), with a seamless fallback to a general **web search (DuckDuckGo)** when local information is insufficient. The architecture utilizes **Multi-Component Processing (MCP) Servers** for robust, asynchronous, and scalable tool execution.

## 🌟 Features

* **Data Scraping:** Scrapes product details and top reviews from Flipkart using Selenium and BeautifulSoup.
* **Streamlit UI:** A dedicated Streamlit interface (`Scrapper_ui.py`) for easy data scraping and vector store ingestion.
* **Vector Database Ingestion:** Transforms scraped data into LangChain `Document` objects and ingests them into **AstraDB (Apache Cassandra)**.
* **Hybrid Search:** Implements a search mechanism that prioritizes local product data retrieval from AstraDB, falling back to a real-time web search for out-of-scope or unindexed queries.
* **MCP Architecture:** Uses LangChain's Multi-Component Processing (MCP) to manage the local retriever and web search tools as separate, callable services.
* **FastAPI Router:** A simple web interface (`Router.main.py`) powered by FastAPI and Jinja2 templates to interact with the RAG agent.

## 🛠️ Prerequisites

1.  **Python 3.9+**
2.  **Required Libraries:**
    ```bash
    pip install pandas python-dotenv langchain-core langchain-astradb undetected-chromedriver selenium beautifulsoup4 fastapi uvicorn jinja2 mcp langchain-community groq google-genai streamlit
    # Note: Specific project dependencies like 'prod_assistant.utils' and 'workflow.agentic_workflow_with_mcp_websearch' are assumed to be present.
    ```
3.  **Environment Variables:** You must set up the following variables in a `.env` file in the project root:
    * `GROQ_API_KEY` (For the RAG agent's LLM)
    * `GOOGLE_API_KEY` (If used by other parts of the system)
    * `ASTRA_DB_API_ENDPOINT`
    * `ASTRA_DB_APPLICATION_TOKEN`
    * `ASTRA_DB_KEYSPACE`

## 🚀 Getting Started

### 1. Data Collection and Ingestion

The first step is to scrape product data and load it into your vector database.

#### Using the Streamlit UI

Run the Streamlit application to scrape data and ingest it:

```bash
streamlit run Scrapper_ui.py
