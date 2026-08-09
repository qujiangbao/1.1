# Database Physical Schema V1.0

> 版本：V1.0 | 状态：READY FOR IMPLEMENTATION
> 数据库：PostgreSQL 16 + pgvector + Redis
> 提供给：FastAPI Backend Agent, 所有 Business Agent (通过 Tool Gateway)

---

## 1. 总览

```
industrial_park_db
  |
  ├── 业务数据层 (5 表)
  │   ├── enterprise           企业主数据
  │   ├── enterprise_profile   企业AI画像
  │   ├── industry             产业体系 (树形)
  │   ├── policy               政策库
  │   └── risk                 风险数据
  |
  ├── Agent 运行层 (6 表)
  │   ├── agent_task           任务记录
  │   ├── agent_execution      执行记录
  │   ├── agent_trace          追踪链路
  │   ├── agent_memory         Agent 记忆
  │   ├── conversation         会话
  │   └── tool_call_log        工具调用审计
  |
  ├── 企业服务层 (4 表)
  │   ├── service_request      服务请求
  │   ├── service_ticket       服务工单
  │   ├── service_history      服务历史
  │   └── service_memory       服务记忆
  |
  ├── BI 层 (2 表)
  │   ├── dashboard_metric     指标存储
  │   └── dashboard_widget     组件配置
  |
  └── pgvector 向量库 (3 表)
      ├── policy_embedding     政策向量
      ├── industry_embedding   产业向量
      └── enterprise_embedding 企业向量
```

---

## 2. 业务数据层 DDL

### 2.1 enterprise（企业主数据）

```sql
CREATE TABLE enterprise (
    enterprise_id   VARCHAR(50) PRIMARY KEY,
    name            VARCHAR(500) NOT NULL,
    credit_code     VARCHAR(50) UNIQUE,
    industry_id     INTEGER REFERENCES industry(industry_id),
    park_id         VARCHAR(50),
    company_type    VARCHAR(50),
    status          VARCHAR(30) DEFAULT 'active',
    address         TEXT,
    location        POINT,                          -- GIS 坐标
    description     TEXT,
    created_time    TIMESTAMP DEFAULT NOW(),
    updated_time    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_enterprise_industry ON enterprise(industry_id);
CREATE INDEX idx_enterprise_park ON enterprise(park_id);
CREATE INDEX idx_enterprise_status ON enterprise(status);
CREATE INDEX idx_enterprise_location ON enterprise USING GIST(location);
```

### 2.2 enterprise_profile（企业AI画像）

```sql
CREATE TABLE enterprise_profile (
    profile_id      SERIAL PRIMARY KEY,
    enterprise_id   VARCHAR(50) UNIQUE REFERENCES enterprise(enterprise_id),
    business_scope  TEXT,
    core_product    TEXT,
    technology_stack JSONB,
    customer_info   JSONB,
    funding_stage   VARCHAR(50),
    employee_count  INTEGER,
    revenue_level   VARCHAR(50),
    rd_ratio        DECIMAL(5,2),
    growth_rate     DECIMAL(5,2),
    ai_summary      TEXT,
    updated_time    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_profile_funding ON enterprise_profile(funding_stage);
```

### 2.3 industry（产业体系 — 树形结构）

```sql
CREATE TABLE industry (
    industry_id     SERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    parent_id       INTEGER REFERENCES industry(industry_id),
    level           INTEGER NOT NULL,              -- 1=一级, 2=二级, 3=三级
    category        VARCHAR(100),                  -- manufacturing/service/tech
    description     TEXT,
    keywords        TEXT[],
    is_active       BOOLEAN DEFAULT true
);

CREATE INDEX idx_industry_parent ON industry(parent_id);
CREATE INDEX idx_industry_level ON industry(level);
```

### 2.4 policy（政策库）

```sql
CREATE TABLE policy (
    policy_id       VARCHAR(50) PRIMARY KEY,
    title           VARCHAR(500) NOT NULL,
    level           VARCHAR(30),                   -- national/provincial/municipal/district
    department      VARCHAR(200),
    category        VARCHAR(100),
    industry_scope  TEXT[],                        -- 适用行业
    region_scope    TEXT[],                        -- 适用区域
    content         TEXT,
    publish_date    DATE,
    expire_date     DATE,
    status          VARCHAR(30) DEFAULT 'active',
    source          VARCHAR(500),
    file_url        VARCHAR(1000)
);

CREATE INDEX idx_policy_level ON policy(level);
CREATE INDEX idx_policy_status ON policy(status);
CREATE INDEX idx_policy_industry ON policy USING GIN(industry_scope);
CREATE INDEX idx_policy_region ON policy USING GIN(region_scope);
```

### 2.5 risk（风险数据）

```sql
CREATE TABLE risk (
    risk_id         SERIAL PRIMARY KEY,
    enterprise_id   VARCHAR(50) REFERENCES enterprise(enterprise_id),
    risk_type       VARCHAR(50),                   -- business/finance/opinion/legal/talent/market
    risk_score      DECIMAL(5,2),
    risk_level      VARCHAR(20),                   -- LOW/MEDIUM/HIGH
    risk_reason     TEXT,
    source          VARCHAR(200),
    indicators      JSONB,
    created_time    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_risk_enterprise ON risk(enterprise_id);
CREATE INDEX idx_risk_type ON risk(risk_type);
CREATE INDEX idx_risk_level ON risk(risk_level);
CREATE INDEX idx_risk_time ON risk(created_time);

-- 风险指标明细
CREATE TABLE risk_indicator (
    id              SERIAL PRIMARY KEY,
    enterprise_id   VARCHAR(50) REFERENCES enterprise(enterprise_id),
    indicator_name  VARCHAR(100),
    indicator_value DECIMAL(10,2),
    weight          DECIMAL(5,2),
    source          VARCHAR(200),
    recorded_time   TIMESTAMP DEFAULT NOW()
);

-- 风险事件
CREATE TABLE risk_event (
    id              SERIAL PRIMARY KEY,
    enterprise_id   VARCHAR(50) REFERENCES enterprise(enterprise_id),
    event_type      VARCHAR(50),
    description     TEXT,
    severity        VARCHAR(20),
    event_date      DATE,
    created_time    TIMESTAMP DEFAULT NOW()
);
```

### 2.6 辅助业务表

```sql
-- 企业财务
CREATE TABLE enterprise_finance (
    id              SERIAL PRIMARY KEY,
    enterprise_id   VARCHAR(50) REFERENCES enterprise(enterprise_id),
    financing_round VARCHAR(50),
    financing_amount DECIMAL(15,2),
    investors       TEXT[],
    cash_flow       VARCHAR(30),
    revenue         DECIMAL(15,2),
    valuation       DECIMAL(15,2),
    recorded_date   DATE
);

-- 企业招聘
CREATE TABLE enterprise_recruitment (
    id              SERIAL PRIMARY KEY,
    enterprise_id   VARCHAR(50) REFERENCES enterprise(enterprise_id),
    job_count       INTEGER,
    job_types       TEXT[],
    recruitment_change DECIMAL(5,2),
    recorded_date   DATE
);

-- 企业舆情
CREATE TABLE enterprise_news (
    id              SERIAL PRIMARY KEY,
    enterprise_id   VARCHAR(50) REFERENCES enterprise(enterprise_id),
    title           VARCHAR(500),
    content         TEXT,
    sentiment_score DECIMAL(5,2),
    event_type      VARCHAR(50),
    source_url      VARCHAR(1000),
    publish_date    DATE
);
```

---

## 3. Agent 运行层 DDL

```sql
-- 任务
CREATE TABLE agent_task (
    task_id         VARCHAR(50) PRIMARY KEY,
    conversation_id VARCHAR(50) REFERENCES conversation(conversation_id),
    user_id         VARCHAR(50),
    intent          VARCHAR(100),
    goal            TEXT,
    priority        VARCHAR(20),
    plan            JSONB,
    status          VARCHAR(30) DEFAULT 'created',
    result          JSONB,
    error           JSONB,
    created_time    TIMESTAMP DEFAULT NOW(),
    completed_time  TIMESTAMP
);

CREATE INDEX idx_task_status ON agent_task(status);
CREATE INDEX idx_task_user ON agent_task(user_id);
CREATE INDEX idx_task_created ON agent_task(created_time);

-- Agent 执行记录
CREATE TABLE agent_execution (
    execution_id    VARCHAR(50) PRIMARY KEY,
    task_id         VARCHAR(50) REFERENCES agent_task(task_id),
    agent_name      VARCHAR(100),
    order_num       INTEGER,
    input           JSONB,
    output          JSONB,
    status          VARCHAR(30),
    start_time      TIMESTAMP,
    end_time        TIMESTAMP,
    duration_ms     INTEGER,
    error           JSONB
);

CREATE INDEX idx_exec_task ON agent_execution(task_id);
CREATE INDEX idx_exec_agent ON agent_execution(agent_name);

-- Agent Trace
CREATE TABLE agent_trace (
    trace_id        VARCHAR(50) PRIMARY KEY,
    task_id         VARCHAR(50) REFERENCES agent_task(task_id),
    step            INTEGER,
    type            VARCHAR(50),              -- supervisor_decision/agent_call/tool_call
    agent_name      VARCHAR(100),
    action          VARCHAR(200),
    input           JSONB,
    output          JSONB,
    source          VARCHAR(200),
    timestamp       TIMESTAMP DEFAULT NOW(),
    duration_ms     INTEGER
);

CREATE INDEX idx_trace_task ON agent_trace(task_id);

-- Tool 调用审计
CREATE TABLE tool_call_log (
    tool_call_id    VARCHAR(50) PRIMARY KEY,
    execution_id    VARCHAR(50),
    agent_name      VARCHAR(100),
    tool_name       VARCHAR(100),
    parameters      JSONB,
    response        JSONB,
    duration_ms     INTEGER,
    status          VARCHAR(30),
    timestamp       TIMESTAMP DEFAULT NOW()
);

-- Agent Memory（带向量）
CREATE TABLE agent_memory (
    memory_id       SERIAL PRIMARY KEY,
    agent_name      VARCHAR(100),
    memory_type     VARCHAR(50),              -- supervisor/agent/knowledge
    content         JSONB,
    summary         TEXT,
    tags            TEXT[],
    embedding       VECTOR(1536),
    created_time    TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_memory_agent ON agent_memory(agent_name);
CREATE INDEX idx_memory_type ON agent_memory(memory_type);
CREATE INDEX idx_memory_embedding ON agent_memory 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 会话
CREATE TABLE conversation (
    conversation_id VARCHAR(50) PRIMARY KEY,
    user_id         VARCHAR(50),
    title           VARCHAR(500),
    status          VARCHAR(30) DEFAULT 'active',
    created_time    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE conversation_message (
    message_id      SERIAL PRIMARY KEY,
    conversation_id VARCHAR(50) REFERENCES conversation(conversation_id),
    role            VARCHAR(20),              -- user/assistant/system/tool
    content         TEXT,
    agent_name      VARCHAR(100),
    metadata        JSONB,
    timestamp       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_msg_conv ON conversation_message(conversation_id);
```

---

## 4. 企业服务层 DDL

```sql
CREATE TABLE enterprise_service_request (
    id              SERIAL PRIMARY KEY,
    enterprise_id   VARCHAR(50) REFERENCES enterprise(enterprise_id),
    request_text    TEXT,
    intent          VARCHAR(100),
    service_category VARCHAR(100),
    priority        VARCHAR(20),
    lifecycle_stage VARCHAR(50),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE service_ticket (
    id              SERIAL PRIMARY KEY,
    ticket_id       VARCHAR(50) UNIQUE NOT NULL,
    enterprise_id   VARCHAR(50) REFERENCES enterprise(enterprise_id),
    service_category VARCHAR(100),
    sub_services    JSONB,
    status          VARCHAR(30) DEFAULT 'created',
    assigned_agents JSONB,
    results         JSONB,
    created_at      TIMESTAMP DEFAULT NOW(),
    completed_at    TIMESTAMP
);

CREATE TABLE service_history (
    id              SERIAL PRIMARY KEY,
    enterprise_id   VARCHAR(50),
    ticket_id       VARCHAR(50),
    service_type    VARCHAR(100),
    description     TEXT,
    result          JSONB,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE enterprise_service_memory (
    id              SERIAL PRIMARY KEY,
    enterprise_id   VARCHAR(50),
    memory_type     VARCHAR(50),
    content         JSONB,
    embedding       VECTOR(1536),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_svc_memory_embedding ON enterprise_service_memory 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
```

---

## 5. BI 层 DDL

```sql
CREATE TABLE dashboard_metric (
    id              SERIAL PRIMARY KEY,
    metric_code     VARCHAR(100) UNIQUE,
    metric_name     VARCHAR(200),
    metric_category VARCHAR(100),
    value           DOUBLE PRECISION,
    dimension       JSONB,
    period          VARCHAR(20),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE dashboard_widget (
    id              SERIAL PRIMARY KEY,
    dashboard_id    VARCHAR(50),
    widget_type     VARCHAR(50),
    title           VARCHAR(200),
    config          JSONB,
    position        JSONB,
    permission      VARCHAR(50)
);

CREATE INDEX idx_metric_category ON dashboard_metric(metric_category);
CREATE INDEX idx_metric_period ON dashboard_metric(period);
```

---

## 6. pgvector 向量库 DDL

```sql
-- 需先启用: CREATE EXTENSION vector;

-- 政策向量（RAG 检索）
CREATE TABLE policy_embedding (
    id              SERIAL PRIMARY KEY,
    policy_id       VARCHAR(50) REFERENCES policy(policy_id),
    chunk_index     INTEGER,
    content         TEXT,
    metadata        JSONB,
    embedding       VECTOR(1536)
);

CREATE INDEX idx_policy_emb ON policy_embedding 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 产业向量
CREATE TABLE industry_embedding (
    id              SERIAL PRIMARY KEY,
    industry_id     INTEGER REFERENCES industry(industry_id),
    content         TEXT,
    doc_type        VARCHAR(50),
    embedding       VECTOR(1536)
);

CREATE INDEX idx_industry_emb ON industry_embedding 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- 企业语义搜索向量
CREATE TABLE enterprise_embedding (
    id              SERIAL PRIMARY KEY,
    enterprise_id   VARCHAR(50) REFERENCES enterprise(enterprise_id),
    content         TEXT,
    embedding       VECTOR(1536)
);

CREATE INDEX idx_enterprise_emb ON enterprise_embedding 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

---

## 7. 核心索引汇总

| 表 | 索引 | 类型 | 用途 |
|---|------|------|------|
| enterprise | idx_enterprise_location | GIST | GIS 空间查询 |
| enterprise | idx_enterprise_industry | B-tree | 按行业筛选 |
| policy | idx_policy_industry | GIN | 数组字段过滤 |
| agent_memory | idx_memory_embedding | IVFFlat | 向量相似搜索 |
| policy_embedding | idx_policy_emb | IVFFlat | RAG 检索 |
| agent_task | idx_task_status | B-tree | 任务状态查询 |
| agent_trace | idx_trace_task | B-tree | Trace 查询 |

---

## 8. ER 关系图（文字版）

```
industry ──1:N──> enterprise ──1:1──> enterprise_profile
    |                  |
    |                  +──1:N──> enterprise_finance
    |                  +──1:N──> enterprise_recruitment
    |                  +──1:N──> enterprise_news
    |                  +──1:N──> risk
    |                  +──1:N──> risk_indicator
    |                  +──1:N──> risk_event
    |                  +──1:N──> service_ticket
    |
policy ──1:N──> policy_embedding (pgvector)

conversation ──1:N──> conversation_message
     |
     +──1:N──> agent_task ──1:N──> agent_execution
                       +──1:N──> agent_trace
```

---

## 9. Redis 缓存设计

```
# Key 设计
enterprise:{id}:profile        → JSON (企业画像缓存, TTL=1h)
enterprise:{id}:risk           → JSON (风险评分缓存, TTL=30m)
policy:search:{hash}           → JSON (政策搜索结果, TTL=15m)
session:{session_id}           → JSON (会话状态, TTL=30m)
rate_limit:{user_id}:{api}     → INT (速率限制, TTL=1m)
ws:task:{task_id}:events       → LIST (WebSocket 事件队列)
agent:status:{agent_name}      → JSON (Agent 健康状态, TTL=10s)
```

---

**文档状态：READY FOR IMPLEMENTATION**
