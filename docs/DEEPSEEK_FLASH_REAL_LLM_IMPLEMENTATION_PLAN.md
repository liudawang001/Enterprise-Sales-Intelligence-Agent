# DeepSeek Flash 真实 LLM 链路开发计划

**项目：** Enterprise Sales Intelligence Agent  
**目标模型：** `deepseek-flash`  
**计划版本：** v1.0  通过前置 Release Gate 后执行  
**编制日期：** 2026-09-14（Asia/Shanghai）

## 1. 目标与边界

### 1.1 目标

把当前“默认 FakeChatModel、局部正则解析、未闭合的 ChatOpenAI 注入”升级为可观测、可回退、可验收的真实 DeepSeek LLM 链路：

```text
用户消息
  -> MainGraph
  -> Intent / Requirement 结构化理解
  -> RAG 检索与证据门禁
  -> DeepSeek Flash 受证据约束的回答
  -> LangGraph 状态、引用、审计与 API 响应
```

同时将同一个 LLM 依赖注入到已有的官方规则抽取、模型建议和研究查询生成扩展点，确保没有“配置了真实模型但业务仍静默走 Fake”的生产路径。

### 1.2 非目标

- 不让 LLM 直接决定 Hard Filter、实体合并、Lead Score 或任务版本提升；这些仍由确定性代码和证据链负责。
- 不把 API Key 写入代码、文档、测试 fixture、日志、checkpoint、截图或 Git 历史。
- 不在本计划中引入新的 Agent 框架或替换现有 LangGraph 主图。
- 不因为接入 LLM 而放宽现有 SSRF、工作区隔离、Citation、Evidence 和版本围栏。

## 2. 当前基线与已识别问题

| 区域 | 当前实现 | 风险 |
|---|---|---|
| Provider | `app/providers/llm/factory.py` 仅在 `provider == openai_compatible` 时创建 `ChatOpenAI`，缺少配置时静默返回 `FakeChatModel` | 生产配置错误会返回合成答案，无法发现 |
| QA | `KnowledgeService.answer()` 调用 `self.chat_model.answer(question, hits)` | `ChatOpenAI` 没有同名业务方法，配置真实 Key 后会在运行时失败 |
| Intent | `app/agent/nodes/intent.py` 只有正则规则 | 复杂自然语言无法理解；没有 LLM 置信度回退 |
| Requirement | `extract_task_patch()` 只有正则解析 | 多条件、否定、修改语句覆盖不足 |
| Rule | `OfficialRuleExtractor`、`ModelSuggestionGenerator` 已支持 `with_structured_output`，但 `BusinessRuleService` 没有注入 LLM | 接口存在但真实链路未启用 |
| Research | `SearchQueryGenerator.generate_with_llm()` 已存在，主流程仍使用确定性生成 | LLM 扩展点没有统一配置、预算和验收 |
| 配置 | 只有 `LLM_PROVIDER/LLM_MODEL/LLM_API_KEY/LLM_BASE_URL` | 没有超时、重试、思考模式、结构化输出及生产强校验 |
| 测试 | 现有测试主要覆盖 Fake/离线路径 | 缺少 DeepSeek 请求契约、结构化解析、超时/429/脱敏和真实 smoke |

## 3. 官方 DeepSeek API 契约（已核验）

核验来源（访问日期：2026-09-14）：

- [Your First API Call](https://api-docs.deepseek.com/)
- [JSON Output](https://api-docs.deepseek.com/guides/json_mode)
- [Tool Calls](https://api-docs.deepseek.com/guides/tool_calls)

必须以官方文档和 SDK 实际行为为准，不在代码中复制 API Key。

### 3.1 基本调用

- OpenAI-compatible `base_url`：`https://api.deepseek.com`
- Chat endpoint：`POST /chat/completions`
- 模型名：`deepseek-flash`
- 认证：`Authorization: Bearer <DEEPSEEK_API_KEY>`，优先使用 `langchain-openai` / `openai` SDK。
- `stream` 可选；第一阶段默认非流式，待 API SSE 验收通过后再接入 UI 流式输出。

LangChain 目标配置形态：

```python
ChatOpenAI(
    model="deepseek-flash",
    api_key=SecretStr(...),
    base_url="https://api.deepseek.com",
    timeout=..., 
    max_retries=...,
    reasoning_effort="...",
    extra_body={"thinking": {"type": "enabled"}},
)
```

`reasoning_effort` 与 `thinking` 是否启用必须由配置控制，并在 smoke 中验证服务端是否接受；默认关闭以降低延迟和成本。

### 3.2 JSON/结构化输出

DeepSeek JSON Output 要求：

1. 请求传 `response_format: {"type": "json_object"}`；
2. system 或 user prompt 必须明确包含 `json`，并提供目标 JSON 形状示例；
3. 对空 content、截断 JSON、字段类型错误进行显式处理和有限重试；
4. 最终必须通过 Pydantic `model_validate`，不能把未经校验的字典写入 Task/Rule/Criteria。

对于当前 `with_structured_output()`，先验证 `ChatOpenAI` 对 DeepSeek 的兼容行为；若不能稳定生成 provider-native schema，则实现统一的 `JsonStructuredInvoker`：JSON mode -> `json.loads` -> Pydantic 校验 -> 一次纠错重试。

### 3.3 Tool Calls 边界

DeepSeek Tool Calls 支持函数 schema 和 strict 模式，但 Chat Completions 不支持把模型生成的 tool call 消息插入历史中间位置。第一阶段不让 LLM 直接执行研究 Provider；所有外部工具仍走现有 Provider Adapter、预算、重试、SSRF 和幂等边界。

## 4. 目标架构

### 4.1 LLM 抽象

新增 `app/providers/llm/base.py`，定义最小接口：

- `ainvoke_text(messages, *, metadata) -> str`
- `invoke_text(messages, *, metadata) -> str`
- `structured(schema, messages, *, metadata) -> BaseModel`
- `astream_text(...)`（第二阶段）

新增 `app/providers/llm/deepseek.py`：

- 内部封装 `ChatOpenAI`，固定或校验 DeepSeek base URL；
- 统一 timeout、有限重试、request id、token usage 采集；
- 统一异常映射：认证、限流、超时、服务端错误、响应解析错误；
- 通过 `redaction` 层禁止输出 API Key、Authorization、Cookie、完整 prompt/response（除非显式允许且脱敏）。

保留 `FakeChatModel` 作为显式离线依赖，只能在 `LLM_PROVIDER=fake` 或测试注入时使用。

### 4.2 Provider Factory 与严格模式

改造 `create_chat_model()`：

- `deepseek`：创建 DeepSeek 适配器；
- `openai_compatible`：保留通用兼容模式，但必须显式配置；
- `fake`：仅开发/测试允许；
- 未知 provider 直接抛错，不静默降级为 Fake。

生产校验规则：

- `APP_ENV=production` 时禁止 `LLM_PROVIDER=fake`；
- 要求 `LLM_MODEL=deepseek-flash`、HTTPS `LLM_BASE_URL=https://api.deepseek.com`、非空 API Key；
- 禁止在启动日志、健康检查和异常响应中回显 Key；
- 失败时启动失败或明确 `LLM_UNAVAILABLE`，不得返回合成业务结论。

### 4.3 LangGraph 依赖注入

`AgentDependencies` 增加 `llm` 字段，并由 `build_dependencies(settings)` 和 `build_postgres_dependencies()` 使用同一个实例注入：

- `KnowledgeService(chat_model=llm)`；
- `BusinessRuleService(llm=llm)`；
- Intent/Requirement 节点通过 deps 使用 LLM；
- `SearchQueryGenerator` 作为受配置开关控制的可选扩展；
- 测试可注入 `FakeChatModel` 或 deterministic structured stub。

同时修复 `create_app(settings)` 与依赖构造之间读取全局缓存 settings 的问题，确保传入的 Settings 对所有 provider 生效。

## 5. 业务链路接入顺序

### Phase A — Provider、配置与安全基线

**目标：** 先让真实客户端可创建、可失败、可观测，再接业务节点。

任务：

1. 新增 DeepSeek adapter/base protocol、错误类型、脱敏和 usage model。
2. 扩展 Settings：
   - `LLM_PROVIDER=deepseek`
   - `LLM_MODEL=deepseek-flash`
   - `LLM_BASE_URL=https://api.deepseek.com`
   - `LLM_API_KEY`（仅环境变量/Secret Manager）
   - `LLM_TIMEOUT_SECONDS`、`LLM_MAX_RETRIES`、`LLM_REASONING_EFFORT`、`LLM_THINKING_TYPE`
   - `LLM_STRUCTURED_MAX_RETRIES`、`LLM_MAX_COMPLETION_TOKENS`
3. 更新 `.env.example`，只保留空占位符；不提交真实密钥。
4. 生产启动校验和 provider 健康检查：区分“配置有效”和“远端可调用”。
5. 增加依赖版本兼容测试，锁定 `langchain-openai` / `openai` 的实际请求参数行为。

交付物：`app/providers/llm/{base,deepseek,factory}.py`、settings 变更、配置说明、单元测试。

### Phase B — 真实 Business QA（最小闭环）

**目标：** 先打通用户可见且有 Evidence Gate 的问答链路。

任务：

1. 将 `KnowledgeService.answer()` 改为调用 LLM adapter 的 text API，而不是假设 `.answer()` 方法。
2. Prompt 固定结构：
   - 业务问题；
   - 检索到的 Evidence（chunk id、文档、页码、内容）；
   - 明确“只能使用给定证据，不足则拒答”；
   - 要求引用 `[1]`、`[2]` 等 citation marker。
3. 保留 `CitationValidator`，验证失败时触发一次修复提示；仍失败则返回安全的 evidence-only 摘要或 abstain。
4. 把 provider latency、token usage、model、request id 写入结构化 trace，不记录敏感原文。
5. 无证据时禁止调用 LLM，直接走现有 `NO_EVIDENCE` 分支，避免无根据回答和无效成本。

### Phase C — Intent 与 Requirement 结构化理解

**目标：** 保留规则快速路径，同时让复杂表达进入 DeepSeek。

任务：

1. `classify_intent`：正则高置信命中直接返回；模糊/低置信文本调用 `IntentResult` 结构化输出。
2. `extract_task_patch`：正则提取结果作为候选，复杂文本调用 `TaskPatch` JSON 输出；禁止模型写入未知字段。
3. 所有模型结果执行：枚举校验、数值范围校验、字段白名单、冲突检测和 provenance 记录。
4. LLM 失败、超时、429、非法 JSON 时回退到确定性解析；若仍无法满足 Required Slot，继续现有 `interrupt()`，不猜测地区/数量。
5. 将 prompt、schema 版本和解析结果摘要写入可审计 metadata，避免把完整用户隐私写入日志。

### Phase D — 规则、建议与研究查询扩展

**目标：** 启用代码中已有但当前未注入的 LLM 扩展点。

任务：

1. `BusinessRuleService(llm=llm)` 注入 `OfficialRuleExtractor` 与 `ModelSuggestionGenerator`。
2. 官方规则抽取严格绑定检索 Evidence；缺少 evidence id、越权字段或把营销话术当官方要求时丢弃并告警。
3. Model Suggestion 只能生成 `SOFT`，必须引用现存 evidence，最多 5 条；确定性 validator 负责最终接受/拒绝。
4. `SearchQueryGenerator.generate_with_llm()` 仅生成有限 query variants，不得修改 hard constraints；使用预算和最大变体数限制。
5. 实际 Research Provider、Filter、Scoring、Entity Resolution 继续由程序控制，LLM 不可直接提升候选或分数。

### Phase E — 稳定性、成本与可运维性

任务：

1. 对 408/429/5xx/超时采用有界指数退避；认证、参数、Pydantic 校验错误不重试。
2. 增加 LLM 独立并发限制、请求预算、熔断和可选缓存；缓存 key 不包含明文 API Key。
3. 为每次调用生成 `llm_call_id`，关联 `thread_id`、`task_id`、`task_version`、node、schema_version。
4. 监控：调用成功率、p50/p95 延迟、输入/输出 token、429 数、解析失败数、fallback 数、NO_EVIDENCE 比例。
5. 明确数据策略：业务资料和用户消息是否允许发送至 DeepSeek，按部署环境配置；默认关闭完整内容 trace。

## 6. 预计修改文件清单

### 必改

- `app/providers/llm/factory.py`
- `app/providers/llm/fake.py`
- `app/providers/llm/base.py`（新增）
- `app/providers/llm/deepseek.py`（新增）
- `app/settings/production.py`
- `.env.example`
- `app/agent/dependencies.py`
- `app/main.py`
- `app/knowledge/services/knowledge_service.py`
- `app/agent/nodes/intent.py`
- `app/agent/subgraphs/requirement/nodes.py`
- `app/rules/service.py`
- `app/rules/extractor.py`
- `app/rules/suggestion.py`

### 建议新增

- `app/providers/llm/errors.py`
- `app/providers/llm/structured.py`
- `app/observability/llm_metrics.py`
- `tests/providers/test_deepseek_llm.py`
- `tests/providers/test_llm_factory.py`
- `tests/agent/test_llm_intent_fallback.py`
- `tests/agent/test_llm_task_patch.py`
- `tests/test_real_llm_contract.py`
- `tests/external/test_deepseek_external_smoke.py`
- `scripts/smoke_deepseek_llm.py`

## 7. 测试与验收计划

### 7.1 不联网单元测试（CI 必须通过）

- Factory：deepseek/openai-compatible/fake/unknown provider 行为；未知 provider 不得静默 Fake。
- Settings：开发环境可显式 Fake；生产环境缺 Key、错误 base URL、Fake provider 均拒绝启动。
- 请求契约：模型名、base URL、超时、重试、thinking/reasoning 参数正确传递；API Key 只出现在 Authorization header。
- Structured JSON：合法 JSON、空 content、截断 JSON、额外字段、非法枚举、类型错误和一次修复重试。
- QA：有证据才调用；CitationValidator 失败时安全降级；无证据不调用。
- Intent/TaskPatch：规则快速路径、LLM 回退、LLM 失败回退、Required Slot 中断。
- Rules/Suggestions：证据绑定、字段白名单、SOFT-only、最多 5 条。
- 安全：日志/异常/trace/checkpoint 不出现 Key 或 Authorization。

### 7.2 外部 DeepSeek smoke（显式执行，消耗额度）

用临时环境变量运行，不把 Key 写入 shell history、`.env` 或文件：

```bash
LLM_PROVIDER=deepseek \
LLM_MODEL=deepseek-flash \
LLM_BASE_URL=https://api.deepseek.com \
LLM_API_KEY="$DEEPSEEK_API_KEY" \
python scripts/smoke_deepseek_llm.py
```

Smoke 至少验证：

1. 普通文本请求返回非空 assistant content；
2. `deepseek-flash` 被服务端接受；
3. JSON mode 返回可被 Pydantic 校验的结果；
4. 超时/429 错误映射和脱敏符合预期；
5. 不启用 thinking 与启用 thinking 各有一条记录（若当前账号/模型支持）；
6. 不产生任何研究 Provider、数据库写入或用户可见的伪造 Lead。

### 7.3 Golden E2E

使用已存在的本地 Fake fixture 和单独的 DeepSeek credentialed run，各自标记结果：

```text
Fake regression     = 离线确定性回归，不证明真实质量
DeepSeek smoke/E2E  = 真实调用证据，结果可能随模型变化
```

必须覆盖：

- Business QA：证据回答、citation、无证据拒答；
- Lead Discovery：复杂自然语言 -> TaskPatch -> Required Slot -> Criteria -> Research；
- Task Modification：版本递增、部分重执行、旧版本不可覆盖；
- Export/UI：仍消费冻结 Delivery Snapshot；
- 重启恢复：LLM 调用失败或 interrupt 后恢复不得重复非幂等副作用。

## 8. Release Gate（必须全部通过）

| Gate | 通过标准 |
|---|---|
| Provider correctness | DeepSeek API 请求契约与 SDK 版本锁定，模型名为 `deepseek-flash` |
| No silent fake | 生产配置错误立即失败；真实 provider 失败不返回 Fake 业务结论 |
| Structured safety | 所有 LLM 决策通过 Pydantic、白名单、枚举和 provenance 校验 |
| Grounded QA | 仅基于 Evidence 回答，Citation 校验失败安全降级，无证据不调用 |
| Graph integrity | `thread_id`/`task_id` 分离，LLM 不绕过 interrupt、版本围栏和幂等边界 |
| Deterministic core | Hard Filter、实体、评分、交付快照结果不由 LLM 直接决定 |
| Resilience | timeout/429/5xx 有界重试、熔断、fallback 和可观测指标齐全 |
| Security | Secret scan、日志脱敏、workspace/SSRF/注入回归全部通过 |
| Real smoke | 使用授权 Key 完成普通、JSON、失败路径 smoke；记录真实响应元数据，不记录密钥 |
| Full acceptance | 现有 `FINAL_ACCEPTANCE_REPORT.md` 的 18 个 Mandatory Gates 重新执行，所有阻塞项为 PASS |

任何一项为 `NOT_RUN`、`PARTIAL` 或 `FAIL`，Release Decision 必须为 `NO-GO`。

## 9. 实施顺序与完成定义

推荐顺序：

```text
A Provider/Config/Security
  -> B Business QA
  -> C Intent/Requirement
  -> D Rules/Research extensions
  -> E Reliability/Observability
  -> Unit/External Smoke
  -> Golden E2E
  -> Final Acceptance
```

每个阶段完成定义：

- 代码、测试、配置说明和回滚方式齐全；
- 不破坏现有 Fake 离线测试与确定性评测；
- 新增真实链路有可重复命令和脱敏日志；
- 发现阻塞项立即记录到 `FINAL_ACCEPTANCE_REPORT.md`，不以“模型可返回文本”替代验收。

## 9.1 建议的 Git Commit 拆分

仓库历史采用简短的 Conventional Commits 风格，例如 `feat(agent): ...`、`fix(config): ...`、`test(e2e): ...`、`docs: ...`。建议按依赖顺序拆分，避免把 provider、业务节点、测试和 Release 文档混在一个大 commit 中：

| 顺序 | 建议 commit subject | 主要内容 | 完成条件 |
|---:|---|---|---|
| 1 | `chore(llm): define DeepSeek provider configuration contract` | Settings 新增模型、URL、超时、重试、thinking、token 上限；更新 `.env.example` | 配置 schema 和生产校验测试通过 |
| 2 | `feat(llm): add DeepSeek Flash chat adapter` | 新增 LLM protocol、DeepSeek adapter、factory 分支、错误映射 | 可创建 `deepseek-flash` 客户端；未知 provider 不再静默 Fake |
| 3 | `test(llm): cover DeepSeek request and JSON contracts` | MockTransport 请求契约、JSON mode、Pydantic 解析、空响应/截断/非法字段测试 | 不联网测试覆盖成功与失败路径 |
| 4 | `fix(runtime): inject one LLM instance across agent services` | `AgentDependencies`、`main.py`、`BusinessRuleService`、`KnowledgeService` 统一注入；修复传入 Settings 未贯穿的问题 | 各服务使用同一 provider；Fake 测试仍可注入 |
| 5 | `feat(rag): ground business answers with DeepSeek Flash` | QA prompt、evidence payload、citation 修复/降级、无证据不调用 | Business QA 真实 adapter 闭环且 Citation Gate 通过 |
| 6 | `feat(agent): add structured intent and task patch fallback` | IntentResult、TaskPatch JSON 输出、规则快速路径、失败回退、provenance | 复杂表达可解析；缺槽位仍触发 interrupt |
| 7 | `feat(rules): enable evidence-bound DeepSeek extraction` | 注入 OfficialRuleExtractor、ModelSuggestionGenerator，增加 evidence/字段/Soft-only 约束 | 官方规则和模型建议不能越权或脱离证据 |
| 8 | `feat(research): gate bounded LLM query generation` | 可选 SearchQueryGenerator LLM 路径、变体上限、预算与 hard constraint 围栏 | 查询生成不改变 Criteria；默认确定性路径可回退 |
| 9 | `fix(llm): harden timeout retry and secret redaction` | 限流/超时/5xx 退避、熔断、usage 指标、日志/trace/checkpoint 脱敏 | 故障测试通过；不存在静默伪造业务结果 |
| 10 | `test(e2e): verify DeepSeek golden workflow` | 外部 smoke、QA/Lead Discovery/Mutation/Restart/Export 验收脚本与脱敏摘要 | 真实 Key 运行结果可复现；Fake 与真实结果分开标记 |
| 11 | `docs: record DeepSeek real LLM acceptance` | 更新架构、部署、运行手册和 `FINAL_ACCEPTANCE_REPORT.md`，记录实际模型、延迟、token、失败率 | 证据齐全；未执行项明确写 `NOT_RUN` |
| 12 | `chore(release): prepare v1.0.0 real LLM configuration` | 仅在全部 Mandatory Gates 为 PASS 后更新版本/Release 配置 | 不包含密钥；Release Decision 为 GO |

### Commit 编排规则

- 每个 commit 保持单一主题，subject 使用历史中的小写 scope 和动词短语，不在 subject 中写凭据、环境值或临时机器信息。
- 第 1～4 个 commit 应先于业务接入合并；第 5～8 个 commit 可按阶段独立回滚；第 9～10 个 commit 必须在真实 smoke 前完成。
- 第 11 个文档 commit 只记录实际执行结果，不预先写 `PASS`；第 12 个 Release commit 不得与功能实现同批提交。
- 真实 API Key 只能通过环境变量或 Secret Manager 注入；任何疑似泄漏都应先撤销 Key，再继续提交和验收。
- 建议每个 commit 单独运行相关测试，并在 PR 描述中列出从第 1 个到第 10 个 commit 的依赖顺序和对应 Release Gate。

## 10. 配置与密钥处置

文档、代码和示例只允许出现以下占位配置：

```dotenv
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-flash
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=2
LLM_REASONING_EFFORT=
LLM_THINKING_TYPE=disabled
```

用户在本次对话中粘贴的 API Key 已属于敏感凭据，不能写入仓库；实施前应立即在 DeepSeek 平台撤销并重新生成，然后通过本机环境变量或 Secret Manager 注入。完成 smoke 后继续轮换，避免把短期测试凭据带入长期运行环境。

## 11. 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| DeepSeek 参数/模型变更 | provider contract test + smoke；模型名集中配置 | 切回显式 `LLM_PROVIDER=fake`（仅开发/测试）或上一稳定兼容 provider |
| 延迟/成本上升 | 非流式默认关闭 thinking、token 上限、预算/熔断、缓存 | 关闭 LLM 扩展开关，仅保留 QA/必要结构化节点 |
| 结构化输出不稳定 | JSON mode、schema 示例、Pydantic、一次修复重试、确定性 fallback | 禁用对应 LLM 节点，保留正则/规则路径 |
| 外部数据泄露 | 最小化 prompt、脱敏 trace、部署前数据处理评审 | 关闭真实 provider，恢复离线模式并撤销 Key |
| 真实链路绕过业务约束 | adapter/节点只产生候选；Hard Filter/Score/Delivery 仍由程序执行 | 阻断 Release，回到 Fake regression 验证 |

## 12. 最终交付物

- 本开发计划；
- DeepSeek provider adapter 与配置/密钥说明；
- 真实 LLM 单元测试、外部 smoke 脚本与脱敏结果；
- 更新后的架构、部署、运行手册；
- `FINAL_ACCEPTANCE_REPORT.md` 中的真实调用证据与 18 Gate 结果；
- 只有在所有 Mandatory Gates 为 PASS 后，才允许准备 `v1.0.0` tag/release。

## 13. 本次实施记录（2026-09-14）

已完成并验证：

- 新增 `DeepSeekChatModel` 与 provider-neutral LLM protocol；使用 `langchain-openai` 的 OpenAI-compatible 客户端。
- `create_chat_model()` 支持显式 `deepseek` provider，未知 provider 抛错；Fake 仅保留为显式离线路径。
- Settings 增加超时、重试、thinking、reasoning effort、completion token 和 structured retry 配置，并在 production 对 DeepSeek 配置做强校验。
- `AgentDependencies`、Knowledge QA、Business Rule Extractor、Model Suggestion、Intent 和 Requirement 共用同一 LLM 实例。
- Business QA 保留无证据门禁与 CitationValidator；Intent/TaskPatch 保留确定性快速路径，复杂文本才进入结构化 LLM 回退。
- 新增离线 provider 单元测试与 `scripts/smoke_deepseek_llm.py`。
- 使用临时环境变量完成一次真实 `deepseek-flash` 文本 + JSON smoke，结果为 `ok=true`；未记录响应正文或 API Key。
- 使用合成知识片段完成一次真实 Business QA 闭环，Evidence count=1、Citation count=1。

本轮已补齐：LLM 调用并发上限、进程内熔断与 LLM 指标；现有 Redis 分布式限流/熔断、任务 SSE、Golden API/UI E2E 已复用并完成回归。仍需在 Release Candidate 中完成真实 Intent/Requirement/Rules/Research Golden E2E、LLM SSE 逐 token 输出（当前任务事件 SSE 不等同于 LLM token 流），以及 `FINAL_ACCEPTANCE_REPORT.md` 中的 18 个 Mandatory Gates 复验。未完成项不能标记为 Release PASS。

## 13.1 后续 Release Commit 计划（执行顺序）

当前工作区尚未创建实际 commit。建议按以下顺序提交，并保持每个 commit 单一主题：

1. `chore(llm): define DeepSeek provider configuration contract` — 配置字段、`.env.example`、生产校验。
2. `feat(llm): add DeepSeek Flash chat adapter` — provider protocol、DeepSeek adapter、factory。
3. `test(llm): cover DeepSeek request and JSON contracts` — 请求契约、结构化输出、Circuit/并发单测。
4. `fix(runtime): inject one LLM instance across agent services` — AgentDependencies、QA、Rules、Intent、Requirement 注入。
5. `feat(rag): ground business answers with DeepSeek Flash` — Evidence prompt、Citation Gate、无证据短路。
6. `feat(agent): add structured intent and task patch fallback` — IntentResult、TaskPatch、失败回退与 provenance。
7. `feat(rules): enable evidence-bound DeepSeek extraction` — OfficialRule/ModelSuggestion 真实调用与确定性约束。
8. `feat(research): gate bounded LLM query generation` — SearchQuery 受限生成、hard constraint 围栏和预算。
9. `fix(llm): harden timeout retry and secret redaction` — 并发上限、熔断、指标、脱敏与故障测试。
10. `test(e2e): verify DeepSeek golden workflow` — 真实 smoke、Intent/Requirement/Rules/Research/QA/Mutation/Export/Restart。
11. `docs: record DeepSeek real LLM acceptance` — 记录真实调用元数据、测试结果、NOT_RUN 项与回滚说明。
12. `chore(release): prepare v1.0.0 real LLM configuration` — 仅在 18 个 Mandatory Gates 全部 PASS 后更新版本和 Release 配置。

每个 commit 合并前必须执行对应测试；第 10 个 commit 的真实结果不得与 Fake fixture 混写；第 11 个 commit 不得预先声明 PASS；第 12 个 commit 不得包含任何凭据。
