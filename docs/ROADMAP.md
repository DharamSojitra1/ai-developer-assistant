# Roadmap: Production and Interview-Ready Phase

Living tracker for the remaining work on AI Developer Assistant. Tick checkboxes as sub-tasks land, update the item status, and add a line to the [Changelog](#changelog).

Completed: items 1-18 (FastAPI backend, auth, MongoDB chat history, LLM integration, RAG with Chroma, tool calling, LangGraph agent, agent memory, streaming, logging), Phase A, items 19-21 (agent state, tool architecture, agent configuration), items 22-23 (testing strategy, agent evaluation), items 25-26 (production RAG, advanced agent patterns), and item 27 (security hardening). In progress: item 24 (only tracing left) and item 28. See [Known issues](#known-issues) for cleanup found in the latest audit.

Last updated: 2026-10-11

## Status legend

- **Done**: all checklist items complete and "Done when" criteria met
- **In progress**: actively being worked on
- **Next**: the item to pick up next
- **Not started**: not yet begun



## Overview

- [19. Proper Agent State](#19-proper-agent-state): Done
- [20. Better Tool Architecture](#20-better-tool-architecture): Done
- [21. Agent Configuration](#21-agent-configuration): Done
- [22. Proper Testing Strategy](#22-proper-testing-strategy): Done
- [23. Agent Evaluation](#23-agent-evaluation): Done
- [24. Production Observability](#24-production-observability): In progress
- [25. Production RAG Improvements](#25-production-rag-improvements): Done
- [26. Agent Advanced Patterns](#26-agent-advanced-patterns): Done
- [27. Security Hardening](#27-security-hardening): Done
- [28. Docker + Deployment](#28-docker--deployment): In progress
- [29. Frontend / Production API Usage](#29-frontend--production-api-usage): Not started
- [30. Interview Preparation](#30-interview-preparation): Not started



## Suggested order

- **Phase A, Agent core hardening**: 19, 20, 21
- **Phase B, Quality**: 22, 23, 24
- **Phase C, Capability**: 25, 26
- **Phase D, Ship**: 27, 28, 29
- **Phase E, Career**: 30 (run alongside every phase; each item above feeds interview material)

---



## Phase A: Agent core hardening



### 19. Proper Agent State

**Status:** Done

**Current state:** `AgentState` in `app/agents/calculator_agent.py` has `messages`, `iteration_count`, `sources`, `tool_calls`, `run_id`, `started_at`, and `stop_reason`. After `tools`, a `collect_sources` node writes deduplicated `search_knowledge_base` results into `sources`, and a `collect_tool_calls` node records each tool call's name, args, and success or error status into `tool_calls`. `stop_reason` is set to `final_answer` by the LLM node or `max_iterations` by the guard node. `agent_service.py` creates the run ID and start time, returns `result["sources"]` directly, and logs tool calls and run metadata (run ID, start and end time, duration, stop reason) for both the normal and streaming endpoints.

**Checklist:**

- [x] Decide which fields earn their place (only add fields with a consumer)
- [x] Populate `sources` inside the graph (e.g. a reducer or post-tool node) instead of parsing after the run
- [x] Track tool usage (tool name, args, success/failure) if it is used by the API response, logs, or evaluation
- [x] Track execution metadata (run ID, start/end time, stop reason such as `final_answer` or `max_iterations`) if consumed by observability
- [x] Remove the post-run `ToolMessage` parsing from `agent_service.py`
- [x] Update tests for the new state shape

**Done when:** every state field is read by something (API, logs, or tests), and `agent_service.py` returns sources directly from the final state.

**Key files:** `app/agents/calculator_agent.py`, `app/agents/agent_service.py`, `tests/test_agent_execution_tracking.py`, `tests/test_agent_logging.py`

### 20. Better Tool Architecture

**Status:** Done

**Current state:** `app/tools/calculator.py` uses an AST-based evaluator (numeric literals and arithmetic operators only), with tests rejecting function calls, Python code, and variables. It also caps expression length (200 characters), exponent size (1000), result size (1000 digits), and nesting depth (50), rejecting oversized powers before computing them. Every tool has a Pydantic `args_schema` (length limits and field descriptions) and returns JSON in the shape `{"ok", "result", "error"}` via helpers in `app/tools/tool_result.py`; invalid input comes back in the same shape instead of raising. `ToolNode` uses `handle_tool_exception`, so an unexpected crash in any tool reaches the LLM as a generic `{"ok": false}` error while the real exception is only logged. The one exception is an LLM calling a tool name that doesn't exist: `ToolNode` answers that with its own plain-text message listing the valid tool names. Async tools can use the `with_timeout` decorator (`TOOL_TIMEOUT_SECONDS`, default 30), which returns a structured timeout error; `search_knowledge_base` uses it, and the blocking Chroma search and reranking in `RAGService.retrieve` run via `asyncio.to_thread` so they neither stall the event loop nor escape the timeout. `app/tools/registry.py` lists every tool with its allowed roles, whether it is deterministic, and its side effects; `create_agent_graph(role=...)` gives both the LLM and `ToolNode` only the tools that role may use (unknown roles get none), and the agent routes pass the user's role through. Only `search_knowledge_base` is non-deterministic (documented in its module docstring and registry entry). Tool inputs reject blank strings, wrong types, and unknown arguments, and the calculator rejects booleans, float overflow (`inf`/`nan`), and complex results. Each tool has tests for malicious and malformed input (`tests/test_calculator.py`, `tests/test_text_analyzer.py`, `tests/test_rag_tool.py`, `tests/test_tool_registry.py`). `ToolNode` runs with `handle_tool_errors=True`. Tools live in `app/tools/` (`calculator`, `text_analyzer`, `rag_search`, and `delete_document` from item 26).

**Checklist:**

- [x] Replace `eval()` with a safe AST-based evaluator (whitelist numeric literals and arithmetic operators only)
- [x] Guard against huge computations (e.g. cap exponent size / input length)
- [x] Tool input validation with Pydantic `args_schema`
- [x] Tool output schemas (consistent structured result, e.g. `{ "ok": ..., "result": ..., "error": ... }`)
- [x] Structured tool errors returned to the LLM instead of raw exceptions
- [x] Timeout considerations for slow tools (RAG search, future network tools)
- [x] Tool permissions (which tools a user/agent may call)
- [x] Keep tools deterministic and side-effect free where possible; document any that are not
- [x] Unit tests per tool, including malicious and malformed inputs

**Done when:** no `eval()`/`exec()` remains in `app/`, every tool has an input schema and a consistent output/error shape, and tool tests cover invalid input.

**Key files:** `app/tools/calculator.py`, `app/tools/text_analyzer.py`, `app/tools/rag_search.py`, `tests/test_calculator_agent.py`, `tests/test_tool_calling.py`

### 21. Agent Configuration

**Status:** Done

**Current state:** `app/config.py` defines a `pydantic-settings` `Settings` class that validates every variable at startup (types, ranges such as `AGENT_TEMPERATURE` 0-2 and `AGENT_MAX_ITERATIONS` 1-20, `RERANKER_DEVICE` limited to `auto`/`cpu`/`cuda`, non-empty `API_KEY` and `JWT_SECRET_KEY`) and re-exports the same module-level constants, so existing imports are unchanged. `agent_service.py` and `calculator_agent.py` read `AGENT_TEMPERATURE`, `AGENT_MAX_TOKENS`, `AGENT_MAX_ITERATIONS`, and `AGENT_HISTORY_LIMIT` from config, and `FRONTEND_URL` is env-backed. `tests/test_config.py` checks defaults, overrides, invalid values, and that every setting is listed in `.env.example`.

**Checklist:**

- [x] Add env-backed settings to `app/config.py` (e.g. `AGENT_TEMPERATURE`, `AGENT_MAX_TOKENS`, `AGENT_MAX_ITERATIONS`, `AGENT_HISTORY_LIMIT`)
- [x] Use those settings in `agent_service.py` and `calculator_agent.py`
- [x] Make `FRONTEND_URL` env-backed
- [x] Document new variables in `.env.example`
- [x] Optional: move to `pydantic-settings` for typed validation

**Done when:** no agent tuning values are hardcoded outside `app/config.py`, and `.env.example` lists all of them.

**Key files:** `app/config.py`, `app/agents/agent_service.py`, `app/agents/calculator_agent.py`, `.env.example`, `tests/test_config.py`

---



## Phase B: Quality



### 22. Proper Testing Strategy

**Status:** Done

**Current state:** 72 test files in `tests/` (539 offline tests after item 27) covering agent, routes, streaming, RAG (relevance, reranking, thresholds, MRR, fallback, answerability), auth, database, and tools. `pytest.ini` registers `unit`, `integration`, and `live` markers with `--strict-markers`; `tests/conftest.py` applies `unit`/`integration` automatically (integration if a test uses a DB or app-client fixture or is `live`), and every paid-API test is marked `live`, so `pytest -m "not live"` costs nothing. An autouse fixture forces chat mock mode for non-live tests regardless of `.env`. The shared `scripted_llm` fixture (`ScriptedLLM`, a fake `BaseChatModel` that supports streaming) scripts tool calls and answers, and is used by the agent routing, execution tracking, tool error, and tool permission tests. A MongoDB outage (`ConnectionFailure`) now returns 503 `DATABASE_UNAVAILABLE` with `Retry-After` instead of a 500, covered by `tests/test_database_failures.py`. Coverage via `pytest-cov` and `.coveragerc` (branch coverage over `app/`): 90.2% on the non-live suite when item 22 closed (not re-measured since). Markers and commands were documented in `README.md`, but the README has since been cut back to a short stub, so they need documenting again (see [Known issues](#known-issues)).

**Checklist:**

- [x] Unit tests (pure functions, tools, services with dependencies mocked)
- [x] Integration tests (routes plus DB/vector store)
- [x] Agent routing tests (correct path through the graph for a given LLM response)
- [x] Tool tests
- [x] RAG tests (ingestion, retrieval, empty results)
- [x] API tests (status codes, auth, validation)
- [x] Streaming tests (chunk order, tool output not leaked)
- [x] Failure tests (LLM timeout, tool error, DB down, max iterations)
- [x] Shared mock-LLM fixture in `tests/conftest.py` (scripted tool calls and answers)
- [x] pytest markers (`unit`, `integration`) registered and documented
- [x] Coverage report

**Done when:** tests can be run by type via markers, a shared mock LLM is used across agent tests, and each failure mode above has at least one test.

**Key files:** `tests/`, `tests/conftest.py`, `pytest.ini`, `.coveragerc`, `tests/test_database_failures.py`, `tests/test_agent_routing.py`, `app/exceptions.py`

### 23. Agent Evaluation

**Status:** Done (optional LangSmith and RAGAS integrations deferred)

**Current state:** evaluation cases live in `evals/datasets/` as JSONL (one case per line, `#` comments allowed). `agent.jsonl` holds questions with expected tools, expected answer rules (`contains`, `contains_any`, `refusal`; rules rather than exact text because LLM wording varies), and expected source document IDs (`[]` = no sources allowed, `null` = not checked). `rag.jsonl` holds retrieval queries with an expected document ID, or `null` for negative queries that must retrieve nothing. `evals/schema.py` validates every line with Pydantic (unknown fields, blank strings, unknown tool names, duplicate IDs, and contradictory rules are rejected with file and line number), and `evals/checks.py` compares an agent run against a case and returns one message per unmet expectation. `tests/test_agent_evaluation.py` and `tests/test_rag_evaluation.py` are parametrized over the datasets (live), computing Hit Rate@3 and MRR@3; `tests/test_eval_datasets.py` tests the loader and checks offline. Cases can also carry a `numeric` answer rule and a `reference_answer`. `evals/judges.py` adds two LLM-as-judge evaluators with structured output: `CorrectnessJudge` grades the answer against the reference (`correct` / `partially_correct` / `incorrect`; only `correct` passes), and `FaithfulnessJudge` splits the answer into atomic claims and checks each against the retrieved chunk text (score = supported ÷ total, pass at ≥ 0.9; skipped when nothing was retrieved or the answer makes no claims). The live agent evaluation runs the free rule checks first and calls the judges only if they pass. Judges accept an injected runnable and are tested offline in `tests/test_eval_judges.py`. The judge uses the same Groq model as the agent, so it may grade leniently. Hallucination detection has two layers: a free rule (cases marked `grounded` must refuse when nothing was retrieved) and the faithfulness judge, which now checks claims against both retrieved documents and tool results (e.g. the calculator output); `summarize()` reports a hallucination rate (cases with any unsupported claim) and the hallucinated case IDs. `RelevanceJudge` checks that the answer addresses the question (`relevant` / `partially_relevant` / `irrelevant`; skipped for refusal cases); retrieval relevance is covered by the distance, rerank, and answerability gates plus Hit Rate@3 / MRR@3. The agent dataset has 9 cases, including 4 near-miss negatives. The live test prints a report (correctness accuracy, mean faithfulness, hallucination rate, relevance rate).

`python -m evals.run` (`evals/run.py`) is the eval runner: it runs the agent and RAG suites (filterable with `--suite`, `--ids`, `--tags`; `--no-judges` for a cheaper run), prints a summary, writes the full per-case report as JSON to `evals/reports/` (gitignored), and exits 1 if any case fails. Unlike the pytest suite it runs the judges even when a rule fails, so judge metrics cover every applicable case. The summary reports pass rate, tool-selection accuracy, correctness accuracy, mean faithfulness, hallucination rate (grounding rule plus faithfulness judge), relevance rate, Hit Rate@3, MRR@3, false-positive rate, and per-run latency (mean, p50, p95, max), tokens, and cost, with agent and judge usage reported separately. Latency and tokens are measured by `evals/usage.py` using LangChain's `get_usage_metadata_callback`, which also captures nested LLM calls such as the answerability check inside RAG search. Cost uses the per-model price table in `evals/pricing.py` (unknown models give no cost rather than zero; Gemini embedding calls are not counted). The agent runner (`evals/agent_runner.py`) and retrieval metrics (`evals/metrics.py`) are shared by the CLI and the pytest suites. Offline tests: `tests/test_eval_runner.py`.

The first live run caught two real hallucinations: the agent answered "According to the knowledge base, who created Python?" with "Guido van Rossum" (nothing retrieved), and padded a Generative AI answer with unsupported examples. Fixed by adding grounding rules to `SYSTEM_PROMPT` in `app/agents/calculator_agent.py` (answer knowledge-base questions only from `search_knowledge_base` results; say so when they do not answer the question).

**Checklist:**

- [x] Evaluation dataset (questions with expected tool, expected answer, expected sources)
- [x] Expected outputs format and storage (e.g. `evals/datasets/*.jsonl`)
- [x] Tool-selection evaluation (did the agent choose the correct tool?)
- [x] RAG retrieval evaluation (did retrieval return the right chunks? hit rate / recall@k)
- [x] Answer correctness
- [x] Faithfulness (did the final answer use the retrieved context?)
- [x] Hallucination detection
- [x] Relevance
- [x] Latency measurement per run
- [x] Token and cost tracking per run
- [x] Eval runner script producing a summary report
- [ ] Optional: LangSmith
- [ ] Optional: RAGAS
- [x] Optional: LLM-as-judge custom evaluators

**Done when:** a single command runs the eval dataset and prints tool-selection accuracy, retrieval metrics, faithfulness, latency, and token usage.

**Key files:** `evals/run.py`, `evals/datasets/agent.jsonl`, `evals/datasets/rag.jsonl`, `evals/schema.py`, `evals/checks.py`, `evals/judges.py`, `evals/usage.py`, `evals/pricing.py`, `evals/metrics.py`, `evals/agent_runner.py`, `tests/test_agent_evaluation.py`, `tests/test_rag_evaluation.py`, `tests/test_eval_datasets.py`, `tests/test_eval_judges.py`, `tests/test_eval_runner.py`

### 24. Production Observability

**Status:** In progress

**Current state:** `app/middleware.py` assigns an `X-Request-ID` per request and binds it in a context variable (`app/utils/log_context.py`) for the whole request, including streaming bodies; `agent_service.py` binds the agent `run_id` and `user_id` the same way for each run. A `LogContextFilter` on the root JSON handler (`app/main.py`) stamps `request_id`, `run_id`, and `user_id` onto every log record, including logs from tools, RAG, and threads (`asyncio.to_thread` and LangGraph tasks copy the context); values passed via `extra` win. `app/utils/llm_logging.py` registers a LangChain callback handler process-wide (a configure hook, installed from `llm_service.py`), so every chat-model call, including the RAG chat chain and the answerability check nested inside RAG search, logs `LLM call completed` (logger `agent.llm`: model, latency_ms, input/output/total tokens, message count, tool-call count, finish reason) or `LLM call failed` (error type). Every tool execution logs `Agent tool executed` (logger `agent.tools`: name, args, success/error, latency_ms, error type on crash) as it happens; the run-completed log keeps a name/status summary that also covers calls rejected without running. Prompts, answers, and tool outputs are never logged. The request middleware logs `Request completed` (logger `app.request`) for every request once the response body has finished streaming, with method, path, route template, status, duration_ms, user ID, and that request's LLM call count and token totals. Tokens are summed per request in a context-bound `RequestMetrics` (`app/utils/request_metrics.py`) fed by the LLM callback, then added to a per-user, per-day `token_usage` collection in MongoDB; `GET /api/usage/me` returns a user's daily usage and totals. Agent failures log `Agent execution failed` with run ID and the failing step (`load_history`, `llm`, `tools`, `save_history`, ...), and the API error handlers (`app/exceptions.py`) log request ID, path, method, user ID, run ID, and step without repeating the traceback. Offline tests: `tests/test_observability_logging.py`, `tests/test_request_observability.py`; live: `tests/test_agent_logging.py`.

**Checklist:**

- [x] Propagate request ID into agent logs (e.g. via `contextvars`)
- [x] Agent run ID per execution
- [x] Log each LLM call (model, latency, token usage)
- [x] Log each tool call (name, latency, success/error)
- [x] Total request latency
- [x] Token usage aggregation per request/user
- [x] Error logging with context (request ID, run ID, step)
- [x] Structured (JSON) log output
- [ ] Adopt a tracing solution (LangSmith, Langfuse, or OpenTelemetry)

**Done when:** a single request can be followed end to end (request ID to run ID to each LLM and tool call) with latency and token counts.

**Key files:** `app/middleware.py`, `app/utils/log_context.py`, `app/utils/llm_logging.py`, `app/utils/request_metrics.py`, `app/utils/agent_logger.py`, `app/agents/agent_service.py`, `app/exceptions.py`, `app/routes/usage.py`, `app/database.py`, `app/main.py`

---



## Phase C: Capability



### 25. Production RAG Improvements

**Status:** Done (optional vector-store migration not started)

**Current state:** Chroma persisted in `chroma_db/`, with document, embedding, vector-store, and RAG services in `app/services/` and a `search_knowledge_base` tool. `RAGService.retrieve` filters by distance (`RAG_DISTANCE_THRESHOLD`), reranks with a cross-encoder (`RerankerService`), drops results below `RERANKER_SCORE_THRESHOLD`, and gates the context through an LLM answerability check (`AnswerabilityService`). It returns no results if reranking or answerability fails. Chunks use deterministic IDs (`{document_id}_{i}`) and are upserted; re-indexing a document removes leftover chunks beyond the new chunk count (`VectorStoreService.delete_stale_chunks`). `DELETE /documents/{document_id}` removes all chunks of a document. Ingestion runs load, clean, chunk, embed, and store: `POST /api/rag/upload` accepts `.txt`, `.md`, and `.pdf` files (`RAG_MAX_UPLOAD_BYTES`, default 5 MB; PDFs via `pypdf`) and `POST /api/rag/index` accepts raw text. `app/services/ingestion_service.py` loads and cleans the text (Unicode normalization, control and zero-width character removal, whitespace collapsing, PDF hyphenation repair), and `RAGService.index_document` chunks, embeds, and stores it. Every chunk carries `source`, `doc_type`, `visibility` (`shared`/`private`), and `owner_id`. Any user can add private documents; only admins can add shared ones. Users can only overwrite or delete their own documents, and admins can delete (but not overwrite) other users' private documents. Search (`/api/rag/search`, chat RAG, and the agent's `search_knowledge_base` tool, which takes the user from the request context) returns shared documents plus the caller's own private ones, and the search endpoint can also filter by `source` and `doc_type`. Chunks indexed before this change are backfilled once as shared when the vector store opens.

Chunking (`app/services/document_service.py`) is structure-aware: Markdown is split on `#`/`##`/`###` headings first, and each chunk is prefixed with its heading path (also stored as `section`); text and PDFs split on paragraph, then sentence and clause boundaries. Size and overlap come from `RAG_CHUNK_SIZE`/`RAG_CHUNK_OVERLAP` (800/100). `python -m evals.chunking` sweeps sizes and overlaps on a 4-document, 20-question corpus (`evals/datasets/chunking/`), checking that a top-3 chunk contains the answer phrase. Sizes from 500 to 1200 all scored hit@3 = MRR = 1.0; 300 lost ranking quality in vector-only search (MRR 0.97). The corpus is too easy to separate sizes of 500 and above.

Retrieval is hybrid (`RAG_HYBRID_SEARCH`): an in-memory BM25 index (`app/services/keyword_index.py`, rebuilt when the collection changes) runs next to vector search, with the same access filters. Results are merged by reciprocal rank fusion (`RAG_RRF_K`) and deduplicated by chunk text before reranking. Keyword-only matches skip the distance threshold but still pass the reranker and answerability check. If keyword search fails, retrieval falls back to vector results.

Duplicates: each document stores a SHA-256 `content_hash` of its cleaned text and each chunk a `chunk_hash`. Re-indexing identical content with the same settings returns `status: unchanged` without embedding. Identical content under another ID is rejected with 409; only documents the caller can see count, so another user's private document is never revealed. Repeated chunks inside a document are stored once, and chunk embeddings are reused by hash, so editing a document only embeds the changed chunks.

Embedding versioning: each `EMBEDDING_MODEL_NAME` has its own Chroma collection (`documents-<model>`, because vector dimensions are fixed per collection). Every chunk records `embedding_model` and `chunking`. After a model change, `python -m app.scripts.reembed` fills the new collection from older ones: it copies vectors when the model is unchanged and re-embeds otherwise. It supports `--dry-run` and `--drop-old`. Startup logs a warning while chunks are still pending. The pre-versioning `documents` collection was copied into `documents-gemini-embedding-001` without any embedding calls and is kept until it is dropped with `--drop-old`.

**Checklist:**

- [x] Document ingestion pipeline (load, clean, chunk, embed, store)
- [x] Metadata filtering (by user, source, document type)
- [x] Chunking strategy (size/overlap tuning, structure-aware splitting)
- [x] Similarity thresholds (drop low-relevance results)
- [x] Hybrid search (keyword + vector)
- [x] Reranking
- [x] Document deletion and update
- [x] Duplicate handling (content hashing)
- [x] Embedding versioning (re-embed on model change)
- [ ] Optional: migrate to Postgres + pgvector or another production vector store

**Done when:** documents can be added, updated, and deleted without duplicates, retrieval respects metadata filters and thresholds, and retrieval quality is measured by item 23.

**Key files:** `app/services/` (`ingestion_service.py`, `document_service.py`, `keyword_index.py`, `rag_service.py`, `vector_store_service.py`, `embedding_migration.py`), `app/scripts/reembed.py`, `app/routes/rag.py`, `app/tools/rag_search.py`, `evals/chunking.py`

### 26. Agent Advanced Patterns

**Status:** Done

**Current state:** `/api/agent/chat` and `/api/agent/chat/stream` run an orchestrator graph (`app/agents/orchestrator.py`). An LLM classifier (`app/agents/router.py`, structured `RouteDecision`) picks one route per message: `knowledge_base` goes to a RAG agent (only `search_knowledge_base`), `calculation` to a calculator agent (`calculator`, `analyze_text`), `chat` to a single LLM call with no tools, `multi_agent` to the supervisor, and `general` to the tool agent with every tool the role allows. If the classifier fails, or `AGENT_ROUTING_ENABLED=false`, the message goes to `general`. Every agent is built by `build_tool_agent` in `app/agents/calculator_agent.py` (LLM, optional approval step, ToolNode, source and tool-call collection, max-iterations guard), and every agent's tools are filtered by the role registry. The route is returned in the response and logged on "Agent execution completed". `create_agent_graph()` still builds the single tool agent used by evals and older tests.

Parallel tools: tools are bound with `parallel_tool_calls=True` (`AGENT_PARALLEL_TOOL_CALLS`), the prompts ask for independent lookups in one step, and `ToolNode` runs those calls concurrently. The double binding in `create_tool_llm` (which always pre-bound the calculator) is fixed.

Human-in-the-loop: the new `delete_my_document` tool (`app/tools/delete_document.py`) deletes one of the caller's own private documents, through a non-admin requester taken from the request context. Its registry entry has `describe_approval`, which makes `requires_approval` true. Before any step containing such a call, the `approval` node calls `interrupt()` with the action, document ID, and source; the source is shown only if the caller owns the document. The run pauses, and the response has `status: awaiting_approval`, `run_id`, and `approval`. `POST /api/agent/runs/{run_id}/approval` with `{approved}` resumes it with `Command(resume=...)`; another user's or an unknown run returns 404, and a run with nothing pending returns 409. The decision is stored per tool call in `approvals`, and the tool itself refuses to delete without a recorded approval, so a rejection comes back to the model as "did not approve". Because the interrupt sits in its own node, other calls from the same step run once, after the decision. Chat history is saved only when the run completes. The stream sends `X-Agent-Run-ID` and, if paused, ends with the approval URL.

Multi-agent: `app/agents/supervisor.py` loops a structured supervisor decision (`research`, `analysis`, `coding`, or `finish` plus a task). Each worker is a `build_tool_agent` graph with its own prompt, tools, and message list, and receives its task plus earlier findings. Worker results become `findings`; their sources and tool calls are merged into the run. After `SUPERVISOR_MAX_ROUNDS` (default 4) hand-offs the supervisor is forced to finish (`stop_reason: supervisor_max_rounds`), and one `finalize` LLM call writes the answer. Streaming only forwards tokens from LLM calls tagged `agent:final_answer` (route agents, plain LLM, and finalize), never the classifier, supervisor decisions, or workers.

Persistence: each run is a LangGraph thread (`thread_id = run_id`), checkpointed by `MongoDBSaver` (`langgraph-checkpoint-mongodb`) in the `agent_checkpoints` / `agent_checkpoint_writes` collections, with a TTL (`AGENT_CHECKPOINT_TTL_SECONDS`, default 7 days). The lifespan installs it through `app/agents/checkpoints.py`; if MongoDB is unavailable it logs a warning and uses `InMemorySaver`, so paused runs don't survive a restart. Conversation memory stays in `chat_history`.

**Checklist:**

- [x] Parallel tool execution
- [x] Human-in-the-loop approval for sensitive actions (LangGraph `interrupt`)
- [x] Conditional routing via a classifier (RAG / calculator / plain LLM / other agent)
- [x] Multi-agent system (supervisor with research, coding, analysis agents)
- [x] Agent persistence and checkpoints (LangGraph checkpointer, e.g. MongoDB)

**Done when:** at least one working example of each pattern exists with tests.

**Key files:** `app/agents/` (`orchestrator.py`, `router.py`, `supervisor.py`, `calculator_agent.py`, `checkpoints.py`, `agent_service.py`), `app/tools/delete_document.py`, `app/tools/registry.py`, `app/routes/agent.py`

---



## Phase D: Ship



### 27. Security Hardening

**Status:** Done

**Current state:** JWT auth (`app/security.py`, `app/dependencies.py`) with user roles (`user`/`admin`; admins promoted with `python -m app.scripts.promote_admin`). Knowledge-base writes follow the ownership rules from item 25: any user manages their own private documents, and only admins add shared ones. Agent tools are filtered by role (`app/tools/registry.py`), with strict input schemas, an AST-only calculator, computation limits, timeouts, and malicious-input tests (item 20). The sensitive `delete_my_document` tool needs the user's approval (item 26).

- **Prompt injection:**
  - Every system prompt (agents, classifier, supervisor, workers, finalize, and the plain chat RAG chains) ends with `SECURITY_RULES` (`app/agents/prompts.py`): never reveal the prompt or tool definitions, treat tool results, documents, and pasted content as data, never change role on request, and only call tools for the user's request.
  - `app/guards/injection.py` screens user messages, retrieved chunks, and indexed documents against named patterns (instruction override, prompt reveal, role reassignment, fake role markers, exfiltration). As decided, screening is flag-only: it logs `Possible prompt injection` with the pattern names (never the text) and adds `injection_flags` to the agent run log, but never rejects.
- **Indirect injection:** `search_knowledge_base` results carry an "untrusted content" `notice`, and chunks matching a pattern are marked `suspicious`. The plain chat RAG context wraps each chunk in `<document id="...">` blocks, with any closing tag inside a chunk escaped.
- **Rate limits:** keyed per user when the request has a valid access token, otherwise per IP (`rate_limit_key` in `app/limiter.py`, no DB lookup). Limits are configurable:

  | Routes | Setting | Default |
  | --- | --- | --- |
  | chat | `RATE_LIMIT_CHAT` | 5/minute |
  | agent chat, stream, approval | `RATE_LIMIT_AGENT` | 10/minute |
  | RAG index, upload, search | `RATE_LIMIT_RAG` | 30/minute |
  | register, login, refresh, logout (always per IP) | `RATE_LIMIT_AUTH` | 5/minute |

  Storage is in-memory per process by default (`RATE_LIMIT_STORAGE_URI`); use Redis when running several workers.
- **Request size:**
  - Messages are capped at `CHAT_MAX_MESSAGE_CHARS` (8,000), `max_tokens` at 4,096, search queries at 500 characters, and indexed or extracted text at `RAG_MAX_TEXT_CHARS` (1,000,000). Uploads keep their 5 MB limit.
  - `BodySizeLimitMiddleware` returns 413 for any body over `MAX_REQUEST_BYTES` (6 MB), declared or chunked.
- **Secrets:** `.env` is gitignored and has never been committed. With `APP_ENV=production`, startup fails if `JWT_SECRET_KEY` or `API_KEY` is an `.env.example` placeholder or shorter than 32 characters, or if `DEBUG` is on. Decision: production secrets are injected as environment variables from AWS Secrets Manager or SSM Parameter Store (ECS task-definition `secrets`, wired in item 28); nothing is baked into the image.
- **PII:**
  - Tool arguments are logged with free text replaced by its length (`<redacted len=N>`), keeping only short `expression` and `document_id` values. LangGraph-injected `state` and `tool_call_id` are never logged (`LOG_REDACT_TOOL_ARGS`).
  - A `RedactionFilter` on the JSON log handler masks email addresses and bearer or JWT tokens in messages and extra fields.
  - `chat_history` has a TTL index (`CHAT_HISTORY_RETENTION_DAYS`, default 90; a changed value is applied with `collMod`), and users can erase their own history with `DELETE /api/chat/history`. Agent checkpoints expire after `AGENT_CHECKPOINT_TTL_SECONDS`, and `token_usage` holds counts only.
- **SSRF:** no tool fetches URLs. `app/utils/url_safety.py` provides `validate_outbound_url` for future web tools: https on port 443 only, no credentials, an allowlisted host, and every resolved address must be public (private, loopback, link-local such as `169.254.169.254`, CGNAT, multicast, and IPv4-mapped IPv6 are blocked). Decision: such a tool must validate every redirect hop and connect to a vetted address.
- **Sandboxing:** there is no code-execution tool, and the coding worker only writes text. A test scans `app/` for `eval`, `exec`, `subprocess`, `os.system`, `os.popen`, and `pickle`/`marshal` loads. Decision: any future executor runs outside the API process, in a separate container with no network, as non-root, with a read-only filesystem and CPU, memory, and time limits.
- **CORS:** CORS now also allows `DELETE`, which document and history deletion need.

**Checklist:**

- [x] Prompt injection defenses (system prompt hardening, input screening)
- [x] Indirect prompt injection from RAG documents (treat retrieved text as data, delimit it)
- [x] Malicious tool argument handling
- [x] Tool authorization per user/role
- [x] Rate limits per user (not only per IP)
- [x] Request size limits (message length, upload size)
- [x] Secrets management (no secrets in repo, production secret store)
- [x] PII considerations (logging redaction, retention)
- [x] Unsafe tool execution prevention
- [x] SSRF considerations for future web tools (URL allowlists, block private IPs)
- [x] Sandboxing for any code-execution tools

**Done when:** each item has either an implemented control or a documented decision, with tests for injection and malicious tool inputs.

**Key files:** `app/agents/prompts.py`, `app/guards/injection.py`, `app/limiter.py`, `app/middleware.py`, `app/config.py`, `app/utils/redaction.py`, `app/utils/url_safety.py`, `app/database.py`, `app/schemas.py`, `app/tools/`

### 28. Docker + Deployment

**Status:** In progress

**Current state:** `Dockerfile` builds the API on `python:3.12-slim`, runs as a non-root user, and starts a single Uvicorn process. `compose.yaml` runs `api` and `mongodb` (with a MongoDB health check); Chroma is embedded in the API process and persisted on the `chroma_data` volume, so it needs no separate service. Config comes from `.env` via validated `pydantic-settings` (item 21), and compose overrides `MONGODB_URI` for the container network. `/health` is a liveness check only; the Dockerfile has no `HEALTHCHECK` and compose has none for `api`. On shutdown the lifespan handler closes the agent checkpointer's and the app's MongoDB clients. Both files create and mount a `state` directory that no code uses. Both files are not yet committed, and there is no CI config.

**Checklist:**

- [x] `Dockerfile` for the FastAPI app
- [x] Docker Compose with FastAPI, MongoDB, and Chroma / vector DB
- [ ] Environment variable handling per environment; `APP_ENV` (which enables the production secrets check from item 27), compose `env_file` and overrides exist, no separate dev/prod setup
- [ ] Production server (e.g. Gunicorn with Uvicorn workers)
- [ ] Health checks (liveness and readiness, including DB connectivity); liveness only, no readiness/DB check or compose API health check
- [ ] Graceful shutdown (close DB clients, finish in-flight streams); MongoDB client closed, in-flight streams not handled
- [ ] Production configuration (debug off, CORS, logging level); `DEBUG` and `FRONTEND_URL` env-backed, and `APP_ENV=production` refuses to start with `DEBUG` on; log level hardcoded to `INFO`
- [ ] AWS deployment
- [ ] CI/CD pipeline (tests, lint, build, deploy)

**Done when:** `docker compose up` brings up the full stack locally, and a CI pipeline runs tests and deploys to AWS.

**Key files:** `Dockerfile`, `compose.yaml`, CI config

### 29. Frontend / Production API Usage

**Status:** Not started

**Current state:** backend APIs only; CORS allows the origin in `FRONTEND_URL` (default `http://localhost:5173`).

**Checklist:**

- [ ] React / Next.js chat UI
- [ ] Streaming UI consuming the agent stream endpoint
- [ ] Source citations display
- [ ] Tool status display (e.g. "Searching knowledge base...")
- [ ] Conversation history
- [ ] Authentication (login, token refresh)

**Done when:** a user can log in, chat with the agent with streamed responses, and see sources and tool status.

**Key files:** new frontend project

---



## Phase E: Career



### 30. Interview Preparation

**Status:** Not started

Tick a topic when you can explain it clearly and point to where it is used in this project.

**GenAI**

- [ ] LLM
- [ ] Tokens
- [ ] Embeddings
- [ ] Vector databases
- [ ] RAG
- [ ] Chunking
- [ ] Context window
- [ ] Temperature
- [ ] Hallucination

**LangChain**

- [ ] Runnable
- [ ] LCEL
- [ ] Tools
- [ ] Tool calling
- [ ] Messages
- [ ] Structured output

**LangGraph**

- [ ] State
- [ ] Nodes
- [ ] Edges
- [ ] Conditional edges
- [ ] ToolNode
- [ ] Checkpoints
- [ ] Loops
- [ ] Human-in-the-loop

**Production**

- [ ] Latency
- [ ] Cost
- [ ] Caching
- [ ] Retries
- [ ] Observability
- [ ] Evaluation
- [ ] Security
- [ ] Deployment

**Done when:** every topic is ticked and you can walk through the project architecture end to end.

---



## Known issues

Found in the 2026-10-11 audit. None of these breaks the test suite, but each one weakens the repo for review or deployment.

- [ ] **Uncommitted work:** git has 5 commits, ending at "Reject unsupported RAG answers". Items 19-27, `Dockerfile`, `compose.yaml`, `evals/`, and most tests are untracked or modified. Commit them in reviewable chunks.
- [ ] **`chroma_db/` is tracked:** the Chroma files are still in git and `chroma_db/` is not in `.gitignore`. Add it and run `git rm -r --cached chroma_db`.
- [ ] **README is a stub:** `README.md` has 3 lines. It needs setup, configuration, test markers and commands, eval commands, and an architecture overview.
- [ ] **Dead code:** `app/auth.py` (`verify_api_key`, the old API-key check) is imported nowhere and imports an unused `requests.status_codes`. `manual_llm_test.py` calls the async `generate_ai_response` without awaiting it, so it prints a coroutine. Delete both or turn the script into a working example.
- [ ] **Unused `state` volume:** `Dockerfile` creates `/app/state` and `compose.yaml` mounts `app_state` on it, but no code writes there.
- [ ] **No CI or linter:** no workflow runs `pytest -m "not live"`, and there is no lint or format config (item 28).

---



## Changelog

- 2026-10-06: Roadmap created. Items 1-18 complete; item 19 marked Next.
- 2026-10-09: Progress audit against the code. Item 19: sources collected in-graph via `collect_sources`, post-run parsing removed. Item 20: calculator moved to an AST evaluator. Item 22: unit, integration, routing, tool, RAG, and API tests in place. Item 23: tool-selection and RAG retrieval (Hit Rate@3, MRR@3) evaluation added. Item 25: distance threshold, cross-encoder reranking, rerank score threshold, and answerability gate added. Item 21 marked Next.
- 2026-10-10: Item 25: document deletion endpoint and stale-chunk cleanup on re-index (deletion and update ticked). Item 27 started: user roles, `require_admin` on RAG index/delete, admin promotion script, and role-based route tests. Open issue: `test_delete_stale_chunks_rejects_negative_count` fails because the test expects "Chunk count cannot be negative" while the code raises "keep_chunk_count must be greater than zero".
- 2026-10-11: Phase A complete. Item 19: `tool_calls`, `run_id`, `started_at`, and `stop_reason` in agent state, logged per run. Item 20: calculator computation limits, Pydantic tool input schemas, `{ok, result, error}` tool output, structured errors for unexpected tool crashes, tool timeouts with blocking RAG steps moved off the event loop, role-based tool registry, and malicious-input tool tests. Item 21: `pydantic-settings` config with validated, env-backed agent settings. Item 24 started (agent run ID). Open issue: `tests/test_chat_service.py` is stale (`generate_response` now requires `user_id`; `generate_ai_response` no longer exists in `chat_service`).
- 2026-10-11: Progress audit against the code. Item 22: streaming tests ticked (chunk order in `tests/test_agent_stream_route.py`, no tool-output leak in `tests/test_agent_stream.py`). Item 24: JSON log output ticked (`JsonFormatter` in `app/main.py`); partial progress noted on tool-call logging, request latency, and error context. Item 27: malicious tool arguments, tool authorization per role, and unsafe tool execution prevention ticked (delivered by item 20). Item 28 moved to In progress: `Dockerfile` and `compose.yaml` (API + MongoDB, embedded Chroma on a volume) ticked; partial progress noted on env handling, health checks, graceful shutdown, and production config. Item 29: CORS origin now comes from `FRONTEND_URL`. Open issues: `Dockerfile` and `compose.yaml` are not committed yet; `chroma_db/` is tracked in git and should be gitignored and untracked.
- 2026-10-11: Item 22 Done. MongoDB outages return 503 `DATABASE_UNAVAILABLE` (global `ConnectionFailure` handler, re-raised by the chat and agent routes) with DB-down tests in `tests/test_database_failures.py`. Shared `scripted_llm` fixture in `tests/conftest.py`, now used by the agent tests, plus new `tests/test_agent_routing.py`. `unit`/`integration`/`live` markers registered in `pytest.ini` and applied automatically; paid-API tests marked `live`. Non-live tests are forced into chat mock mode, because four chat/API tests had been calling Groq when `.env` sets `MOCK_MODE=false`. Coverage report via `pytest-cov` (90.2% on `-m "not live"`). Stale tests fixed, which resolves both earlier open issues: `tests/test_chat_service.py` rewritten for the current `generate_response`, the stale-chunk test now expects "keep_chunk_count must be greater than zero" (for -1 and 0), and the reranker-failure test now expects no results, matching the intended behaviour.
- 2026-10-11: Item 23: evaluation dataset and storage format ticked. Agent (5 cases) and RAG (14 cases) evaluation data moved from test code into validated JSONL files under `evals/datasets/`, with a shared loader (`evals/schema.py`) and expectation checker (`evals/checks.py`). The six hand-written agent evaluation tests became one test parametrized over `agent.jsonl` (the two `125 * 4` tests merged into one case); the missing-information case now also requires that no sources are returned. Refusal matching now also recognises "does not have enough information".
- 2026-10-11: Item 23: answer correctness and faithfulness ticked. `evals/judges.py` adds a correctness judge (agent answer vs. a dataset `reference_answer`) and a claim-level faithfulness judge (answer claims vs. retrieved chunk text, threshold 0.9), both with structured output and run by the live agent evaluation after the free rule checks pass. New `numeric` answer rule (the calculator case uses it instead of a substring match). Reference answers added for the three knowledge-base cases. Live run: 5/5 agent cases pass.
- 2026-10-11: Item 23: hallucination detection and relevance ticked. `grounded` rule (no retrieval must mean refusal), faithfulness judge extended to tool results, new `RelevanceJudge`, `JudgeReport`/`summarize()` with hallucination and relevance rates, and 4 new agent cases (text analyzer plus three near-miss negatives). Live run: 7/9 pass, hallucination rate 0.2, relevance rate 1.0, correctness accuracy 1.0. The two failures were real agent hallucinations; fixed by adding grounding and refusal rules to the agent's `SYSTEM_PROMPT`, after which both cases pass (re-run of those two cases only).
- 2026-10-11: Item 23 Done. Eval runner `python -m evals.run` with JSON reports in `evals/reports/` and a printed summary covering tool selection, correctness, faithfulness, hallucination, relevance, retrieval metrics, and per-run latency (mean/p50/p95/max), tokens, and estimated cost (agent and judge usage separate). Token tracking via LangChain's `get_usage_metadata_callback` (captures nested LLM calls), costs from `evals/pricing.py`. Agent runner and retrieval metrics moved into `evals/` and shared with the pytest suites. Smoke run (2 agent cases, 1 RAG case): about 1,260 tokens and $0.0003 per agent run, 3.0 s mean latency.
- 2026-10-11: Item 24: request ID propagation, per-LLM-call logging, and per-tool-call logging ticked. Request ID, run ID, and user ID are carried in context variables (`app/utils/log_context.py`) and added to every log record by a filter on the JSON handler. A process-wide LangChain callback handler (`app/utils/llm_logging.py`) logs each LLM call (model, latency, tokens) and each tool call (name, args, status, latency) as it runs, including LLM calls nested inside tools. The post-run per-tool log in `agent_service.py` was replaced by these live logs plus a name/status summary on the run-completed log. With this, one request can be followed from request ID to run ID to each LLM and tool call.
- 2026-10-11: Item 24: total request latency, token usage aggregation, and error context ticked; only the tracing solution remains. Every request logs `Request completed` after its body finishes streaming, with route template, status, duration, and the request's LLM calls and tokens. Per-user daily token totals are stored in MongoDB (`token_usage`, upserted with `$inc`) and exposed at `GET /api/usage/me`. Agent failures record the failing step (graph node, or history load/save), and API error logs include run ID and step. New tests: `tests/test_request_observability.py` (15). Offline suite: 338 passed.
- 2026-10-11: Item 25: ingestion pipeline and metadata filtering ticked. New `POST /api/rag/upload` for `.txt`, `.md`, and `.pdf`, with a load and clean stage (`app/services/ingestion_service.py`) ahead of chunk, embed, and store. Chunks now carry source, document type, visibility, and owner. Search covers shared documents plus the caller's own private ones and can filter by source and type. Indexing and deletion moved from admin-only to ownership rules: users manage their own private documents, only admins add shared ones. Older chunks are backfilled as shared on startup. Fixed the empty-chunk branch of `index_document`, which called a non-existent `delete_document` on the vector store. New dependencies: `pypdf`, `python-multipart`. New tests: `tests/test_document_ingestion.py` (run against a temporary Chroma collection with fake embeddings). Offline suite: 370 passed.
- 2026-10-11: Item 25 Done. Chunking, hybrid search, duplicate handling, and embedding versioning ticked; only the optional vector-store migration remains. Markdown is chunked along its headings, with the heading path on each chunk. Chunk size and overlap are configurable (800/100), and a sweep (`python -m evals.chunking`, embedding calls only) found sizes of 500 to 1200 all perfect on the new chunking corpus, with 300 slightly worse. BM25 keyword search is fused with vector search by reciprocal rank fusion. Content and chunk hashes skip unchanged re-indexing, reject duplicates with 409, and reuse stored embeddings. Each embedding model has its own collection, filled by `python -m app.scripts.reembed`; the existing chunks were copied into `documents-gemini-embedding-001` for free. Live RAG eval with hybrid search on: 14/14, false-positive rate 0. New tests: `test_chunking.py`, `test_hybrid_search.py`, `test_duplicate_handling.py`, `test_embedding_versioning.py`, `test_chunking_eval.py`. Offline suite: 406 passed.
- 2026-10-11: Item 26 Done. The agent endpoints now run an orchestrator: an LLM classifier routes each message to a RAG agent, a calculator agent, a plain LLM, a supervisor with research, analysis, and coding workers, or the general tool agent (the fallback). All agents share one tool-agent builder. Tool calls in a step run in parallel (`parallel_tool_calls`). The new `delete_my_document` tool pauses the run with LangGraph `interrupt` until `POST /api/agent/runs/{run_id}/approval`. Runs are checkpointed in MongoDB (`thread_id = run_id`, TTL), so paused runs can be resumed by a new process. Agent responses gain `run_id`, `route`, `status`, and `approval` (new `AgentChatResponse`; plain `/chat` is unchanged). New settings: `AGENT_PARALLEL_TOOL_CALLS`, `AGENT_ROUTING_ENABLED`, `SUPERVISOR_MAX_ROUNDS`, `AGENT_CHECKPOINT_TTL_SECONDS`. New dependency: `langgraph-checkpoint-mongodb` (plus its requirements). New tests: `test_parallel_tools.py`, `test_agent_approval.py`, `test_agent_router.py`, `test_supervisor.py`, `test_agent_checkpoints.py`. Live: the classifier routed 5/5 sample messages correctly, and `tests/test_agent_logging.py` passes through the orchestrator. Offline suite: 444 passed.
- 2026-10-11: Item 27 Done. Every system prompt (agents, router, supervisor, plain chat) ends with shared security rules (`app/agents/prompts.py`). User messages, retrieved chunks, and newly indexed documents are screened for prompt-injection patterns (`app/guards/injection.py`); matches are logged with flag names only and never rejected, and agent runs log `injection_flags`. The RAG tool output carries an untrusted-content notice and marks flagged chunks `suspicious`; chat context wraps each chunk in an escaped `<document>` block. Rate limits are keyed per user (JWT `sub`, falling back to IP), configurable, and applied to chat, agent, RAG, and auth (auth is per IP). Requests over `MAX_REQUEST_BYTES` get 413 from a new body-size middleware, and messages, tokens, indexed text, uploads, and search queries have length caps. `APP_ENV=production` refuses placeholder or short secrets. Logs redact emails, bearer tokens, and JWTs, and tool arguments other than `expression` and `document_id` are logged as lengths only. `chat_history` has a TTL index (`CHAT_HISTORY_RETENTION_DAYS`), and `DELETE /api/chat/history` clears the caller's history (CORS now allows DELETE). An outbound URL guard (`app/utils/url_safety.py`) is ready for future fetch tools. Decision: no code-execution tool, which a scan test enforces. New settings: `MAX_REQUEST_BYTES`, `CHAT_MAX_MESSAGE_CHARS`, `RAG_MAX_TEXT_CHARS`, `RATE_LIMIT_ENABLED`, `RATE_LIMIT_STORAGE_URI`, `RATE_LIMIT_CHAT`, `RATE_LIMIT_AGENT`, `RATE_LIMIT_RAG`, `RATE_LIMIT_AUTH`, `CHAT_HISTORY_RETENTION_DAYS`, `LOG_REDACT_TOOL_ARGS`. New tests: `test_prompt_injection.py`, `test_rate_limits.py`, `test_request_limits.py`, `test_secrets_config.py`, `test_pii.py`, `test_url_safety.py`, `test_no_code_execution.py`, plus live `test_prompt_injection_live.py`. Live: 3/3 injection cases held (no prompt leak, override canary ignored, poisoned document ignored). Offline suite: 539 passed.
- 2026-10-11: Progress audit against the code. Statuses for items 19-30 match the code; no checkbox changed. Updated stale text: the header's completed list, item 20's tool list (`delete_document`), item 22's test count (72 files) and README note, and item 28's notes on health checks, shutdown, `APP_ENV`, and the unused `state` volume. New [Known issues](#known-issues) section: uncommitted work, tracked `chroma_db/`, README stub, dead `app/auth.py` and `manual_llm_test.py`, unused `state` volume, and no CI or linter.

