# Enterprise Sales Intelligence Agent（政企营销智能体）

**Enterprise Sales Intelligence Agent（政企营销智能体）** 是一套面向政企营销场景的状态化智能 Agent。系统通过 RAG 获取产品、套餐和营销活动知识，结合多轮对话形成结构化营销任务，并编排企业信息、地图、Web Search 与企业官网等多源工具，实现企业潜客发现、情报补全、实体归一化、证据核验、潜客评分及 Excel 交付。

## Phase 1 范围

本阶段只实现 LangGraph Agent Runtime 与离线 Mock Workflow：多 Intent 入口、结构化 `LeadTask`、Required Slot 校验、真实 `interrupt()` / `Command(resume=...)`、MemorySaver、Mock Business Planning、Mock Research、Mock Lead Scoring、Mutation Skeleton 和 FastAPI `/api/chat`。Mock BusinessQA、Mock Research、Mock Scoring 均不是生产能力。

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

## 已完成与未实现

已完成：Phase 1 Runtime、MainGraph、五个 SubGraph、Intent/Mutation Router、任务版本、MemorySaver、FastAPI 和离线测试。

尚未实现：真实 RAG、PostgreSQL、Redis、真实企业搜索、地图 API、官网抓取、正式 Entity Resolution、Evidence Verification、生产级评分、Excel 文件导出、Langfuse 和生产 Checkpointer。这些属于后续 Phase。
