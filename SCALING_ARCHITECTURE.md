# AI-Helper: AWS Scaling Architecture (v0 → 10k Merchants)

**Date:** 17 May 2026  
**Status:** Production Planning  
**Target:** 10,000 merchants, 10,000 calls/min

---

## Part 1: Current State (v0)

### What We Have Today

```
Local Development:
┌─────────────────┐
│   FastAPI App   │
│  (1 Fargate)    │
├─────────────────┤
│  SQLite DB      │
│  (Single file)  │
├─────────────────┤
│ Connectors:     │
│ - Shopify       │
│ - Shiprocket    │
│ - Razorpay      │
└─────────────────┘
```

**Current Capabilities:**
- ✅ 3 connectors (mocked data)
- ✅ Normalized schema (orders, shipments, payments)
- ✅ Provenance tracking (field-level lineage)
- ✅ Chat tools with citations (19 tools)
- ✅ RTO agent (autonomous monitoring)
- ✅ Local Ollama integration (qwen2.5-coder)

**Current Limits:**
- ❌ SQLite (single writer, no concurrency)
- ❌ No cache layer (every query hits DB)
- ❌ Synchronous sync (blocks API)
- ❌ No multi-region support
- ❌ No provenance partitioning
- ❌ Local LLM (qwen3.5) unreliable → switched to qwen2.5-coder
- ❌ Single Fargate task (no autoscaling)

**Performance Baseline:**
- Handles: ~100 merchants, ~100 calls/min
- Response time: 200-500ms
- Database size: ~50MB (test data)

---

## Part 2: Critical Gaps Analysis

### Gap 1: Database Bottleneck (CRITICAL)

**Current Problem:**
```
SQLite:
- Single writer lock
- No connection pooling
- No read replicas
- Full-table scans kill performance

At 10k calls/min:
- Connection queue immediately fills
- Queries timeout after 30s
- Transactions fail with lock timeout
```

**Impact:** System becomes completely unavailable above 500 calls/min

**Solution: RDS PostgreSQL**
```yaml
Primary Instance:
  Type: db.r6i.xlarge (4 vCPU, 32GB RAM)
  Storage: 1TB SSD (auto-expand)
  Multi-AZ: Yes (automatic failover)
  Backup: Automated daily + point-in-time recovery

Read Replicas:
  Replica 1: db.r6i.large (analytics queries)
  Replica 2: db.t3.xlarge (backup/failover)

Connection Pooling:
  PgBouncer or RDS Proxy
  - Min pool: 10 connections
  - Max pool: 100 connections
  - Timeout: 30s idle

Performance:
  - Supports 1000+ concurrent connections
  - 10k calls/min = ~166 req/sec
  - Each query: ~100ms average
  - Replicas absorb 80% of read load
```

---

### Gap 2: Provenance Explosion (CRITICAL)

**Current Problem:**
```
Example: 10k merchants × 100 orders/merchant × 5 provenance rows per order
= 5M provenance rows

Repeating syncs every hour:
- 5M rows × 365 days × 24 hours = 43.8B rows!
- Single table scan: 10+ seconds
- Storage: 1TB+ in 6 months

Current schema:
  CREATE TABLE provenance (
    id PRIMARY KEY,
    internal_entity_id,  -- NOT INDEXED FOR MERCHANT
    source_system,
    source_row_id,
    synced_at
  );
  
Query performance:
  SELECT * FROM provenance WHERE internal_entity_id = 'INT-ORD-123'
  → Full table scan (millions of rows)
```

**Impact:** Analytics queries timeout, sync performance degrades

**Solution: Partitioning by Merchant + Date**
```sql
-- Create partitioned table
CREATE TABLE provenance (
    id BIGSERIAL,
    merchant_id VARCHAR(50),
    internal_entity_id VARCHAR(50),
    source_system VARCHAR(20),
    source_field VARCHAR(100),
    source_row_id VARCHAR(100),
    field_name VARCHAR(100),
    synced_at TIMESTAMP,
    PRIMARY KEY (merchant_id, internal_entity_id, synced_at)
) PARTITION BY RANGE (merchant_id, DATE_TRUNC('month', synced_at));

-- Auto-create partitions
-- partition_provenance_2024_05_merchant_0001 to merchant_9999 (10k merchants)
-- partition_provenance_2024_06_merchant_0001 to merchant_9999
-- ... monthly partitions

-- Index on each partition (local indexes)
CREATE INDEX idx_provenance_entity ON provenance (internal_entity_id, synced_at);

-- Query performance after partitioning
SELECT * FROM provenance WHERE merchant_id = '0042' AND internal_entity_id = 'INT-ORD-123'
→ Scans only 1 partition (June 2024, merchant 0042)
→ 50,000 rows instead of 5B rows
→ Query time: 2ms (vs 10s before)
```

**Retention & Archival:**
```
Hot (RDS): 90 days
  - Fast query performance
  - Full index support

Warm (S3): 1 year
  - Athena queries (cheap)
  - Compliance audit trail
  - Cost: ~$0.02 per GB/month

Archive (S3 Glacier): 7 years
  - Regulatory retention
  - Cost: ~$0.004 per GB/month
```

---

### Gap 3: Missing Cache Layer (EXPENSIVE)

**Current Problem:**
```
Same question asked 100 times:
  Query 1: "Show RTO orders" → Hit DB → 2ms → Bedrock (2K tokens)
  Query 2: "Show RTO orders" → Hit DB → 2ms → Bedrock (2K tokens)
  ... 100 times
  
Total: 100 queries × 2K tokens = 200K tokens wasted
Cost: 200K tokens × $5/1M = $0.001 per repeated query
× 10k merchants × 100 queries/day = $1/day = $30/month waste
```

**Impact:** 60% of Bedrock costs are preventable cache misses

**Solution: ElastiCache Redis**
```yaml
Cache Layer:
  Engine: Redis 7.x
  Node Type: cache.r6g.xlarge (26GB)
  Cluster: 3 nodes (300GB total, $5/node/day costs)
  Multi-AZ: Yes
  Auto-failover: Yes

Cache Strategy by Tool:

1. get_rto_orders:
   Key: "merchant:0042:rto_orders"
   TTL: 15 minutes (data freshness important)
   Size: ~1KB
   Cache invalidation: On sync_complete event

2. get_revenue:
   Key: "merchant:0042:revenue"
   TTL: 1 hour (less frequent change)
   Size: ~500B
   Cache invalidation: On order update

3. entity_mappings (expensive queries):
   Key: "merchant:0042:mappings"
   TTL: 24 hours (rarely changes)
   Size: ~10KB per merchant
   Warming: Preload on merchant onboard

4. Chat tool descriptions:
   Key: "tools:descriptions"
   TTL: 1 week
   Size: ~10KB
   Warming: Load at app startup

Expected Hit Ratio:
  - Cold start (first query): 0% hits
  - Day 1: 30% hits
  - Week 1: 60% hits (steady state)
  
With 60% cache hit rate:
  - 10k calls/min × 60% = 6k from cache (0 Bedrock tokens)
  - 10k calls/min × 40% = 4k to Bedrock (8M tokens/min)
  - Monthly savings: 60% of Bedrock cost = ~$1,038/month
```

---

### Gap 4: Synchronous Sync Blocks API (PERFORMANCE)

**Current Problem:**
```
POST /sync endpoint:
  1. Fetch from Shopify (5s)
  2. Fetch from Shiprocket (3s)
  3. Fetch from Razorpay (2s)
  4. Normalize (2s)
  5. Upsert to DB (3s)
  Total: 15 seconds blocking

During sync:
- API /chat endpoints hang (connection pool blocked)
- Users see timeouts
- 10k merchants × 1 sync/hour = 166 syncs/hour (10k calls/min just for sync!)
```

**Impact:** Unpredictable latency spikes, poor user experience

**Solution: Async Queue (SQS + Lambda)**
```yaml
Architecture:

POST /sync → Fargate:
  1. Validate merchant_id
  2. Enqueue message to SQS (async)
  3. Return 202 Accepted (immediate)
  4. User checks /sync/status/{job_id}

SQS Queue:
  Name: connector-sync-queue
  Message retention: 14 days
  Visibility timeout: 15 minutes
  DeadLetter queue: Yes (retries)
  Throughput: 300 messages/min (10k merchants, 1 sync/hour)

Lambda Workers (Auto-scaling):
  Runtime: Python 3.11
  Memory: 1GB
  Timeout: 10 minutes
  Concurrency: 20 (parallel workers)
  
  Process:
    1. Dequeue message from SQS
    2. Fetch from all 3 connectors (parallel)
    3. Normalize and deduplicate
    4. Upsert to RDS (batch)
    5. Publish "sync.complete" event to EventBridge
    6. Invalidate cache: Redis DEL merchant:XXXX:*
  
  Execution time:
    - Fetch connectors: 3s (parallel)
    - Normalize: 2s
    - Database upsert: 3s
    - Total: 8s per sync
    
  Cost:
    - 10k merchants × 24 syncs/day = 240k invocations
    - Each: 8s × 1GB = 64 GB-s
    - Total: 240k × 64 = 15.36M GB-s
    - Cost: 15.36M GB-s × $0.0000166667 = $0.256/month

User Experience:
  - POST /sync returns in <100ms
  - Sync runs in background
  - /sync/status/{job_id} shows progress
  - Chat endpoints remain responsive
```

---

### Gap 5: No Merchant Isolation (SECURITY)

**Current Problem:**
```
Shared database, no tenant boundaries:
  - Merchant A can query another merchant's data
  - No access control at DB level
  - Compliance violation (PCI, security audit failure)

Current query:
  SELECT * FROM orders WHERE created_at > '2024-01-01'
  → Returns ALL merchants' orders (security hole)
```

**Impact:** Data leakage risk, regulatory non-compliance

**Solution: Row-Level Security (RLS)**
```sql
-- Add merchant_id to all tables
ALTER TABLE orders ADD COLUMN merchant_id VARCHAR(50);
ALTER TABLE shipments ADD COLUMN merchant_id VARCHAR(50);
ALTER TABLE payments ADD COLUMN merchant_id VARCHAR(50);

-- Create RLS policy
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY orders_merchant_isolation ON orders
  AS PERMISSIVE FOR ALL
  USING (merchant_id = current_setting('app.current_merchant'));

-- In FastAPI middleware:
def set_merchant_context(merchant_id: str):
    db.execute(f"SET app.current_merchant = '{merchant_id}'")

-- Query now automatically scoped:
SELECT * FROM orders  -- Only returns current merchant's orders
→ WHERE merchant_id = current_setting('app.current_merchant')
```

---

## Part 3: Filling the Gaps

### Remediation Roadmap

#### Phase 1: Database Migration (Week 1-2)
```bash
# 1. Spin up RDS PostgreSQL
aws rds create-db-instance \
  --db-instance-identifier ai-helper-prod \
  --db-instance-class db.r6i.xlarge \
  --engine postgres \
  --master-username postgres \
  --allocated-storage 1000 \
  --multi-az

# 2. Migrate schema
python scripts/migrate_sqlite_to_postgres.py

# 3. Migrate data
python scripts/sync_historical_data.py

# 4. Update connection string in FastAPI
# .env: DATABASE_URL=postgresql://user:pass@ai-helper-prod.xxxxx.rds.amazonaws.com/db

# 5. Deploy and validate
git push → CI/CD → Fargate deployment
```

#### Phase 2: Provenance Partitioning (Week 2-3)
```bash
# 1. Create partitioned table structure
python scripts/create_partitions.py

# 2. Migrate existing provenance data
python scripts/backfill_provenance_partitions.py

# 3. Update CRUD operations to use partition key
git diff db/crud.py  # Now includes merchant_id on all provenance queries

# 4. Monitor partition sizes
SELECT partition_name, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables WHERE tablename LIKE 'provenance_%'
```

#### Phase 3: ElastiCache Implementation (Week 3)
```bash
# 1. Create Redis cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id ai-helper-cache \
  --cache-node-type cache.r6g.xlarge \
  --engine redis \
  --num-cache-nodes 3 \
  --multi-az-enabled

# 2. Update connection in FastAPI
pip install redis
# .env: REDIS_URL=redis://ai-helper-cache.xxxxx.ng.0001.use1.cache.amazonaws.com:6379

# 3. Implement cache decorator
@cache_result(ttl_minutes=15)
def get_rto_orders(merchant_id, db):
    ...

# 4. Test hit ratio
python scripts/cache_stats.py → Monitor hits/misses

# Expected result: 60% cache hit rate
```

#### Phase 4: Async Sync (Week 4)
```bash
# 1. Create SQS queue
aws sqs create-queue --queue-name connector-sync-queue

# 2. Convert /sync to async
# FastAPI: POST /sync now enqueues and returns 202

# 3. Deploy Lambda workers
# Deploy Lambda function with RDS access (VPC)
# Auto-scale: Min 1, Max 20 concurrent

# 4. Add event publishing
# On sync completion: EventBridge → SNS → /chat invalidate cache

# 5. Add status endpoint
GET /sync/status/{job_id} → Returns progress
```

#### Phase 5: Merchant Isolation (Week 5)
```bash
# 1. Add merchant_id column to all tables
python scripts/add_merchant_id_column.py

# 2. Implement RLS
python scripts/enable_row_level_security.py

# 3. Update FastAPI middleware
# All requests now set: app.current_merchant = request.headers['X-Merchant-ID']

# 4. Validate isolation
pytest tests/test_merchant_isolation.py
```

---

## Part 4: AWS Production Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         AWS Production Setup                              │
└──────────────────────────────────────────────────────────────────────────┘

                              EXTERNAL TRAFFIC
                                    ↓
                    ┌───────────────────────────────┐
                    │   ALB (Application LB)        │
                    │   HTTPS, SSL termination      │
                    │   Target: Fargate tasks       │
                    └───────────────────────────────┘
                                    ↓
                    ┌───────────────────────────────────────────────────┐
                    │      Fargate Cluster (ECS)                        │
                    │  Auto-scaling 3-50 tasks                          │
                    │  ┌──────────────────────────────────────────────┐ │
                    │  │ Task 1: FastAPI Container                    │ │
                    │  │  GET /chat/rto          (→ Bedrock)          │ │
                    │  │  GET /chat/revenue      (→ Bedrock)          │ │
                    │  │  POST /sync             (→ SQS enqueue)      │ │
                    │  │  GET /sync/status       (→ DynamoDB check)   │ │
                    │  └──────────────────────────────────────────────┘ │
                    │  ┌──────────────────────────────────────────────┐ │
                    │  │ Task 2-50: Additional tasks (auto-scale)     │ │
                    │  │  CPU > 70% or latency > 500ms → +2 tasks    │ │
                    │  │  CPU < 30% for 5min → -1 task               │ │
                    │  └──────────────────────────────────────────────┘ │
                    └───────────────────────────────────────────────────┘
                         ↓                                    ↓
                    ┌────────────────┐          ┌──────────────────────┐
                    │  CloudFront    │          │   SQS Queue          │
                    │  CDN Cache     │          │  connector-sync      │
                    │  (static)      │          │  ↓                   │
                    └────────────────┘          │  Lambda Workers      │
                                               │  (1-20 concurrent)   │
                         ↓                      │  ↓                   │
                    ┌────────────────┐          │  RDS (isolated txn)  │
                    │  ElastiCache   │          │  ↓                   │
                    │  Redis 3-node  │          └──────────────────────┘
                    │  - Chat results│                    ↓
                    │  - Mappings    │          ┌──────────────────────┐
                    │  - Tool desc.  │          │  EventBridge         │
                    │  (60% hit rate)│          │  (sync.complete)     │
                    └────────────────┘          │  ↓ Triggers cache    │
                         ↑                      │    invalidation      │
                         │                      └──────────────────────┘
                    ┌────────────────────────────────────────────────────┐
                    │     RDS PostgreSQL (Multi-AZ)                      │
                    │  Primary: db.r6i.xlarge (4 vCPU, 32GB)             │
                    │  ┌──────────────────────────────────────────────┐  │
                    │  │ Partitioned Tables:                          │  │
                    │  │  - orders (merchant_id partition)            │  │
                    │  │  - shipments (merchant_id partition)         │  │
                    │  │  - payments (merchant_id partition)          │  │
                    │  │  - provenance (merchant_id + date partition) │  │
                    │  │  - entity_mappings (indexed)                 │  │
                    │  ├──────────────────────────────────────────────┤  │
                    │  │ Connection pooling (PgBouncer): 100 conn max │  │
                    │  ├──────────────────────────────────────────────┤  │
                    │  │ Row-Level Security: merchant_id scoped       │  │
                    │  └──────────────────────────────────────────────┘  │
                    │           ↑                          ↓              │
                    │  Read Replica 1             Read Replica 2         │
                    │  db.r6i.large               db.t3.xlarge           │
                    │  (Analytics)                (Backup)               │
                    └────────────────────────────────────────────────────┘
                         ↓                              ↓
                    ┌────────────────────────────────────────────────────┐
                    │  S3 (Audit Trail & Archive)                        │
                    │  ┌──────────────────────────────────────────────┐  │
                    │  │ Daily Backup: RDS snapshot                   │  │
                    │  │ Archive: Provenance tables older than 90 days│  │
                    │  │ (Move to S3 Glacier for 7-year retention)    │  │
                    │  │ Raw payloads: connector responses (audit)    │  │
                    │  └──────────────────────────────────────────────┘  │
                    └────────────────────────────────────────────────────┘
                         ↓
                    ┌────────────────────────────────────────────────────┐
                    │  CloudWatch & Monitoring                           │
                    │  ├─ Fargate CPU/Memory/Network metrics             │
                    │  ├─ RDS queries/connections/storage               │
                    │  ├─ Cache hit/miss ratios                          │
                    │  ├─ Bedrock token usage & costs                    │
                    │  ├─ Lambda execution time & errors                 │
                    │  └─ SQS queue depth & age                          │
                    │                                                     │
                    │  Alarms:                                            │
                    │  - CPU > 80% → Page on-call                        │
                    │  - DB connections > 90 → Scale up                  │
                    │  - Cache hit rate < 50% → Investigate              │
                    │  - Bedrock rate limit hit → Circuit breaker        │
                    └────────────────────────────────────────────────────┘


CONNECTION FLOW (Example: GET /chat/rto):

1. Request arrives at ALB
2. Routed to Fargate task
3. FastAPI middleware:
   a. Set X-Merchant-ID context
   b. Check Redis cache ("merchant:XXXX:rto_orders")
4. Cache HIT (60%):
   a. Return cached result
   b. Cost: $0
5. Cache MISS (40%):
   a. Query RDS (using merchant_id partition)
   b. Query time: 2ms (vs 10s without partitioning)
   c. Call Bedrock with result
   d. Bedrock tokens: 2K
   e. Cost: $0.01
   f. Store in Redis for 15 minutes
6. Response to user with citations
```

---

## Part 5: Scaling Phases & Roadmap

### Phase 1: Development (Current)
```
Timeline: Done
Servers:
  - LocalOS: Ollama (qwen2.5-coder)
  - DB: SQLite (data/app.db)
  - Deployment: uvicorn local

Capacity:
  - ~100 merchants
  - ~100 calls/min
  - Response time: 200-500ms

Cost: $500/month (dev environment)

Metrics:
  - Chat accuracy: 95% (heuristic fallback working)
  - Cache hit: N/A
  - Database latency: 2-10ms
```

### Phase 2: AWS Minimal (Weeks 1-5)
```
Timeline: Target v1.0 (end of May 2026)
Servers:
  - Bedrock: Claude 4.5 (managed API)
  - DB: RDS PostgreSQL single instance
  - Cache: ElastiCache Redis (1 node)
  - Sync: Lambda workers (SQS)
  - API: Fargate (2-3 tasks)

Capacity:
  - ~500 merchants
  - ~1k calls/min
  - Response time: 100-300ms

Cost: $2.5k/month

Deployment:
  - Terraform for IaC
  - CircleCI/Github Actions for CI/CD
  - RDS backups automated
  - Manual scaling triggers

Monitoring:
  - CloudWatch dashboards
  - Slack alerts on errors
```

### Phase 3: AWS Production (Months 2-3)
```
Timeline: June-July 2026
Servers:
  - Bedrock: Claude 4.5 (rate limiting: 10k calls/min)
  - DB: RDS PostgreSQL Multi-AZ + 2 read replicas
  - Partitioning: merchant_id + date
  - Cache: ElastiCache Redis 3-node cluster
  - Sync: Lambda auto-scaling (1-20 workers)
  - API: Fargate auto-scaling (5-20 tasks)

Capacity:
  - ~5k merchants
  - ~5k calls/min
  - Response time: 80-200ms

Cost: $8k/month (with discounts)

Features Added:
  - Row-level security (merchant isolation)
  - Cache invalidation on sync
  - Async job tracking
  - Dedupe detection & alerts
  - Multi-region read replicas (optional)

Monitoring:
  - Auto-scaling policies refined
  - Cost optimization enabled
  - RI (Reserved Instances) for steady workload
```

### Phase 4: AWS Full Enterprise (Months 4+)
```
Timeline: August 2026+
Servers:
  - Bedrock: Claude 4.5 + Claude 4.6 for reasoning
  - DB: Aurora PostgreSQL (managed, auto-scaling)
  - Sharding: Hash-based by merchant_id (if >50k merchants)
  - Cache: Memcached cluster + Redis
  - Sync: ECS cluster (GPU-enabled for bulk dedup)
  - API: Fargate multi-region (US, EU, APAC)

Capacity:
  - ~10k merchants
  - ~10k calls/min
  - ~100k concurrent users globally
  - Response time: 50-150ms

Cost: $11k-15k/month (with volume discounts)

Features Added:
  - Multi-region replication (disaster recovery)
  - Merchant-specific rate limits (SLA tiers)
  - Advanced caching (predictive pre-warming)
  - Real-time sync (webhook-based)
  - Cost optimization: Auto-scale down unused merchants
  - Analytics: self-serve dashboards (QuickSight)

Monitoring:
  - DataDog integrations
  - Anomaly detection
  - Cost forecasting
  - Compliance reporting (PCI, SOC2)
```

---

## Part 6: Cost Breakdown

### Phase 2 Monthly Cost ($2.5k)
```
Bedrock Claude 4.5:
  Input tokens: 10k calls × 2K avg = 20M tokens/min
  No cache: 20M tokens/min × 1,440 min × 30 days = 864B tokens
  Pricing: $5 per 1M input tokens
  Cost: 864B ÷ 1M × $5 = $4,320
  ╰─ This phase NOT using cache yet

RDS PostgreSQL (single):
  Instance: db.t3.xlarge
  Storage: 100GB
  Backups: 14 day retention
  Cost: $1.456/hour = $1,053/month

ElastiCache Redis (1 node):
  Instance: cache.t3.small
  Cost: $0.098/hour = $71/month

Fargate:
  vCPU: 0.25 × $0.04 = $0.01/hour
  Memory: 0.5GB × $0.005 = $0.0025/hour
  Average 2 tasks × 730 hours = $65/month

Lambda (sync workers):
  100M requests/month × 8s execution × 1GB
  = 800M GB-seconds = $13/month

S3 (backups):
  50GB monthly = $1/month

Total Phase 2: ≈ $2,500/month
```

### Phase 3 Monthly Cost ($11k - WITH CACHING)
```
Bedrock Claude 4.5 (with 60% cache hit):
  Calls: 10k calls/min × 60% cached = 6k cached
  Calls: 10k calls/min × 40% to Bedrock = 4k to Bedrock
  Tokens: 4k calls × 2K tokens = 8M tokens/min
  Monthly: 8M × 1,440 × 30 = 345.6B tokens
  Cost: 345.6B ÷ 1M × $5 = $1,728

RDS PostgreSQL Multi-AZ + 2 replicas:
  Primary: db.r6i.xlarge = $2.328/hour = $1,683/month
  Replica 1 (analytics): db.r6i.large = $1.164/hour = $842/month
  Replica 2 (backup): db.t3.xlarge = $0.292/hour = $212/month
  Storage: 1TB SSD = $200/month
  Multi-AZ: +50% = $500/month
  Total RDS: $3,437/month

ElastiCache Redis (3-node cluster):
  Instance: cache.r6g.xlarge (26GB each) × 3
  Cost: $2.256/hour × 730 = $4,896/month
  Cluster overhead: +5% = $245/month
  Total Cache: $5,141/month

Fargate (auto-scaling):
  Average 8 tasks (peak 20, low 3)
  vCPU: 0.5 × $0.04 = $0.02/hour × 730 = $146/month
  Memory: 1GB × $0.005 = $0.005/hour × 730 = $36/month
  × 8 tasks = $1,456/month

Lambda (sync workers):
  240k invocations/month × 8s × 1GB
  = 1.92M GB-seconds = $32/month

S3 (backups + archives):
  500GB monthly = $12/month

CloudFront (CDN):
  Cache hits on static responses
  100GB/month egress = $100/month

Data Transfer:
  Inter-region/AZ: $200/month

Monitoring (CloudWatch):
  Custom metrics + logs = $100/month

Total Phase 3: ≈ $11,241/month
Per merchant: $1.12/month
Per call: $0.0011

Compared to Phase 2: 60% cache saves $2,592 (from $4,320 to $1,728)
```

---

## Part 7: Implementation Priorities & Pointers

### Critical Path (Must-Do First)
```
1. ✅ Bedrock integration (Done: qwen2.5-coder working)
2. ⚠️  RDS Migration (Week 1) - BLOCKS everything else
3. ⚠️  Provenance Partitioning (Week 2) - Required for scale
4. ⚠️  ElastiCache (Week 3) - Saves 60% of cost
5. ⚠️  Async Sync (Week 4) - Enables API responsiveness
6. ⚠️  Merchant Isolation (Week 5) - Compliance requirement
```

### Git Strategy
```
main branch:
  - Always deployable to production
  - All changes code-reviewed
  - Automated tests pass

Feature branches:
  - phase/2-rds-migration
  - phase/3-provenance-partitioning
  - phase/4-elasticache
  - phase/5-async-sync
  - phase/6-merchant-isolation

Each branch includes:
  - Code changes
  - Database migrations
  - Tests
  - CloudFormation/Terraform
  - Deployment guide
```

### Testing Checklist
```
Before Phase transition:
- [ ] Local tests pass (pytest)
- [ ] Load test 10x expected traffic (k6)
- [ ] Failover test (RDS failover simulation)
- [ ] Cache invalidation tested
- [ ] Merchant isolation verified (no data leaks)
- [ ] Cost dashboard shows expected savings
- [ ] Backup/recovery tested
- [ ] Security scan (OWASP)
```

### Operations Checklist
```
Day 1 Production Readiness:
- [ ] On-call rotation defined
- [ ] Runbooks written (Confluence/GitHub wiki)
- [ ] Alerts tuned (no alert fatigue)
- [ ] Database backup schedule confirmed
- [ ] Disaster recovery plan documented
- [ ] Incident response process established
- [ ] Logging & audit trails enabled
- [ ] Compliance documentation updated
```

### Tools & Commands
```bash
# Terraform deployment
terraform init                    # First time only
terraform plan -out=tfplan        # Review changes
terraform apply tfplan            # Deploy

# Database migration
alembic init migrations           # First time only
alembic revision --autogenerate   # Detect schema changes
alembic upgrade head              # Apply migrations

# Load testing
k6 run tests/load/chat_rto.js     # 100 concurrent users
k6 run tests/load/sync_queue.js   # SQS throughput test

# Monitoring
aws s3 cp test-schema.sql s3://backup/
pg_dump -U postgres db > backup.sql

# Cost monitoring
aws ce get-cost-and-usage --metric UnblendedCost --groupby SERVICE
```

---

## Summary: What Happens When

| Date | What | Capacity |
|------|------|----------|
| Today | v0 (SQLite) |100 merchants, 100 calls/min |
| Week 1-2 | Phase 2a: RDS | 500 merchants, 1k calls/min |
| Week 3 | Phase 2b: Cache | 500 merchants, 1k calls/min (60% cheaper queries) |
| Week 4 | Phase 2c: Async sync | Same capacity, faster API |
| Week 5 | Phase 2d: Isolation | Multi-tenant ready |
| Month 2 | Phase 3: Auto-scaling | 5k merchants, 5k calls/min |
| Month 3 | Phase 3: Full enterprise | 10k merchants, 10k calls/min |

---
