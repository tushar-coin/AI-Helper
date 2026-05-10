You are a senior AI systems engineer. Evolve (do not rewrite) this existing FastAPI + SQLite D2C assistant into a grounded conversational analytics system.

Constraints:
- Incremental changes only; preserve current architecture and endpoints.
- Keep `GET /chat/rto?question=...` (do not remove).
- LLM is router/narrator only; tools are source of truth.
- No LangChain/LangGraph/CrewAI/AutoGen.
- No uncited numeric claims.

Current codebase already has FastAPI, SQLAlchemy models, normalized tables, provenance, mappings, deterministic tools, and an RTO agent.

Implement:
1) `chat/tool_registry.py`  
   - register deterministic tools: total revenue, average daily revenue, rto orders, failed shipments, order by id  
   - include descriptions + argument schema

2) Refactor `chat/tools.py`  
   - deterministic structured outputs (metric, value, calculation, citations, records)  
   - keep backward compatibility with existing `ChatAnswer` wrappers

3) `chat/llm_router.py` using local Ollama (`qwen3.5`)  
   - strict JSON output only: `{"tool_name": "...", "arguments": {...}}`  
   - constrained system prompt  
   - safe fallback when model is unavailable

4) `chat/tool_executor.py`  
   - validate tool name + args against registry  
   - execute deterministic function

5) `chat/validator.py`  
   - verify numeric claims are backed by tool output + citations  
   - reject hallucinated/unsupported numbers

6) `chat/summarizer.py`  
   - summarize only from validated tool outputs

7) Evolve `GET /chat/rto` flow  
   question -> router -> executor -> validator -> summarizer -> response

8) Add `POST /chat/query`  
   request: `{"question":"..."}`  
   response: `{question, tool_used, answer, structured_data, citations}`

9) Refactor `agents/rto_agent.py` to consume deterministic tools + citations.

Acceptance:
- Existing endpoints still work.
- `/chat/rto` and `/chat/query` are grounded and citation-aware.
- LLM never computes business metrics.
- All numeric claims are tool-backed.
