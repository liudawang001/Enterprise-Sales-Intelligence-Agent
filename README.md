# Enterprise Sales Intelligence Agent（政企营销智能体）

**Enterprise Sales Intelligence Agent（政企营销智能体）** 是一套面向政企营销场景的状态化智能 Agent。系统通过 RAG 获取产品、套餐和营销活动知识，结合多轮对话形成结构化营销任务，并编排企业信息、地图、Web Search 与企业官网等多源工具，实现企业潜客发现、情报补全、实体归一化、证据核验、潜客评分及 Excel 交付。

## Phase 1 / Phase 2 / Phase 3 / Phase 4 / Phase 5 / Phase 6 / Phase 7 范围

Phase 1 实现 LangGraph Agent Runtime 与离线 Mock Workflow：多 Intent 入口、结构化 `LeadTask`、Required Slot 校验、真实 `interrupt()` / `Command(resume=...)`、MemorySaver、Mock Business Planning、Mock Research、Mock Lead Scoring、Mutation Skeleton 和 FastAPI `/api/chat`。

Phase 2 将 BusinessQA 升级为真实可追溯的 RAG Knowledge Engine：PDF 上传与按页解析、结构优先 Chunking、SHA-256 幂等、Embedding 抽象、Dense + 中文 Sparse 检索、Metadata/有效期/区域过滤、RRF、Reranker、No-Evidence Gate、页级 Citation 和离线 Evaluation。默认 Demo 使用内存 Repository 与确定性 FakeEmbedding；配置 PostgreSQL/pgvector 后可执行 Alembic migration 和 PGVectorStore 适配。

Phase 3 将业务知识编译为带来源、版本和冲突处理的 `LeadCriteria`。Phase 4 将该 Criteria 编译为有界 `SearchPlan`，通过企业数据、地图、Web Search 和 Web Fetch Provider 执行候选发现、低成本补全、Hard Filter 与有限深研。默认配置使用 Fake Provider，完整走相同 Provider/预算/来源链路且不消耗外部 credits；配置合法凭据后切换到真实适配器。

Phase 5 将多源 Candidate 转换为 `CanonicalEnterprise`，对每个业务字段独立建立 Evidence、归一化、冲突检测和主值选择，生成 Task-aware `VerifiedEnterpriseProfile`。最终排序由版本化的确定性 Scoring Profile 计算，LLM 仅能解释既有分数和合法 Evidence ID。

Phase 6 将对话升级为多 Task、不可变 Task Version 和依赖感知的局部重执行系统。自然语言修改先经过 `TaskReferenceResolver`、`MutationPreview`、`TaskDiff / CriteriaDiff` 与 `ArtifactReuseContext`，再由确定性 `TaskMutationPlanner` 选择最小安全 Scope。旧执行可以完成并保留历史，但版本栅栏禁止它覆盖新版本的 current head。

Phase 7 将某个明确 Task Version 的 Verified Lead、Lead Score 与字段级 Evidence 冻结为不可变 `DeliverySnapshot`。React Workspace 和 Excel Export 只消费同一个 Delivery Read Model，因此排名、评分、核验状态、公开联系方式与 Evidence lineage 不会在 UI 和工作簿之间产生两套口径。导出固定 Snapshot，后续 Task Mutation 不会改变已生成 Artifact。

## Phase 7 Delivery Workspace

```text
Task Version + Execution Snapshot
        |
        v
DeliverySnapshot -> DeliveryLeadRow / TaskSummaryDTO / LeadDetailDTO
        |                                      |
        v                                      v
React Workspace                         ExportSpec / ExportJob
                                               |
                                               v
                                      OpenPyXL -> XLSX Artifact
```

Workspace 提供 Task List、Conversation、Version Selector、SSE Progress、服务端分页/排序/筛选的 Lead Table、Lead Detail Drawer、字段核验、Evidence/Conflict、Score Breakdown、Export Panel、Export History 和下载。桌面端为三栏工作台，小屏为任务/对话/潜客三个 Tab。

历史版本通过 `/tasks/{task_id}?version={version}` 表达。历史视图显示 `Historical Version · 只读查看`，禁止从旧版本直接发起 Mutation；导出仍绑定所查看的旧 Snapshot，而不是自动跳到 current head。

Phase 7 Delivery API：

```text
GET  /api/tasks
GET  /api/tasks/{task_id}
GET  /api/tasks/{task_id}/versions
GET  /api/tasks/{task_id}/versions/{version}
GET  /api/tasks/{task_id}/versions/{version}/leads
GET  /api/tasks/{task_id}/versions/{version}/leads/{enterprise_id}
GET  /api/tasks/{task_id}/versions/{version}/leads/{enterprise_id}/score
GET  /api/enterprises/{enterprise_id}/evidence?task_id=...&version=...
GET  /api/tasks/{task_id}/events
GET  /api/tasks/{task_id}/events/stream
GET  /api/exports/fields
POST /api/exports
GET  /api/exports/{export_id}
GET  /api/exports/{export_id}/events
GET  /api/exports/{export_id}/download
GET  /api/tasks/{task_id}/exports
```

XLSX 可包含五个真实 Sheet：

| Sheet | 内容 |
|---|---|
| `潜客清单` | 用户选择的受控字段、排名、评分与核验状态 |
| `评分说明` | 已持久化的评分组件与 Scoring Profile Version |
| `证据摘要` | 字段主值、状态、置信度、来源、URL 与 Evidence 计数 |
| `任务信息` | Task Version、Criteria、Lead/Score Set、Snapshot 与 Export ID |
| `冲突明细` | 主值、备选值及对应来源，按导出选项生成 |

导出字段来自 `ExportFieldRegistry` allowlist；未知或敏感字段会被拒绝。任一已选择事实字段存在缺失时返回 `EXPORT_FIELD_DATA_INCOMPLETE`，ExportService 不会偷偷发起 Search 或补全。工作簿会防御公式注入，只将 HTTP/HTTPS 设为 Hyperlink，并清理文件名路径穿越字符。下载只读取已有 Artifact，并返回 SHA-256。

### 启动与 Demo

后端：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173/workspace`，在对话区输入“帮我找上海松江 3 家集团 V 网潜客”。任务完成后在潜客表点击企业名称查看字段状态、Evidence、冲突与 Score Breakdown；点击“导出”选择 Top N、字段和附加 Sheet，生成后可从面板或 Export History 下载。

默认 Demo 使用确定性 Fake Provider 和内存 Repository，不访问外部付费服务。页面展示的企业、电话、评分和证据均为合成演示数据，不代表真实企业情报或中国移动正式营销标准。

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
       BusinessPlanning -> Research -> Verification -> Score -> Promotion Guard
```

`RequirementGraph` 收集 `business`、`region`、`target_count`。缺失时调用 LangGraph `interrupt()`，同一 `session_id` 同时作为 `thread_id`，后续请求通过 `Command(resume={"text": ...})` 恢复，不创建第二个任务。`task_id` 由 Repository 单独生成 UUID。

ResearchGraph 不再内置固定企业；所有 Candidate 必须来自 Provider 返回并绑定 `SourceRecord`。Graph State 只保留 run/plan/set/batch 引用和计数，Candidate、Source、ToolRun 与集合 lineage 留在 Repository 边界。Phase 5 主链使用正式的确定性 `LeadScoringService`；`MockScoringService` 仅为前序阶段兼容保留。

## Phase 6 Conversation Task Control

同一 `thread_id` 可以拥有多个 `task_id`，每个 Task 的修改形成递增且不可覆盖的 `task_version`。任务可通过显式 ID、唯一业务名称或 Active Task 解析；多个候选无法消歧时触发 `TASK_SELECTION_REQUIRED`，并用原 `thread_id` 的 `Command(resume=...)` 继续。

MutationGraph 的执行顺序为：

```text
resolve_target_task -> load_current_task -> parse/validate_mutation
-> MutationPreview -> TaskDiff -> CriteriaDiff -> ArtifactReuseContext
-> classify_invalidation -> ReexecutionPlan -> persist new Task Version
```

七个路由值及最小执行边界：

| Scope | 执行范围 |
|---|---|
| `NONE` | 记录 no-op，不创建 Task Version 或新快照 |
| `DISPLAY_ONLY` | 复用 Score Set，仅 Projection / Top N |
| `RANK_ONLY` | 复用 Verified Profile，重新确定性评分 |
| `FILTER_ONLY` | 复用 Raw/Researched Candidate Set，重新过滤及必要核验 |
| `ENRICHMENT_REQUIRED` | 复用企业集合，仅定向补字段与重新核验 |
| `DISCOVERY_REQUIRED` | 复用仍有效的 Business Planning，重新 Research |
| `FULL_REPLAN` | 业务语义变化时从 Business Planning 完整重算 |

Scope 由 `TaskDiff + CriteriaDiff + ArtifactReuseContext + SearchPlan.field_dependencies` 共同决定。例如删除仅在 post-filter 使用的员工规模条件可走 `FILTER_ONLY`；删除已下推到 Discovery 的行业条件必须走 `DISCOVERY_REQUIRED`。运行时若复用假设不成立，只允许记录原因后安全升级 Scope。

每个新结果 head 保存 `TaskExecutionSnapshot`，串联 Criteria、SearchPlan、Raw/Filtered/Researched Candidate、Verified 与 Score Artifact。`ArtifactValidity` 区分 `CURRENT / REUSABLE / SUPERSEDED / INVALIDATED`。Promotion 前检查当前 Task Version；旧版本晚完成时保存为 `SUPERSEDED`，不会成为 current head。Discovery、Enrichment、Deep Research 与 Targeted Verification 的批次边界还会执行 cooperative superseded check。

Phase 6 API：

```text
GET  /api/tasks
GET  /api/tasks/{task_id}
GET  /api/tasks/{task_id}/versions
GET  /api/tasks/{task_id}/versions/{version}
POST /api/tasks/{task_id}/activate
POST /api/tasks/{task_id}/mutations
GET  /api/tasks/{task_id}/mutations/{mutation_id}
GET  /api/reexecution/{plan_id}
```

Lead Query 和 Export Request 都先解析 Task Reference，因此可以读取非 Active Task；Phase 6 Export 只解析 `task_id / task_version / lead_set_id`，不生成 Excel。

Phase 6 固定评测：

```bash
python -m evals.mutation.run_mutation_eval
```

当前固定数据包含 60 个 Mutation Scope case、20 个 Artifact Reuse case 和 20 个 Version/Stale case。CI Gate 包括 Scope Accuracy、Unsafe Under-reexecution Rate、Unnecessary Full Replan Rate、Artifact Reuse Correctness、Version Fence Correctness 与 Mutation Idempotency；这些是确定性合成工程指标，不代表生产流量效果。

Phase 7 固定评测：

```bash
python -m evals.delivery.run_delivery_eval
python -m scripts.benchmark_phase7_delivery
```

固定数据包含 20 个 Snapshot Consistency、20 个 Export Field、20 个 Evidence Display、10 个 Historical Version 与 10 个 Security case。Gate 覆盖 Snapshot Version Accuracy、UI/Excel Critical Field Consistency、Export Field Accuracy/Allowlist、Evidence Traceability、Export Idempotency、Workbook Parse、Unsafe Hyperlink、Formula Injection、Filename Traversal 与 Historical Version Accuracy。

2026-09-11 本地内存测试环境实测：1000 条 Delivery Projection、100 次 Lead List 查询的 P95 为 `277.237 ms`；完整五 Sheet XLSX 的 100 行生成耗时 `183.370 ms`、大小 `93,203 bytes`，1000 行生成耗时 `2,065.972 ms`、大小 `820,035 bytes`（证据摘要 13,000 行）。本地 Vite 开发服务器的 Chrome 首屏采样为 TTFB `3 ms`、FCP `68 ms`、LCP `68 ms`、CLS `0.08`。这些是单次本地合成数据测量，不是生产 SLA。

### Phase 7 边界

Phase 7 不实现 Production Engineering：尚未提供生产级鉴权/RBAC、多租户隔离、对象存储与签名 URL、异步队列/Worker、分布式事件总线、可观测性告警、备份恢复、限流、生产部署与真实数据合规治理；这些属于 Phase 8。

## Phase 5 Verification Architecture

```text
Researched Candidate Set
  -> Resolution Blocking
  -> deterministic matcher (credit code/provider relation/name/domain/phone/address)
  -> bounded ambiguous resolver gate
  -> CanonicalEnterprise + Candidate Link + Relation + Audit
  -> SourceRecord -> field-level Evidence -> normalization
  -> agreement/conflict/freshness/source-priority resolution
  -> bounded targeted verification for MISSING/UNVERIFIED fields
  -> VerifiedEnterpriseProfile + task-aware coverage
  -> versioned deterministic score breakdown
  -> grounded recommendation reason -> VerifiedLeadSet
```

不同且非空的统一社会信用代码是不可被 LLM 推翻的 Hard Negative。`BRANCH_OF`、`OFFICE_OF` 与 `SUBSIDIARY_OF` 始终保存为实体关系，不折叠为 `SAME_ENTITY`。字段冲突不会静默覆盖：例如官网电话 `021-1111` 与地图电话 `021-2222` 会保留两组 Evidence，字段状态为 `CONFLICTING`，展示主值仍按字段来源优先级、时效性和一致来源数选择。

Evidence 的完整审计链为：`LeadScore -> ScoreComponentResult -> ResolvedField -> Evidence -> SourceRecord -> Provider/URL`。公开联系方式过滤会在 Evidence Extraction 再执行一次，不保存个人手机号或私人邮箱。办公点数量基于规范化地址和近似坐标去重，仅统计 Office/Branch，不使用搜索结果条数。

内置 `GROUP_VNET` 与 `ENTERPRISE_DEDICATED_LINE` v1 Profile，组件包括 Business Fit、Office Distribution、Company Scale、Industry Preference、Location Fit、Evidence Confidence 与 Contact Completeness。缺失字段分别支持 `ZERO`、`NEUTRAL`、`REWEIGHT`；硬必需字段缺失返回 `NOT_SCORABLE` 和空分数。

> 内置 Scoring Profile 是项目 Demo Marketing Model，不代表中国移动官方潜客评分标准。

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

## Verification and Score API

```text
GET /api/tasks/{task_id}/verification
GET /api/enterprises/{enterprise_id}
GET /api/enterprises/{enterprise_id}/relations
GET /api/enterprises/{enterprise_id}/evidence
GET /api/enterprises/{enterprise_id}/fields/{field_name}/evidence
GET /api/tasks/{task_id}/scores
GET /api/leads/{enterprise_id}/score
GET /api/leads/{enterprise_id}/score/explain
```

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

Phase 4 migration `0004_phase4_enterprise_research` 新增 research run/plan/batch、candidate/set/member、source record 和 tool run 表。Phase 5 migration `0005_phase5_entity_evidence_scoring` 新增 canonical entity/link/relation/location、resolution/verification audit、field evidence/resolved profile、versioned scoring profile/score/reason/lead set 表。数据库集成测试使用 `TEST_DATABASE_URL`，没有配置时会跳过。

迁移完成后运行 `python -m scripts.seed_demo_scoring_profiles`，可按 `business_code + version` 幂等写入两个不可变 Demo Profile；修改权重时必须创建新版本，脚本不会覆盖已有历史版本。

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

Phase 5 固定评测：

```bash
python -m evals.entity.run_entity_eval
python -m evals.phase5.run_evidence_scoring_eval
```

当前 54 个实体 Pair 的 Precision / Recall / F1 / SAME_ENTITY Precision 均为 `1.000`，不同信用代码 Hard Negative Accuracy 为 `1.000`。30 个 Evidence case 的 Conflict Detection、Primary Value Selection、Source Traceability 均为 `1.000`；30 个 Scoring case 的 Determinism、Monotonicity、Profile Reproducibility 与硬必需字段缺失 `NOT_SCORABLE` 正确率均为 `1.000`。这些是固定合成 Demo 数据集指标，不代表生产数据表现。

## 测试

```bash
pytest
pytest -m integration
cd frontend && npm test
cd frontend && npm run build
```

所有测试离线运行，不需要 OpenAI、高德或企业信息 API Key。

## 当前阶段边界

Phase 6 尚不包含正式 Excel 导出、React 营销工作台、生产级 `AsyncPostgresSaver`、Redis 分布式锁/取消、Langfuse 全量生产观测、多租户 RBAC 或 CRM 写回。这些仍属于 Phase 7 / Phase 8。

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

第二次返回 `COMPLETED`，默认 Fake Provider fixture 中包含五条带来源的 Candidate；因少于目标 50，ResearchRun 状态为 `PARTIAL` 并带 `INSUFFICIENT_CANDIDATES`，但现有 Candidate 仍继续完成实体归一、字段核验与确定性评分。也可以直接发送“帮我找上海松江50家集团V网客户”验证无中断路径。

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

已完成：Phase 1 Runtime、MainGraph、Intent/Mutation Router、任务版本、MemorySaver、FastAPI；Phase 2 PDF Ingestion、Chunking、Embedding 抽象、Dense/Sparse/Hybrid Retrieval、RRF、Reranker、Citation、No-Evidence Gate、Evaluation 和回归测试。

Phase 4 已实现可配置的真实企业 API、高德、Tavily 和 Firecrawl adapters，以及有界多源研究工作流。本次环境未配置任何第三方 Key，因此真实 external smoke 未执行，不能声明真实 Provider E2E 已成功。

Phase 5 已实现 Entity Resolution、字段级 Evidence Verification/Conflict Resolution、Targeted Verification、Verified Profile/Coverage、版本化确定性 Lead Score、Grounded Explain、API、PostgreSQL schema/adapters 和固定评测。

尚未实现的 Phase 6～8 能力：对话任务控制的完整局部失效重算、正式 Excel/UI 交付、CRM 写回、生产级 PostgreSQL TaskRepository/AsyncPostgresSaver、Redis 分布式限流、多租户权限、Langfuse 生产观测、BI Dashboard、机器学习评分模型与 GraphRAG。
