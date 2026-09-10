# Enterprise Sales Intelligence Agent（政企营销智能体）

**Enterprise Sales Intelligence Agent（政企营销智能体）** 是一套面向政企营销场景的状态化智能 Agent。系统通过 RAG 获取产品、套餐和营销活动知识，结合多轮对话形成结构化营销任务，并编排企业信息、地图、Web Search 与企业官网等多源工具，实现企业潜客发现、情报补全、实体归一化、证据核验、潜客评分及 Excel 交付。

## Phase 1 / Phase 2 / Phase 3 / Phase 4 范围

Phase 1 实现 LangGraph Agent Runtime 与离线 Mock Workflow：多 Intent 入口、结构化 `LeadTask`、Required Slot 校验、真实 `interrupt()` / `Command(resume=...)`、MemorySaver、Mock Business Planning、Mock Research、Mock Lead Scoring、Mutation Skeleton 和 FastAPI `/api/chat`。

Phase 2 将 BusinessQA 升级为真实可追溯的 RAG Knowledge Engine：PDF 上传与按页解析、结构优先 Chunking、SHA-256 幂等、Embedding 抽象、Dense + 中文 Sparse 检索、Metadata/有效期/区域过滤、RRF、Reranker、No-Evidence Gate、页级 Citation 和离线 Evaluation。默认 Demo 使用内存 Repository 与确定性 FakeEmbedding；配置 PostgreSQL/pgvector 后可执行 Alembic migration 和 PGVectorStore 适配。

Phase 3 将业务知识编译为带来源、版本和冲突处理的 `LeadCriteria`。Phase 4 将该 Criteria 编译为有界 `SearchPlan`，通过企业数据、地图、Web Search 和 Web Fetch Provider 执行候选发现、低成本补全、Hard Filter 与有限深研。默认配置使用 Fake Provider，完整走相同 Provider/预算/来源链路且不消耗外部 credits；配置合法凭据后切换到真实适配器。

## 当前架构

```text
FastAPI /api/chat
        |
        v
MainGraph: load_context -> classify_intent -> Intent Router
        |             |              |             |
 BusinessQA   Requirement       Mutation      Query/Export/Chat
                     |
             interrupt / resume
                     |
       BusinessPlanning -> Research -> Score -> Response
```

`RequirementGraph` 收集 `business`、`region`、`target_count`。缺失时调用 LangGraph `interrupt()`，同一 `session_id` 同时作为 `thread_id`，后续请求通过 `Command(resume={"text": ...})` 恢复，不创建第二个任务。`task_id` 由 Repository 单独生成 UUID。

ResearchGraph 不再内置固定企业；所有 Candidate 必须来自 Provider 返回并绑定 `SourceRecord`。Graph State 只保留 run/plan/set/batch 引用和计数，Candidate、Source、ToolRun 与集合 lineage 留在 Repository 边界。`MockScoringService` 仍是前序阶段的演示评分，并非正式 Lead Score。

## Phase 4 Research Architecture

```text
LeadCriteria
  -> load/build/validate/persist SearchPlan
  -> Send(discovery batches)
  -> merge/normalize/persist raw set
  -> bounded soft search expansion (max rounds)
  -> Send(cheap enrichment batches)
  -> deterministic MATCH / NO_MATCH / UNKNOWN hard filter
  -> Send(selected deep research batches)
  -> researched candidate set + source lineage
```

`CriteriaPushdownPlanner` 根据各 Provider 的 `ProviderCapabilities` 将 Hard Constraint 拆为 API pushdown、post-filter 和 targeted enrichment。Provider 不支持的 Hard Constraint 不会被静默丢弃；所有来源均不可覆盖时计划验证返回 `UNRESOLVABLE_HARD_CONSTRAINT`。候选不足时只扩展查询词/Provider/Soft preference，绝不自动放宽 User/Official Hard Constraint。

外部调用统一经过 `BoundedProviderRuntime`：调用前原子预留 budget，Provider 类型分别使用 `asyncio.Semaphore`，仅对 timeout、429、502、503 做指数退避与有限重试，尊重 `Retry-After`，并用规范化参数的 SHA-256 `request_hash` 复用成功结果。每次调用都带 connect/read/total timeout；日志和 `request_summary` 会过滤 key、authorization、cookie、token 与 password。

## Provider Setup

复制 [.env.example](.env.example) 中所需配置到本地 `.env`。可配置适配器如下：

- `CommercialEnterpriseProvider`：面向用户合法授权的 JSON 企业数据 API，默认约定 `/companies/search` 和 `/companies/profile`；具体厂商字段映射应在 adapter 内调整。
- `AmapProvider`：高德 Web Service v5 POI text/detail，仅作为地点和办公点来源。
- `TavilyProvider`：Web 搜索，固定 `include_answer=false`，snippet 只作为线索。
- `FirecrawlProvider`：抓取公开网页 main content，限制正文长度；请求 URL 和返回 source URL 都重新执行 SSRF 校验。
- 四个 Fake Provider：默认离线模式，用于单元、集成和评测，不发起网络调用。

Web Fetch 只允许公开 HTTP(S) 地址，会拒绝 localhost、loopback、private/link-local/reserved IP 和 `file://`/`ftp://`。网页正文始终视为 `UNTRUSTED_EXTERNAL_CONTENT`；确定性抽取器不会执行网页指令。公开联系方式策略保留企业总机/客服/企业域邮箱，过滤个人手机号和常见私人邮箱。

## Research API

```text
GET /api/tasks/{task_id}/research
GET /api/tasks/{task_id}/candidates
GET /api/candidates/{candidate_id}
GET /api/candidates/{candidate_id}/sources
GET /api/research/{research_run_id}/plan
GET /api/research/{research_run_id}/events
```

候选 API 始终返回 `provisional: true`。Plan API 展示每个 Provider 的 pushdown、post-filter、enrichment 和实际 budget 使用量；events 端点以 SSE 返回当前研究阶段。

## Phase 2 RAG 架构

```text
PDF Upload -> Validate/File Hash -> PyMuPDF Pages -> Structure-aware Chunks
    -> Jieba lexical content + Embedding -> Knowledge Repository
    -> Query Analysis -> Dense + Sparse -> RRF -> Reranker
    -> Evidence Gate -> Grounded Answer / No Evidence -> Citation Validation
```

`BusinessQAGraph` 通过 `KnowledgeService` 访问知识库，不在节点中写 SQL、加载模型或拼接高优先级指令。文档内容属于不可信业务资料；没有足够证据时系统拒绝编造。Phase 4 ResearchGraph 消费同一份可追溯 Lead Criteria，并通过配置的 Provider 执行研究。

## PostgreSQL / pgvector

Phase 2 提供 `docker-compose.yml`（镜像为 `pgvector/pgvector:pg16`）和 Alembic migrations：

```bash
docker compose up -d postgres
alembic upgrade head
```

Phase 4 migration `0004_phase4_enterprise_research` 新增 research run/plan/batch、candidate/set/member、source record 和 tool run 表。数据库集成测试使用 `TEST_DATABASE_URL`，没有配置时会跳过。

## PDF Upload Demo

先生成仅用于本地演示的合成 PDF：

```bash
python scripts/create_demo_pdf.py
```

```bash
curl -X POST http://localhost:8000/api/documents \
  -F 'file=@data/demo_documents/demo_group_vnet.pdf' \
  -F 'title=集团V网 Demo 业务说明' \
  -F 'business=集团V网' \
  -F 'region=NATIONAL' \
  -F 'authority=DEMO'
```

Demo 文档必须是公开资料或明确标记为 `DEMO/SYNTHETIC` 的自建资料，不代表中国移动正式现行业务规则；禁止把真实内部 PDF 提交到 Git。

## RAG Query / Citation Demo

上传 Demo PDF 后：

```bash
curl -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"rag-demo-001","message":"集团V网主要面向什么客户？"}'
```

有证据时响应 `data.citations` 会包含 `document_id`、`chunk_id`、文档标题和页码；无证据时返回“当前知识库中没有找到足够证据确认该问题”，且不生成虚假 Citation。

## Evaluation

```bash
python -m evals.rag.run_retrieval_eval
```

当前 30 条合成数据（24 条可回答、6 条 Negative）的实际结果为：Dense Recall@5 `1.000` / MRR `0.792`；Sparse `1.000` / `0.938`；Hybrid `1.000` / `0.854`；Hybrid + Reranker `1.000` / `0.854`。这些只是本地 Demo 工程指标，不是生产指标。

Phase 4 固定评测包含 30 个 Search Planning、20 个 Hard Constraint Pushdown、20 个 Budget/Failure case：

```bash
python -m evals.research.run_research_eval
```

当前固定结果：SearchPlan Schema Validity `1.000`、Hard Constraint Coverage `1.000`、Budget Validity `1.000`。Provider 真实结果会变化，不作为稳定 CI gate。

## 安装与启动

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

## 测试

```bash
pytest
```

所有测试离线运行，不需要 OpenAI、高德或企业信息 API Key。

默认 `pytest` 排除 external marker。仅在 `.env.example` 中五项真实 Provider 配置均已合法设置后，显式运行（会消耗第三方额度）：

```bash
pytest -m external
```

## Chat API Demo

第一轮会触发澄清：

```bash
curl -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo-001","message":"帮我找集团V网客户"}'
```

返回 `WAITING_USER`，问题为“请确认主要筛选哪个地区，以及希望先寻找多少家企业？”。使用同一 `session_id` 恢复：

```bash
curl -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo-001","message":"上海松江，50家"}'
```

第二次返回 `COMPLETED`，默认 Fake Provider fixture 中包含五条带来源的 provisional Candidate；因少于目标 50，ResearchRun 状态为 `PARTIAL` 并带 `INSUFFICIENT_CANDIDATES`。也可以直接发送“帮我找上海松江50家集团V网客户”验证无中断路径。

## Phase 3 Business Rule & Lead Criteria Engine

Phase 3 将业务知识转换为可执行、可追溯、可版本化的 `LeadCriteria`。规则严格区分四类来源：`OFFICIAL_REQUIREMENT`（必须绑定 Phase 2 RAG Evidence）、`MARKETING_RULE`（人工维护的 Demo 营销经验）、`USER_REQUIREMENT`（当前任务约束）和 `MODEL_SUGGESTION`（默认只能是 Soft）。`RuleFieldRegistry` 与统一 `RuleOperator` 会在进入 Compiler 前校验字段、操作符和值类型。

规划链路为：

```text
TaskRequirement -> RAG Evidence -> Official Rules
                -> Marketing/User/Model Rules
                -> Normalize -> Validate -> Conflict Detection
                -> Resolve -> Deterministic Criteria Compiler
                -> Versioned Criteria Snapshot -> Phase 4 Research Execution
```

Criteria Snapshot 保存 `criteria_id`、`task_version`、`criteria_hash` 和 `source_rule_ids`。可通过 `GET /api/tasks/{task_id}/criteria` 或 `GET /api/criteria/{criteria_id}/explain` 查看 Hard/Soft 条件、来源、消息与 Evidence。官方 Hard 与用户 Hard 发生互斥时会触发 `RULE_CONFLICT` interrupt，使用原 `thread_id` resume 后重新校验。

Demo Marketing Rules（例如集团V网的 `office_count >= 2`）是项目模拟营销经验，不代表中国移动官方标准。ResearchGraph 对 Provider Candidate 执行 Hard Filter 与 Soft Preference 研究调度；默认 Fake Provider 只用于无凭据的离线开发，真实企业 API、高德、Tavily 和 Firecrawl 可通过环境变量启用。

Phase 3 数据库结构由 `0003_phase3_rules_criteria` migration 创建。执行 `python -m scripts.seed_demo_business_rules` 可按 `source_key` 幂等写入两个 Demo Business 与四条 Marketing Rule。默认离线 Demo 使用内存 repository；PostgreSQL adapters 位于 `app/repositories/`。

规则评测：

```bash
python -m evals.rules.run_rule_eval
```

当前自建数据集包含 30 条 Rule Extraction、20 条 Conflict 和 20 条 Criteria Case；实际结果为 Rule Exact Match `1.000`、Evidence Binding `1.000`、Conflict Accuracy `1.000`、Criteria Validity `1.000`。这是确定性 Demo 数据集结果，不代表真实 LLM 或生产数据表现。

## 已完成与未实现

已完成：Phase 1 Runtime、MainGraph、五个 SubGraph、Intent/Mutation Router、任务版本、MemorySaver、FastAPI；Phase 2 PDF Ingestion、Chunking、Embedding 抽象、Dense/Sparse/Hybrid Retrieval、RRF、Reranker、Citation、No-Evidence Gate、Evaluation 和回归测试。

Phase 4 已实现可配置的真实企业 API、高德、Tavily 和 Firecrawl adapters，以及有界多源研究工作流。本次环境未配置任何第三方 Key，因此真实 external smoke 未执行，不能声明真实 Provider E2E 已成功。

尚未实现：正式 Enterprise Entity Resolution、字段级 Evidence Verification/Conflict Resolution、Verified Confidence、正式 Lead Score、PostgreSQL TaskRepository、AsyncPostgresSaver、Redis 分布式限流、Langfuse 和正式 Excel 导出。这些属于后续 Phase。
