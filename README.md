## [Note : The content and language was fine tuned but was written by myself]

# What you built. 5-line architecture summary

- A FastAPI backend system (skeleton initially generated using prompts from Promts_Used/v0_rough_design.md). Out of all the endpoints, the two most important are /sync and /chat/rto.

- The /sync endpoint extracts data from three connectors — Razorpay, Shiprocket, and Shopify — to generate normalized tables, entity mapping tables, and provenance tables, which are later used for citations during query responses.

- The /chat/rto endpoint takes a user query, and the internal LLM agent processes it. Currently, it uses a hardcoded loop of 3 iterations to imitate a true agent-loop scenario while avoiding context overflows. The LLM call is passed a prompt and tools from a filtered list, currently selected using simple parsing logic to minimize context pollution (observed worse results when passing all tools together). The selected tool is then called, which deterministically fetches data from normalized tables along with citations for those rows from the provenance table (Ref_eg: /Users/tusharmacmini/Documents/Projects/AI-Helper/artifacts/citation_example_rto_query.md).

- If the LLM chooses a specific iteration as the final answer, validation verifies the existence of citations; otherwise, it returns a general response stating that no deterministic answer from the data was used.

- The current DB setup uses local SQLite for easier setup, since local PostgreSQL was slowing down my PC while running local LLMs in parallel. Swagger UI (prepackaged with FastAPI) was used for API testing.

# Connectors. Which 3. Why these 3.

The current system uses 3 connectors — Shopify, Shiprocket, and Razorpay.

Shopify is used as the primary ecommerce/order source, Shiprocket is used for shipment and delivery related data, and Razorpay is used for payment related information. These 3 were selected because together they cover most of the important flows required for ecommerce analytics and RTO related reasoning — orders, payments, shipping, delivery status, and returns.

Another reason for choosing these was that all 3 provide relatively clean APIs and are commonly used together in many Indian ecommerce setups, making them good connectors for testing cross-platform normalization, entity mapping, and provenance tracking scenarios.


# Schema. Why this shape

- The schema was intentionally kept small and normalized around the core ecommerce flow — orders, shipments, and payments — since most analytics and RTO related queries can be derived from these entities.

- orders, shipments, and payments tables act as canonical normalized tables generated from connector data. Instead of directly querying connector-specific schemas, all tools operate on these normalized entities to keep deterministic tool logic simpler and connector independent.

- The entity_mappings table was added to solve cross-platform identity resolution. Different systems use different IDs for the same logical entity, so this table maps external connector IDs to stable internal IDs used across the system.

- The provenance table was added mainly for lineage and citations. Since the system is designed around grounded responses, every important normalized field can be traced back to the original source system, source field, and row id. These provenance rows are later converted into citations during chat responses.

- Pydantic schemas were kept separate from SQLAlchemy models so API responses remain validated and decoupled from ORM objects. The tool execution and chat response schemas were also designed to enforce structured deterministic outputs with citations, instead of allowing free-form LLM generated responses.

# Chat. The tool schema you exposed. How citation works.

The chat system currently works as a bounded agent loop where the LLM decides whether to call a deterministic tool or stop with a final answer. Instead of exposing raw DB access, only structured tool schemas are exposed to the LLM using Pydantic models like ToolCall, AgentAction, and ToolExecutionResult.

The exposed tool schema mainly contains:

* tool name
* validated arguments
* structured deterministic output
* optional filters/calculation metadata
* records used
* citations

The reason for keeping tool outputs structured instead of natural language was to reduce hallucinations and make validation easier before generating the final response.

Citations work through the provenance table. During /sync, whenever normalized fields are populated from connector data, provenance rows are also written containing:

* internal entity id
* source system
* source field
* source row id
* synced timestamp

Later during tool execution, after deterministic data is fetched from normalized tables, the related provenance rows are queried using functions like latest_provenance_for_entities(). These provenance rows are then converted into citation objects and attached to the tool result.

During the final validation step, if the LLM selects a deterministic tool result as the final answer, the system verifies that citations exist for the claims/data used. If citations are missing, it falls back to a general ungrounded response instead of pretending the answer came from deterministic data.

# Agent. What it does. Why this one.

- What is does
Right now the agent uses a bounded hardcoded loop of 3 iterations to imitate a true agent-loop workflow while avoiding large context growth and unstable reasoning behaviour from local LLMs. In each step, the LLM receives the user query, previous tool outputs, available filtered tools, and the current loop context, after which it decides whether to call another tool, continue reasoning using existing outputs, or stop and generate the final answer.

- Why this one
The reason for using this approach instead of a single-shot prompt was that multi-step queries performed better when the model could iteratively reason over smaller structured outputs. At the same time, exposing all tools together caused noticeable context pollution and worse tool selection, so a filtered tool exposure strategy was added.It keeps most computation deterministic while still allowing flexible query handling from the LLM side

# Scale. How this goes from 1 merchant to 10,000. What breaks. What you've built to absorb it.

- Right now the system is designed more as a strong v0 architecture with clear scaling boundaries already identified instead of trying to prematurely optimize everything from day 1. The current setup can handle roughly ~100 merchants and ~100 calls/min on local SQLite with a single FastAPI instance, but the main scaling bottlenecks identified were database concurrency, provenance table explosion, synchronous sync workflows, missing cache layers, and lack of merchant isolation.

- The first thing that breaks while scaling towards 10,000 merchants is SQLite itself since it allows only limited concurrent writes and no proper connection pooling or read replicas. To absorb this, the planned migration is towards RDS PostgreSQL with Multi-AZ setup, read replicas, and PgBouncer/RDS Proxy for connection pooling.

- Another major bottleneck identified was provenance growth. Since provenance is written at field level, repeated syncs can generate billions of rows over time. To handle this, provenance partitioning by merchant and date was planned so queries only scan relevant partitions instead of full table scans.

- The second large issue was repeated expensive queries and Bedrock token costs. To reduce this, Redis/ElastiCache was introduced as a caching layer with TTL-based cache invalidation triggered after sync completion events.

- The current /sync endpoint is synchronous, which becomes problematic at scale since connector fetches block API responsiveness. The scaling design moves sync processing into async SQS + Lambda workers so API requests return immediately while sync jobs execute independently in the background.

- Merchant isolation was another important scaling and security concern. The future architecture adds merchant_id scoped partitioning and row-level security (RLS) policies so queries automatically stay tenant isolated.

- At infra level, scaling is handled using AWS Fargate auto-scaling, Redis clusters, RDS replicas, Lambda workers, and CloudWatch based monitoring/alerts. The idea was to keep deterministic tool execution and normalized schemas unchanged while horizontally scaling infrastructure components around them instead of redesigning the entire architecture later.

# Eval. Where it breaks

- A big input from connectors will overload the local sqlite tables

- The timeout for local llm call is currently set to 120 seconds which in some queries was timing out along with the parsing logic to pass tools currently focuses on keyword not sematic which missed imp tools during llm call.

- [Future_Plan]The architecture already stores structured traces (AgentStepLog, ToolExecutionResult, provenance citations), which makes future eval systems easier to build without redesigning the whole pipeline later

# Hours spent. Across how many days or sessions

- Around 12 hours across 5 session which had 2 session of 4 hours[weekends] and 2 of about 2 hours.

# What you'd do with another week.

- With another week, I would mainly focus on improving reliability and evaluation instead of adding more features. Right now the core architecture works end-to-end, but the biggest gaps are around production stability, eval quality, and scaling readiness.

- The first thing I would improve is the eval pipeline by creating a proper golden dataset for tool routing, citation validation, and multi-step agent reasoning. Currently validation is mostly heuristic based, so adding replayable agent traces and automated scoring would make debugging and benchmarking much easier.

- I would also replace the current simple filtered-tool parsing logic with embedding or retrieval-based tool selection since context pollution becomes worse as tool count increases.

- On the infra side, I would start migrating from SQLite towards PostgreSQL and begin implementing provenance partitioning because provenance growth becomes one of the biggest long-term bottlenecks in this architecture.

- Another thing I would improve is observability. Right now traces exist structurally through run logs and tool outputs, but I would integrate something like Langfuse/OpenTelemetry to visualize complete agent execution paths, tool calls, retries, and latency.

- Finally, I would improve sync performance by moving connector sync fully async using queues/workers instead of synchronous execution, since that becomes important very quickly once merchant count starts increasing.