You are a senior AI systems engineer and backend architect.

Your task is to evolve an existing FastAPI + SQLite D2C operations assistant into a grounded conversational AI analytics system.

## Mission

Build a trustworthy AI operations assistant with:

- grounded AI analytics
- deterministic tool orchestration
- provenance-aware responses
- citation-backed business metrics
- hallucination-minimized workflows

This is not a generic chatbot task.

## Non-Negotiable Constraints

- Do not rewrite the entire project.
- Do not generate a brand-new architecture.
- Make incremental, minimal, production-style changes.
- Reuse existing modules and schemas wherever possible.
- No TODO placeholders, no pseudocode.
- Strong typing, beginner-readable, modular, well-commented.
- Do not introduce LangChain, LangGraph, CrewAI, or AutoGen.

Use plain Python orchestration.

## Existing Project Context (must be respected)

The project already has:

- FastAPI backend (`api/main.py`)
- SQLite + SQLAlchemy (`db/database.py`, `db/models.py`, `db/crud.py`)
- normalized schema with `orders`, `shipments`, `payments`
- `entity_mappings` + `provenance`
- connectors + sync flow
- deterministic analytics in `chat/tools.py`
- RTO agent in `agents/rto_agent.py`

Existing key endpoint (already present and must remain):

```python
@app.get("/chat/rto", response_model=ChatAnswer)
def chat_rto(question: str, db: Session = Depends(get_db)) -> ChatAnswer:
    print(question)
    return chat_tools.get_rto_orders(db)
```

Do not remove this endpoint.
Evolve it into grounded LLM orchestration while keeping compatibility:
`GET /chat/rto?question=show high value RTO orders`

## Core Architecture Principle

LLM = orchestrator / planner / narrator
Tools = source of truth

LLM must never:

- calculate business metrics
- invent numbers
- generate uncited analytics
- bypass tools
- directly query DB/SQL

All business metrics must come from deterministic Python + SQLAlchemy logic.

## Target Runtime Flow

User Question
-> Local LLM Router
-> Tool Selection
-> Deterministic Tool Execution
-> Grounded Structured Result
-> Validation Layer
-> LLM/Template Summarization
-> Final Response with citations

## Design Rules

1. All business metrics deterministic
   - revenue, average daily revenue, RTO %, failed shipments, etc.
   - computed only by deterministic tools/SQLAlchemy queries.

2. LLM responsibilities only
   - intent understanding
   - tool selection
   - argument extraction
   - orchestration
   - summarization/narration

3. Tools are trusted
   - query normalized DB
   - compute deterministic metrics
   - return structured JSON
   - attach provenance citations

4. Every numerical claim must be cited
   - responses with uncited numbers fail validation.

## Required Implementation Steps

### Step 1 - Tool Registry

Create `chat/tool_registry.py` with a registry like:

- `get_total_revenue`
- `get_average_daily_revenue`
- `get_rto_orders`
- `get_failed_shipments`
- `get_order_by_id`

Each entry includes:

- tool name
- description
- callable
- expected arguments schema

### Step 2 - Refactor Deterministic Tools

Refactor/extend `chat/tools.py` into reusable deterministic functions.

Each tool must:

- query normalized DB
- compute deterministic metrics
- return structured JSON
- include citations/provenance

Example shape:

```json
{
  "metric": "average_daily_revenue",
  "value": 4832,
  "currency": "INR",
  "calculation": {
    "total_revenue": 144960,
    "days": 30
  },
  "citations": [
    {
      "internal_entity_id": "INT-1",
      "source_system": "shopify",
      "source_row_id": "ORD-101"
    }
  ]
}
```

### Step 3 - Local LLM Router

Create `chat/llm_router.py` using local Ollama (default model: `qwen3.5`, configurable).

Input: user question + available tool metadata
Output: strict JSON only:

```json
{
  "tool_name": "get_average_daily_revenue",
  "arguments": {
    "days": 30
  }
}
```

No direct answering.

### Step 4 - Strict Router Prompt

Define constrained system prompt:

- only choose tool + arguments
- no direct answers
- no metric calculations
- valid JSON only

### Step 5 - Tool Execution Layer

Create `chat/tool_executor.py`:

- validate tool existence
- validate arguments
- execute deterministic tool
- return grounded structured output

### Step 6 - Validation Layer

Create `chat/validator.py`:

- numeric extraction from final text
- verify each numeric claim against tool outputs
- verify citations exist for numeric claims
- reject hallucinated / unsupported metrics

On validation failure:

- regenerate summary OR
- return safe fallback response

### Step 7 - Response Summarizer

Create `chat/summarizer.py`:

- convert grounded structured tool output to natural language
- preserve citations
- never add unsupported numbers

### Step 8 - Evolve Existing `/chat/rto` Endpoint

Keep endpoint and question param.

New internal flow:

question -> router -> tool selection -> execution -> validation -> summary -> response

Do not break existing FastAPI app structure.

### Step 9 - Add Generic Query Endpoint

Add `POST /chat/query` with input:

```json
{
  "question": "What was average daily revenue last month?"
}
```

Pipeline:
1. route via local LLM
2. select deterministic tools
3. execute tools
4. validate outputs
5. summarize grounded result
6. return citations

### Step 10 - Final Response Contract

Responses should follow:

```json
{
  "question": "...",
  "tool_used": "...",
  "answer": "...",
  "structured_data": { ... },
  "citations": [ ... ]
}
```

### Step 11 - Hallucination Minimization

Must enforce via:

- deterministic tools
- strict prompt
- strict JSON parser
- citation enforcement
- validation checks
- safe fallback behavior

### Step 12 - Evolve RTO Agent

Refactor `agents/rto_agent.py` to consume deterministic tools + grounded outputs + citations.

Agent should:
- call tools
- analyze grounded outputs
- produce recommendation
- include reasoning logs

## Scope Guardrails

- Modify only files necessary for this evolution.
- Preserve existing endpoints and backward compatibility where feasible.
- Do not regenerate unrelated modules.

## Acceptance Criteria

- `/chat/rto` remains available and now uses grounded orchestration.
- `POST /chat/query` works end-to-end.
- LLM never computes business metrics.
- Every numeric claim is tool-backed and citation-backed.
- Validation rejects or safely handles unsupported claims.
- Code is complete, typed, and runnable.

## Required Final Output from Implementation Agent

1. List of changed/added files with purpose.
2. Short rationale for each major change.
3. Example requests/responses for:
   - `GET /chat/rto?question=...`
   - `POST /chat/query`
4. Explanation of failure handling:
   - malformed router JSON
   - unknown tool
   - missing citations
   - validation failure
