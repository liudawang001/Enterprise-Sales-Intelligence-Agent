# Enterprise Sales Intelligence Agent（政企营销智能体）

**Enterprise Sales Intelligence Agent（政企营销智能体）** 是一套面向政企营销场景的状态化智能 Agent。系统通过 RAG 获取产品、套餐和营销活动知识，结合多轮对话形成结构化营销任务，并编排企业信息、地图、Web Search 与企业官网等多源工具，实现企业潜客发现、情报补全、实体归一化、证据核验、潜客评分及 Excel 交付。

## Phase 1 / Phase 2 / Phase 3 范围

Phase 1 实现 LangGraph Agent Runtime 与离线 Mock Workflow：多 Intent 入口、结构化 `LeadTask`、Required Slot 校验、真实 `interrupt()` / `Command(resume=...)`、MemorySaver、Mock Business Planning、Mock Research、Mock Lead Scoring、Mutation Skeleton 和 FastAPI `/api/chat`。

Phase 2 将 BusinessQA 升级为真实可追溯的 RAG Knowledge Engine：PDF 上传与按页解析、结构优先 Chunking、SHA-256 幂等、Embedding 抽象、Dense + 中文 Sparse 检索、Metadata/有效期/区域过滤、RRF、Reranker、No-Evidence Gate、页级 Citation 和离线 Evaluation。默认 Demo 使用内存 Repository 与确定性 FakeEmbedding；配置 PostgreSQL/pgvector 后可执行 Alembic migration 和 PGVectorStore 适配。

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

`MockResearchService` 提供五条示例企业，`MockScoringService` 使用固定规则打分；Graph State 仅保存集合引用、数量和少量演示结果，业务对象保留在 Service 边界。

## Phase 2 RAG 架构

```text
PDF Upload -> Validate/File Hash -> PyMuPDF Pages -> Structure-aware Chunks
    -> Jieba lexical content + Embedding -> Knowledge Repository
    -> Query Analysis -> Dense + Sparse -> RRF -> Reranker
    -> Evidence Gate -> Grounded Answer / No Evidence -> Citation Validation
```

`BusinessQAGraph` 通过 `KnowledgeService` 访问知识库，不在节点中写 SQL、加载模型或拼接高优先级指令。文档内容属于不可信业务资料；没有足够证据时系统拒绝编造。`ResearchGraph` 在 Phase 3 仍使用 synthetic Mock 企业，但已真实执行 Lead Criteria。

## PostgreSQL / pgvector

Phase 2 提供 `docker-compose.yml`（镜像为 `pgvector/pgvector:pg16`）和 Alembic migrations：

```bash
docker compose up -d postgres
alembic upgrade head
```

当前开发环境未安装 Docker Compose 插件，因此这里只验证了 migration 静态 SQL 生成；数据库集成测试使用 `TEST_DATABASE_URL`，没有配置时会跳过。

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

第二次返回 `COMPLETED`，包含五条 Mock Lead。也可以直接发送“帮我找上海松江50家集团V网客户”验证无中断路径。

## Phase 3 Business Rule & Lead Criteria Engine

Phase 3 将业务知识转换为可执行、可追溯、可版本化的 `LeadCriteria`。规则严格区分四类来源：`OFFICIAL_REQUIREMENT`（必须绑定 Phase 2 RAG Evidence）、`MARKETING_RULE`（人工维护的 Demo 营销经验）、`USER_REQUIREMENT`（当前任务约束）和 `MODEL_SUGGESTION`（默认只能是 Soft）。`RuleFieldRegistry` 与统一 `RuleOperator` 会在进入 Compiler 前校验字段、操作符和值类型。

规划链路为：

```text
TaskRequirement -> RAG Evidence -> Official Rules
                -> Marketing/User/Model Rules
                -> Normalize -> Validate -> Conflict Detection
                -> Resolve -> Deterministic Criteria Compiler
                -> Versioned Criteria Snapshot -> Mock Criteria Execution
```

Criteria Snapshot 保存 `criteria_id`、`task_version`、`criteria_hash` 和 `source_rule_ids`。可通过 `GET /api/tasks/{task_id}/criteria` 或 `GET /api/criteria/{criteria_id}/explain` 查看 Hard/Soft 条件、来源、消息与 Evidence。官方 Hard 与用户 Hard 发生互斥时会触发 `RULE_CONFLICT` interrupt，使用原 `thread_id` resume 后重新校验。

Demo Marketing Rules（例如集团V网的 `office_count >= 2`）是项目模拟营销经验，不代表中国移动官方标准。ResearchGraph 当前仅消费这些 Criteria 对 synthetic Mock 企业做 Hard Filter 与简单 Soft Preference 排序；真实企业信息 API、高德地图、Web Search、企业官网、Entity Resolution、正式 Lead Scoring 仍属于后续阶段。

Phase 3 数据库结构由 `0003_phase3_rules_criteria` migration 创建。执行 `python -m scripts.seed_demo_business_rules` 可按 `source_key` 幂等写入两个 Demo Business 与四条 Marketing Rule。默认离线 Demo 使用内存 repository；PostgreSQL adapters 位于 `app/repositories/`。

规则评测：

```bash
python -m evals.rules.run_rule_eval
```

当前自建数据集包含 30 条 Rule Extraction、20 条 Conflict 和 20 条 Criteria Case；实际结果为 Rule Exact Match `1.000`、Evidence Binding `1.000`、Conflict Accuracy `1.000`、Criteria Validity `1.000`。这是确定性 Demo 数据集结果，不代表真实 LLM 或生产数据表现。

## 已完成与未实现

已完成：Phase 1 Runtime、MainGraph、五个 SubGraph、Intent/Mutation Router、任务版本、MemorySaver、FastAPI；Phase 2 PDF Ingestion、Chunking、Embedding 抽象、Dense/Sparse/Hybrid Retrieval、RRF、Reranker、Citation、No-Evidence Gate、Evaluation 和回归测试。

尚未实现：真实 Enterprise Research、企业信息 API、高德地图、官网抓取、正式 Entity Resolution、Lead Evidence、正式 Lead Scoring、PostgreSQL TaskRepository、AsyncPostgresSaver、Redis、Langfuse、正式 Excel 导出。这些属于后续 Phase。
