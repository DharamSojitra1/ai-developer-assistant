<p align="center">
  <h1 align="center">🤖 AI Developer Assistant</h1>
  <p align="center">
    A production-grade, AI-powered developer assistant built with <strong>FastAPI</strong>, <strong>LangChain</strong>, <strong>LangGraph</strong>, <strong>RAG</strong>, and <strong>Agentic AI</strong> — featuring multi-agent orchestration, hybrid search, streaming responses, and a modern React frontend.
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangGraph-1.2-purple?logo=langchain" alt="LangGraph">
  <img src="https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white" alt="React">
  <img src="https://img.shields.io/badge/MongoDB-8-47A248?logo=mongodb&logoColor=white" alt="MongoDB">
  <img src="https://img.shields.io/badge/ChromaDB-1.5-orange" alt="ChromaDB">
  <img src="https://img.shields.io/badge/TypeScript-6-3178C6?logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/TailwindCSS-4-06B6D4?logo=tailwindcss&logoColor=white" alt="TailwindCSS">
</p>

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Technology Stack](#-technology-stack)
- [RAG Pipeline](#-rag-pipeline-retrieval-augmented-generation)
- [Agentic AI System](#-agentic-ai-system)
- [Multi-Agent Supervisor](#-multi-agent-supervisor)
- [Agent Tools](#-agent-tools)
- [Security & Safety](#-security--safety)
- [API Endpoints](#-api-endpoints)
- [Frontend](#-frontend)
- [Database Schema](#-database-schema)
- [Evaluation Framework](#-evaluation-framework)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Environment Variables](#-environment-variables)
- [Deployment](#-deployment)
- [Testing](#-testing)

---

## 🌟 Overview

**AI Developer Assistant** is a full-stack AI application that combines Retrieval-Augmented Generation (RAG), multi-agent orchestration, and real-time streaming to provide an intelligent developer assistant. Users can chat with the AI, upload knowledge base documents, search the web, perform calculations, and get contextual answers grounded in their own documents — all through a polished, responsive UI.

---

## ✨ Key Features

| Category | Features |
|---|---|
| **🧠 Agentic AI** | Multi-agent orchestration with LangGraph, intelligent message routing, supervisor pattern for complex tasks |
| **📚 RAG Pipeline** | Hybrid search (vector + BM25), cross-encoder reranking, answerability verification, deduplication |
| **🔍 Web Search** | Live web search via Tavily API, package info from PyPI/npm registries, cached results |
| **💬 Chat** | Real-time token streaming (SSE), conversation history, multi-turn context |
| **🔐 Authentication** | JWT access + refresh tokens, Argon2 password hashing, role-based access (user/admin) |
| **📊 Observability** | Structured JSON logging, per-request LLM token tracking, daily usage dashboards |
| **🛡️ Security** | Prompt injection detection, hardened system prompts, input sanitization, rate limiting |
| **🐳 Deployment** | Docker + Docker Compose, Render.yaml, Vercel-ready frontend |
| **🧪 Testing** | 80+ test files, evaluation framework with LLM judges, chunking quality metrics |

---

## 🏗 Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (React + Vite)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌───────────┐ │
│  │   Chat   │ │Knowledge │ │  History  │ │  Auth   │ │   Usage   │ │
│  │  Panel   │ │  Base    │ │  Sidebar  │ │  Pages  │ │ Dashboard │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬────┘ └─────┬─────┘ │
│       │             │            │             │            │       │
│       └─────────────┴────────────┴─────────────┴────────────┘       │
│                              │  HTTP / SSE                          │
└──────────────────────────────┼──────────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────────┐
│                     FastAPI Backend                                  │
│                              │                                       │
│  ┌───────────────────────────┴────────────────────────────────────┐  │
│  │                     API Layer (Routes)                         │  │
│  │  /api/chat  │  /api/auth  │  /api/rag  │  /api/agent  │ usage │  │
│  └──────┬──────┴──────┬──────┴──────┬─────┴──────┬───────┴───────┘  │
│         │             │             │            │                    │
│  ┌──────┴─────────────┴─────────────┴────────────┴───────────────┐  │
│  │                   Middleware & Guards                          │  │
│  │  RequestID │ BodySize │ RateLimit │ CORS │ InjectionDetection │  │
│  └──────┬────────────────────────────────────────────────────────┘  │
│         │                                                            │
│  ┌──────┴────────────────────────────────────────────────────────┐  │
│  │                 Agentic AI Layer (LangGraph)                   │  │
│  │                                                                │  │
│  │  ┌──────────┐    ┌────────────────────────────────────────┐   │  │
│  │  │ Router / │───►│         Orchestrator Graph              │   │  │
│  │  │Classifier│    │                                        │   │  │
│  │  └──────────┘    │  ┌──────────┐  ┌───────────┐          │   │  │
│  │                  │  │RAG Agent │  │ Web Agent  │          │   │  │
│  │                  │  ├──────────┤  ├───────────┤          │   │  │
│  │                  │  │Calc Agent│  │Plain LLM  │          │   │  │
│  │                  │  ├──────────┤  ├───────────┤          │   │  │
│  │                  │  │Tool Agent│  │Supervisor │          │   │  │
│  │                  │  └──────────┘  └───────────┘          │   │  │
│  │                  └────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│         │                                                            │
│  ┌──────┴────────────────────────────────────────────────────────┐  │
│  │                     Service Layer                              │  │
│  │  LLM Service │ RAG Service │ Embedding │ Reranker │ WebSearch │  │
│  │  Chat Service │ Answerability │ Keyword Index │ Ingestion     │  │
│  └──────┬────────────────────────────────────────────────────────┘  │
│         │                                                            │
└─────────┼────────────────────────────────────────────────────────────┘
          │
┌─────────┼────────────────────────────────────────────────────────────┐
│         │              External Services & Data Stores               │
│  ┌──────┴──────┐  ┌──────────┐  ┌────────┐  ┌────────┐  ┌────────┐ │
│  │   MongoDB   │  │ ChromaDB │  │  Groq  │  │ Gemini │  │ Tavily │ │
│  │  (Async)    │  │ (Vector) │  │  (LLM) │  │(Embed) │  │ (Web)  │ │
│  │             │  │          │  │        │  │        │  │        │  │
│  │• Users      │  │• Vectors │  │• Chat  │  │• Doc   │  │• Live  │  │
│  │• Chat Hist  │  │• Metadata│  │• Route │  │  Embed │  │  Search│  │
│  │• Tokens     │  │• BM25 Idx│  │• Agent │  │• Query │  │        │  │
│  │• Refresh    │  │          │  │        │  │  Embed │  │        │  │
│  │• Checkpts   │  │          │  │        │  │        │  │        │  │
│  └─────────────┘  └──────────┘  └────────┘  └────────┘  └────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Technology Stack

### Backend

| Technology | Version | Purpose |
|---|---|---|
| **Python** | 3.12 | Runtime |
| **FastAPI** | 0.141 | Async REST API framework |
| **Uvicorn** | 0.53 | ASGI server |
| **LangChain** | 1.4 | LLM orchestration, prompts, chains |
| **LangGraph** | 1.2 | Multi-agent state graphs with checkpointing |
| **LangChain-Groq** | 1.1 | Groq LLM integration |
| **LangChain-Google-GenAI** | 4.4 | Gemini embeddings |
| **ChromaDB** | 1.5 | Vector database for document embeddings |
| **MongoDB** | 8.x | Persistent storage (async via PyMongo) |
| **Sentence-Transformers** | 3.x | Cross-encoder reranker model |
| **PyTorch** | (CPU) | ML inference runtime for reranker |
| **Pydantic** | 2.13 | Settings validation, schema enforcement |
| **SlowAPI** | 0.1 | Rate limiting per user/IP |
| **PyJWT** | 2.15 | JWT token authentication |
| **Argon2-cffi** | 25.1 | Secure password hashing |
| **httpx** | 0.28 | Async HTTP client (Tavily, package registries) |
| **Tenacity** | 9.1 | Retry logic with exponential backoff |

### Frontend

| Technology | Version | Purpose |
|---|---|---|
| **React** | 18.3 | UI component library |
| **TypeScript** | 6.0 | Type-safe JavaScript |
| **Vite** | 8.3 | Build tool and dev server |
| **TailwindCSS** | 4.3 | Utility-first CSS framework |
| **React Router** | 7.18 | Client-side routing |
| **Lucide React** | 1.55 | Icon library |
| **React Markdown** | 10.1 | Markdown rendering for AI responses |
| **rehype-highlight** | 7.0 | Syntax highlighting in code blocks |
| **remark-gfm** | 4.0 | GitHub Flavored Markdown support |
| **Vitest** | 5.0 | Unit testing framework |

### Infrastructure & DevOps

| Technology | Purpose |
|---|---|
| **Docker** | Containerized backend (Python 3.12-slim) |
| **Docker Compose** | Local multi-service orchestration (API + MongoDB) |
| **Render** | Cloud deployment (render.yaml) |
| **Vercel** | Frontend static site deployment (vercel.json) |
| **GitHub Actions** | CI/CD (auto-deploy on push) |

---

## 📚 RAG Pipeline (Retrieval-Augmented Generation)

The RAG system is the core knowledge engine, providing grounded, factual answers from user-uploaded documents. It implements a **5-stage retrieval pipeline** with multiple quality gates.

### RAG Architecture Diagram

```
 User Query
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    1. DOCUMENT INGESTION                        │
│                                                                 │
│  Upload (text/PDF/Markdown/code) → Clean → Chunk → Embed       │
│                                                                 │
│  ┌───────────┐    ┌───────────┐    ┌────────────┐    ┌───────┐ │
│  │ Document   │───►│ Cleaning  │───►│  Recursive │───►│Gemini │ │
│  │ (text,pdf, │    │ & Normali-│    │  Character │    │Embed- │ │
│  │  md, code) │    │  zation   │    │  Splitter  │    │dings  │ │
│  └───────────┘    └───────────┘    │ (800 chars, │    │  API  │ │
│                                    │  100 overlap)│    └───┬───┘ │
│                                    └──────────────┘        │     │
│                                                            ▼     │
│                    ┌──────────────────────────────────────────┐  │
│                    │         ChromaDB Vector Store            │  │
│                    │  (per-model collections, metadata,       │  │
│                    │   content hashing, deduplication)        │  │
│                    └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

 User Query
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     2. HYBRID RETRIEVAL                         │
│                                                                 │
│  ┌─────────────────────┐    ┌──────────────────────┐           │
│  │  Vector Search       │    │  BM25 Keyword Search  │           │
│  │  (Gemini embeddings, │    │  (In-memory index,    │           │
│  │   cosine distance,   │    │   tokenized, IDF      │           │
│  │   top-k = 10)        │    │   scoring, top-k = 10)│           │
│  └─────────┬───────────┘    └──────────┬───────────┘           │
│            │                           │                        │
│            └───────────┬───────────────┘                        │
│                        ▼                                        │
│            ┌───────────────────────┐                            │
│            │  Reciprocal Rank      │                            │
│            │  Fusion (RRF, k=60)   │                            │
│            │  + Deduplication       │                            │
│            └───────────┬───────────┘                            │
│                        │                                        │
│            Distance threshold filter (≤ 0.35)                   │
└────────────────────────┼────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      3. RERANKING                               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   Cross-Encoder Reranker                                │    │
│  │   Model: cross-encoder/ms-marco-MiniLM-L6-v2           │    │
│  │   Device: auto (CUDA / CPU)                             │    │
│  │   Score threshold filtering                             │    │
│  │   Output: top-3 most relevant chunks                    │    │
│  └─────────────────────────────────────────────────────────┘    │
└────────────────────────┼────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 4. ANSWERABILITY CHECK                           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   LLM-as-Judge (Structured Output)                      │    │
│  │   - Evaluates if retrieved context can answer the query │    │
│  │   - Returns: { is_answerable: bool, reason: string }    │    │
│  │   - Rejects irrelevant context (prevents hallucination) │    │
│  └─────────────────────────────────────────────────────────┘    │
└────────────────────────┼────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   5. LLM GENERATION                             │
│                                                                 │
│  Context + Query → Groq LLM → Grounded Answer                  │
│  (with conversation history, streaming, source citations)       │
└─────────────────────────────────────────────────────────────────┘
```

### RAG Configuration

| Parameter | Default | Description |
|---|---|---|
| `RAG_DISTANCE_THRESHOLD` | 0.35 | Max cosine distance for vector results |
| `RAG_RETRIEVAL_TOP_K` | 10 | Candidates from each retrieval method |
| `RAG_FINAL_TOP_K` | 3 | Final chunks sent to the LLM |
| `RAG_CHUNK_SIZE` | 800 | Characters per chunk |
| `RAG_CHUNK_OVERLAP` | 100 | Overlap between adjacent chunks |
| `RAG_HYBRID_SEARCH` | true | Enable BM25 + vector fusion |
| `RAG_RRF_K` | 60 | Reciprocal Rank Fusion constant |
| `EMBEDDING_MODEL_NAME` | gemini-embedding-001 | Embedding model (each gets its own collection) |
| `RERANKER_MODEL_NAME` | cross-encoder/ms-marco-MiniLM-L6-v2 | Cross-encoder reranker |

### Document Ingestion

- **Supported formats**: Plain text, PDF (via `pypdf`), Markdown, Source code
- **Max upload**: 5 MB (configurable)
- **Visibility**: `shared` (visible to all) or `private` (owner-only)
- **Deduplication**: Content hashing prevents duplicate documents
- **Chunking**: Recursive character splitting with section-aware boundaries
- **Embedding caching**: Identical chunk text reuses cached embeddings, minimizing API calls
- **Model migration**: `python -m app.scripts.reembed` re-embeds all chunks when switching models

---

## 🤖 Agentic AI System

The agent system is built with **LangGraph** and implements a sophisticated multi-agent architecture with intelligent routing, parallel tool execution, and human-in-the-loop approval flows.

### Agent Orchestrator Flow

```
                    User Message
                         │
                         ▼
                  ┌──────────────┐
                  │   Classify    │  ◄── Router LLM (smaller model)
                  │   Message     │      Structured output → RouteDecision
                  └──────┬───────┘
                         │
            ┌────────────┼────────────────────────────────┐
            │            │            │         │         │
            ▼            ▼            ▼         ▼         ▼
      ┌──────────┐ ┌──────────┐ ┌────────┐ ┌───────┐ ┌────────┐
      │RAG Agent │ │Web Agent │ │Calc    │ │Plain  │ │Tool    │
      │          │ │          │ │Agent   │ │ LLM   │ │Agent   │
      │search_   │ │web_search│ │calcul- │ │(no    │ │(all    │
      │knowledge │ │package_  │ │ator    │ │tools) │ │tools)  │
      │_base     │ │info      │ │analyze │ │       │ │        │
      └──────────┘ └──────────┘ │_text   │ └───────┘ └────────┘
                                └────────┘
            │            │            │         │         │
            ▼            ▼            ▼         ▼         ▼
      ┌──────────────────────────────────────────────────────┐
      │              Supervisor (Multi-Agent)                  │
      │                                                        │
      │  For complex tasks needing multiple capabilities:      │
      │                                                        │
      │   ┌──────────┐  ┌──────────┐  ┌──────────┐           │
      │   │ Research  │  │ Analysis │  │  Coding  │           │
      │   │ Worker    │  │ Worker   │  │  Worker  │           │
      │   └──────────┘  └──────────┘  └──────────┘           │
      │         │              │             │                 │
      │         └──────────────┴─────────────┘                 │
      │                        │                               │
      │                   Findings                             │
      │                        │                               │
      │                   ┌────┴────┐                          │
      │                   │Finalize │ → Final Answer            │
      │                   └─────────┘                          │
      └────────────────────────────────────────────────────────┘
```

### Route Classification

The **Router** uses a smaller, dedicated LLM model (`ROUTER_MODEL_NAME`) to classify each message into one of six routes:

| Route | Agent | Description |
|---|---|---|
| `knowledge_base` | RAG Agent | Questions about uploaded documents |
| `web` | Web Agent | Current events, package versions, live information |
| `calculation` | Calc Agent | Arithmetic, numeric computations, text analysis |
| `chat` | Plain LLM | Greetings, small talk, general questions (no tools) |
| `multi_agent` | Supervisor | Complex tasks combining research + analysis + coding |
| `general` | Tool Agent | Everything else (has access to all tools) |

### Key Agent Features

- **Checkpointing**: Agent state is persisted in MongoDB via `langgraph-checkpoint-mongodb`, enabling run resume after restarts
- **Human-in-the-Loop**: Sensitive tools (e.g., document deletion) pause the agent and require user approval before executing
- **Parallel Tool Calls**: Multiple independent tool calls execute concurrently within a single agent step
- **Streaming**: Final answer tokens are streamed to the client via Server-Sent Events (SSE), while internal reasoning (routing, supervisor decisions) is filtered out
- **Context Compaction**: Older tool results beyond `AGENT_TOOL_CONTEXT_CHARS` (4000) are sent as references only, saving token budget
- **History Truncation**: Earlier conversation responses are shortened to `400` chars to prevent long past answers from dominating context
- **Iteration Limits**: Agents stop after `AGENT_MAX_ITERATIONS` (default: 5) LLM steps with a `max_iterations` stop reason
- **Cancellation**: Clients can disconnect mid-stream, and the agent logs a clean cancellation without errors

---

## 👔 Multi-Agent Supervisor

For complex tasks that require combining research, calculations, and code generation, the **Supervisor** pattern delegates sub-tasks to specialized workers:

```
┌─────────────────────────────────────────────────┐
│                  Supervisor Loop                 │
│                                                  │
│  1. Decide next worker + task (or finish)        │
│  2. Run worker with task + accumulated findings  │
│  3. Record finding → back to step 1              │
│  4. After max_rounds or finish → Finalize        │
│                                                  │
│  Workers:                                        │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐   │
│  │  Research   │ │  Analysis  │ │   Coding   │   │
│  │ • KB search │ │ •Calculator│ │ •Write code│   │
│  │ • Web search│ │ •Text stats│ │ •Use finds │   │
│  │ • Pkg info  │ │            │ │            │   │
│  └────────────┘ └────────────┘ └────────────┘   │
│                                                  │
│  Max rounds: SUPERVISOR_MAX_ROUNDS (default: 4)  │
└─────────────────────────────────────────────────┘
```

---

## 🔨 Agent Tools

| Tool | Description | Side Effects |
|---|---|---|
| `search_knowledge_base` | Query the RAG pipeline for relevant document chunks | Read-only (embedding + LLM costs) |
| `web_search` | Search the live web via Tavily API (with caching) | Read-only (paid API, cached) |
| `package_info` | Get latest version/metadata from PyPI or npm | Read-only (public registries) |
| `calculator` | Evaluate mathematical expressions safely | None (deterministic) |
| `analyze_text` | Count words, lines, characters, sentences | None (deterministic) |
| `delete_my_document` | Delete a user's own KB document | **Destructive** — requires approval |

---

## 🛡 Security & Safety

### Multi-Layer Defense

```
                     User Input
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
     ┌────────────┐ ┌─────────┐ ┌─────────────┐
     │  Injection  │ │  Rate   │ │  Body Size  │
     │  Detection  │ │ Limiter │ │   Limiter   │
     │ (heuristic) │ │(per user│ │ (6 MB max)  │
     │             │ │  or IP) │ │             │
     └──────┬─────┘ └────┬────┘ └──────┬──────┘
            │             │             │
            ▼             ▼             ▼
     ┌─────────────────────────────────────────┐
     │         Hardened System Prompts          │
     │  • Security rules override all others   │
     │  • Tool results treated as data only    │
     │  • No role reassignment via messages    │
     │  • No exfiltration of system prompts    │
     └─────────────────────────────────────────┘
```

| Layer | Implementation |
|---|---|
| **Prompt Injection Detection** | Heuristic regex patterns for override attempts, role reassignment, exfiltration, fake role markers (flag-only, never blocks) |
| **Hardened System Prompts** | Every agent prompt includes `SECURITY_RULES` — text in tool results and documents is treated as data, not instructions |
| **Rate Limiting** | Per-user (authenticated) or per-IP, configurable per endpoint (`5/minute` chat, `10/minute` agent, etc.) |
| **Body Size Limit** | ASGI middleware rejects requests > 6 MB before any parsing |
| **JWT Authentication** | Access tokens (15 min) + refresh tokens (7 days), Argon2 password hashing |
| **RBAC** | `user` and `admin` roles; admins can manage shared documents |
| **Production Secrets** | App refuses to start in production with placeholder secrets or secrets < 32 characters |
| **Input Validation** | Pydantic models enforce field constraints with min/max lengths and ranges |
| **Chat History TTL** | MongoDB TTL index auto-deletes history after 90 days (configurable) |
| **Log Redaction** | Tool arguments logged as lengths only, not content |
| **URL Safety** | Only `https://` and `http://` schemes are allowed in web search results |

---

## 📡 API Endpoints

### Authentication (`/api/auth`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/register` | Create a new user account |
| `POST` | `/login` | Authenticate and get JWT tokens |
| `POST` | `/refresh` | Refresh access token using refresh token |
| `POST` | `/logout` | Revoke refresh token |
| `GET` | `/me` | Get current user profile |

### Chat (`/api/chat`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/` | Send a message, get AI response |
| `POST` | `/stream` | Stream AI response tokens via SSE |
| `GET` | `/conversations` | List user's conversations |
| `GET` | `/conversations/{id}` | Get full conversation history |
| `DELETE` | `/conversations/{id}` | Delete a conversation |

### Agent (`/api/agent`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/agent/chat` | Send message through agentic pipeline |
| `POST` | `/agent/stream` | Stream agentic response via SSE |
| `POST` | `/agent/runs/{id}/approval` | Approve or reject a paused agent action |

### RAG / Knowledge Base (`/api/rag`)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/documents` | Upload and index a document |
| `POST` | `/documents/upload` | Upload a PDF file |
| `POST` | `/search` | Search the knowledge base |
| `DELETE` | `/documents/{id}` | Delete a document |
| `GET` | `/documents` | List indexed documents |

### Usage (`/api`)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/usage` | Get daily LLM token usage stats |

### Utility

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | API root (health message) |
| `GET` | `/health` | Health check endpoint |
| `GET` | `/docs` | Swagger UI (interactive API docs) |
| `GET` | `/redoc` | ReDoc API documentation |

---

## 🎨 Frontend

A modern, responsive React SPA with a polished chat interface:

### Features

| Feature | Description |
|---|---|
| **Chat Interface** | Real-time streaming responses with markdown rendering and syntax highlighting |
| **Knowledge Base** | Upload, view, and manage documents with visibility controls |
| **Conversation History** | Sidebar with searchable conversation list, create/switch/delete |
| **Authentication** | Login/register forms, token management, auto-refresh |
| **Usage Dashboard** | Daily token usage statistics and charts |
| **Responsive Design** | Mobile-friendly layout with collapsible sidebar |
| **Dark Mode** | Modern dark theme with Geist Mono and Inter fonts |
| **Error Handling** | Typed API errors, retry logic, user-friendly error messages |

### Frontend Architecture

```
frontend/src/
├── api/              # HTTP client, typed endpoints, SSE streaming
│   ├── client.ts     # Axios-based API client with interceptors
│   ├── auth.ts       # Auth endpoints
│   ├── chat.ts       # Chat & conversation endpoints
│   ├── agent.ts      # Agent endpoints
│   ├── rag.ts        # Document management endpoints
│   ├── stream.ts     # SSE streaming utilities
│   ├── errors.ts     # Typed error handling
│   └── types.ts      # TypeScript interfaces
├── auth/             # Auth context, token management
├── components/       # Reusable UI components
│   ├── layout/       # AppShell, sidebar, navigation
│   ├── markdown/     # Markdown renderer with code highlighting
│   ├── mascot/       # 3D chatbot mascot assets
│   └── ui/           # Buttons, inputs, modals
├── features/         # Feature modules
│   ├── auth/         # Login/register pages
│   ├── chat/         # Chat panel, message bubbles
│   ├── history/      # Conversation history sidebar
│   ├── knowledge/    # Knowledge base management
│   └── usage/        # Token usage dashboard
├── hooks/            # Custom React hooks
├── lib/              # Utility functions
├── styles/           # Global CSS (TailwindCSS)
└── config/           # App configuration
```

---

## 🗄 Database Schema

### MongoDB Collections

```
┌─────────────────────────────────────────────────────────────┐
│                         MongoDB                              │
│                                                              │
│  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐   │
│  │    users      │  │  chat_history   │  │ refresh_tokens │   │
│  ├──────────────┤  ├────────────────┤  ├────────────────┤   │
│  │ _id          │  │ _id            │  │ _id            │   │
│  │ email (uniq) │  │ user_id        │  │ user_id        │   │
│  │ hashed_pass  │  │ conversation_id│  │ token_hash     │   │
│  │ role         │  │ message        │  │ expires_at     │   │
│  └──────────────┘  │ response       │  │ revoked        │   │
│                    │ model          │  │ created_at     │   │
│                    │ created_at     │  └────────────────┘   │
│                    │ (TTL: 90 days) │                        │
│                    └────────────────┘                        │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │   token_usage     │  │  langgraph_checkpoints           │ │
│  ├──────────────────┤  │  (Agent state persistence)       │ │
│  │ user_id + date   │  │  - Run resume after restart      │ │
│  │ requests         │  │  - Approval flow state           │ │
│  │ llm_calls        │  │  - TTL: 7 days (configurable)   │ │
│  │ input_tokens     │  └──────────────────────────────────┘ │
│  │ output_tokens    │                                       │
│  │ total_tokens     │                                       │
│  └──────────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
```

### ChromaDB (Vector Store)

```
┌─────────────────────────────────────────────────────────┐
│                    ChromaDB Collection                    │
│             (one collection per embedding model)         │
│                                                          │
│  Per chunk:                                              │
│  ├── id: "{document_id}_{chunk_index}"                   │
│  ├── embedding: float[] (from Gemini)                    │
│  ├── document: chunk text                                │
│  └── metadata:                                           │
│      ├── document_id, source, doc_type                   │
│      ├── visibility (shared/private), owner_id           │
│      ├── chunk_index, chunk_hash, section                │
│      ├── content_hash, chunking signature                │
│      └── embedding_model                                 │
│                                                          │
│  + In-memory BM25 index (rebuilt on changes)             │
└─────────────────────────────────────────────────────────┘
```

---

## 🧪 Evaluation Framework

The project includes a custom **evaluation framework** (`evals/`) for measuring RAG quality and agent performance:

| Component | Description |
|---|---|
| `evals/run.py` | Main evaluation runner — executes test datasets against the live system |
| `evals/judges.py` | LLM-as-Judge evaluators for answer quality, faithfulness, and relevance |
| `evals/metrics.py` | Quantitative metrics: MRR, precision, recall, F1 |
| `evals/chunking.py` | Chunk quality evaluation: boundary quality, information preservation |
| `evals/checks.py` | Automated checks: prompt injection resistance, PII handling |
| `evals/datasets/` | Curated test question/answer pairs |
| `evals/reports/` | Generated evaluation reports |
| `evals/schema.py` | Evaluation case and result schemas |
| `evals/pricing.py` | LLM cost estimation for eval runs |

---

## 📁 Project Structure

```
ai-developer-assistant/
│
├── app/                          # FastAPI Backend
│   ├── main.py                   # App entry point, lifespan, routes
│   ├── config.py                 # Pydantic settings (all env vars)
│   ├── database.py               # MongoDB async operations
│   ├── middleware.py              # RequestID, BodySize, token tracking
│   ├── limiter.py                # SlowAPI rate limiter setup
│   ├── security.py               # JWT token creation/verification
│   ├── auth.py                   # Password hashing utilities
│   ├── schemas.py                # Pydantic request/response models
│   ├── dependencies.py           # FastAPI dependency injection
│   ├── exceptions.py             # Global exception handlers
│   ├── custom_exceptions.py      # AppException class
│   │
│   ├── routes/                   # API route handlers
│   │   ├── chat.py               # Chat & conversation endpoints
│   │   ├── auth.py               # Authentication endpoints
│   │   ├── rag.py                # Document & search endpoints
│   │   ├── agent.py              # Agentic chat endpoints
│   │   └── usage.py              # Token usage endpoint
│   │
│   ├── services/                 # Business logic layer
│   │   ├── llm_service.py        # Groq LLM client + retry logic
│   │   ├── chat_service.py       # Chat orchestration
│   │   ├── rag_service.py        # Full RAG pipeline (index, retrieve, delete)
│   │   ├── embedding_service.py  # Gemini embedding client
│   │   ├── vector_store_service.py # ChromaDB operations
│   │   ├── reranker_service.py   # Cross-encoder reranking
│   │   ├── answerability_service.py # LLM answerability judge
│   │   ├── keyword_index.py      # BM25 index + RRF fusion
│   │   ├── ingestion_service.py  # Document cleaning & normalization
│   │   ├── document_service.py   # Chunking strategies
│   │   ├── web_search_service.py # Tavily web search + caching
│   │   ├── embedding_migration.py # Embedding model migration
│   │   └── tool_llm_service.py   # Tool-specific LLM wrappers
│   │
│   ├── agents/                   # LangGraph agent system
│   │   ├── orchestrator.py       # Top-level graph: classify → route → agent
│   │   ├── router.py             # Message classifier (RouteDecision)
│   │   ├── supervisor.py         # Multi-agent supervisor pattern
│   │   ├── calculator_agent.py   # ReAct agent builder + AgentState
│   │   ├── agent_service.py      # Run management, streaming, approval
│   │   ├── final_answer.py       # Final answer extraction
│   │   ├── context.py            # Context compaction logic
│   │   ├── checkpoints.py        # MongoDB checkpointer setup
│   │   └── prompts.py            # Security rules + conversation rules
│   │
│   ├── tools/                    # Agent tool definitions
│   │   ├── registry.py           # Tool registry + RBAC
│   │   ├── calculator.py         # Safe math expression evaluator
│   │   ├── rag_search.py         # Knowledge base search tool
│   │   ├── web_search.py         # Web search tool
│   │   ├── package_info.py       # PyPI/npm package lookup
│   │   ├── text_analyzer.py      # Text statistics tool
│   │   ├── delete_document.py    # Document deletion (with approval)
│   │   ├── tool_result.py        # Tool result formatting
│   │   └── schemas.py            # Tool input schemas
│   │
│   ├── guards/                   # Security guards
│   │   └── injection.py          # Prompt injection heuristic detection
│   │
│   ├── utils/                    # Cross-cutting utilities
│   │   ├── llm_logging.py        # LLM call logging (tokens, latency)
│   │   ├── log_context.py        # Request-scoped log context
│   │   ├── request_metrics.py    # Per-request token counters
│   │   ├── redaction.py          # Log redaction filter
│   │   ├── disconnect.py         # Client disconnect detection
│   │   ├── url_safety.py         # URL scheme validation
│   │   ├── hashing.py            # Content hashing
│   │   └── agent_logger.py       # Agent-specific logger
│   │
│   └── scripts/                  # Management scripts
│       ├── reembed.py            # Re-embed all chunks for model migration
│       └── promote_admin.py      # Promote a user to admin role
│
├── frontend/                     # React + Vite + TypeScript Frontend
│   ├── src/
│   │   ├── api/                  # API client, types, streaming, errors
│   │   ├── auth/                 # Auth context & token management
│   │   ├── components/           # UI components (layout, markdown, mascot)
│   │   ├── features/             # Feature modules (chat, knowledge, auth, etc.)
│   │   ├── hooks/                # Custom React hooks
│   │   ├── lib/                  # Utilities
│   │   ├── styles/               # TailwindCSS styles
│   │   └── config/               # App configuration
│   ├── package.json
│   ├── vite.config.ts
│   ├── vercel.json               # Vercel deployment config
│   └── tsconfig.json
│
├── tests/                        # 80+ test files
│   ├── conftest.py               # Shared fixtures (mock LLM, DB, vector store)
│   ├── test_rag_*.py             # RAG pipeline tests
│   ├── test_agent_*.py           # Agent system tests
│   ├── test_auth.py              # Authentication tests
│   ├── test_prompt_injection.py  # Security tests
│   └── ...
│
├── evals/                        # Evaluation framework
│   ├── run.py                    # Evaluation runner
│   ├── judges.py                 # LLM-as-Judge evaluators
│   ├── metrics.py                # Quality metrics (MRR, precision, etc.)
│   ├── datasets/                 # Test datasets
│   └── reports/                  # Generated reports
│
├── docs/
│   └── ROADMAP.md                # Development roadmap
│
├── Dockerfile                    # Production Docker image (Python 3.12-slim)
├── compose.yaml                  # Docker Compose (API + MongoDB)
├── render.yaml                   # Render cloud deployment
├── requirements.txt              # Python dependencies
├── pytest.ini                    # Test configuration
├── .env.example                  # Environment variable template
└── .coveragerc                   # Code coverage config
```

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.12+
- **Node.js** 18+
- **MongoDB** 8.x (local or Atlas)
- **Groq API Key** (free at [console.groq.com](https://console.groq.com))
- **Gemini API Key** (free at [aistudio.google.com](https://aistudio.google.com))

### 1. Clone & Setup Backend

```bash
git clone https://github.com/DharamSojitra1/ai-developer-assistant.git
cd ai-developer-assistant

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.\.venv\Scripts\Activate.ps1

# Activate (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and set at minimum:
# - API_KEY (any random string)
# - JWT_SECRET_KEY (run: python -c "import secrets; print(secrets.token_urlsafe(48))")
# - GROQ_API_KEY (from Groq console)
# - GEMINI_API_KEY (from Google AI Studio)
# - MONGODB_URI (default: mongodb://localhost:27017)
# - MOCK_MODE=false (to use real LLMs)
```

### 3. Start Backend

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now running at `http://localhost:8000` with interactive docs at `/docs`.

### 4. Setup & Start Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend is now running at `http://localhost:5173`.

### 5. Using Docker Compose (Alternative)

```bash
# Start both API and MongoDB
docker compose up --build

# The API will be available at http://localhost:8000
```

---

## ⚙ Environment Variables

See [`.env.example`](.env.example) for the full list with descriptions. Key groups:

| Group | Key Variables |
|---|---|
| **App** | `APP_NAME`, `APP_ENV`, `DEBUG`, `API_KEY`, `FRONTEND_URL` |
| **LLM** | `GROQ_API_KEY`, `GROQ_MODEL_NAME`, `ROUTER_MODEL_NAME`, `GEMINI_API_KEY`, `MOCK_MODE` |
| **Agent** | `AGENT_TEMPERATURE`, `AGENT_MAX_ITERATIONS`, `AGENT_HISTORY_LIMIT`, `AGENT_ROUTING_ENABLED`, `SUPERVISOR_MAX_ROUNDS` |
| **RAG** | `RAG_DISTANCE_THRESHOLD`, `RAG_RETRIEVAL_TOP_K`, `RAG_FINAL_TOP_K`, `RAG_HYBRID_SEARCH`, `RAG_CHUNK_SIZE` |
| **Embeddings** | `EMBEDDING_MODEL_NAME` |
| **Reranker** | `ENABLE_RERANKER`, `RERANKER_MODEL_NAME`, `RERANKER_DEVICE` |
| **Web Search** | `TAVILY_API_KEY`, `WEB_SEARCH_MAX_RESULTS`, `WEB_SEARCH_CACHE_TTL_SECONDS` |
| **MongoDB** | `MONGODB_URI`, `MONGODB_DATABASE` |
| **JWT** | `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` |
| **Rate Limits** | `RATE_LIMIT_ENABLED`, `RATE_LIMIT_CHAT`, `RATE_LIMIT_AGENT`, `RATE_LIMIT_RAG` |
| **Privacy** | `CHAT_HISTORY_RETENTION_DAYS`, `LOG_REDACT_TOOL_ARGS` |

---

## 🌐 Deployment

### Backend — Render (Free Tier)

The project includes a [`render.yaml`](render.yaml) for one-click Render deployment:

```bash
# 1. Push to GitHub
# 2. Connect repo to Render
# 3. Set environment variables in Render dashboard:
#    - MONGODB_URI (use MongoDB Atlas free tier)
#    - GROQ_API_KEY, GEMINI_API_KEY
#    - FRONTEND_URL (your Vercel URL)
# 4. API_KEY and JWT_SECRET_KEY are auto-generated
```

### Frontend — Vercel

```bash
# 1. Import the `frontend/` directory in Vercel
# 2. Set VITE_API_BASE_URL to your Render API URL
# 3. Deploy
```

### Docker

```bash
# Production build
docker build -t ai-developer-assistant .
docker run -p 8000:8000 --env-file .env ai-developer-assistant
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test categories
pytest tests/test_rag_*.py          # RAG pipeline tests
pytest tests/test_agent_*.py        # Agent system tests
pytest tests/test_auth.py           # Authentication tests
pytest tests/test_prompt_injection.py  # Security tests

# Frontend tests
cd frontend
npm run test
```

### Test Coverage

The test suite includes **80+ test files** covering:

- RAG retrieval quality (MRR, relevance, reranking, hybrid search)
- Agent routing, tool execution, streaming, approval flows
- Authentication and authorization
- Prompt injection resistance
- Rate limiting and request validation
- Document ingestion and deduplication
- Configuration validation
- Observability and logging

---

## 📄 License

This project is open source. See the repository for license details.

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/DharamSojitra1">Dharam Sojitra</a>
</p>