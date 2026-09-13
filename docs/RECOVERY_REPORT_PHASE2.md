# Restart / Recovery / Backup Restore 第二阶段验收报告

**执行时间：** 2026-09-13（Asia/Shanghai）
**分支：** `release/v1.0.0`
**基线 HEAD：** `4747044`
**修复 Commit：** `7d674b3` (`fix(recovery): harden restart and shutdown recovery`)
**Provider 模式：** deterministic fake；503/Timeout 为故障注入，不是外部 Provider E2E
**Recovery 专项结论：** **PASS**
**仓库整体 Release 结论：** **NO-GO**（本阶段之外的既有 Mandatory Gates 与全仓 Ruff 基线尚未全部通过）

## 验收结论

| 验收项 | 结果 | 真实证据 |
|---|---|---|
| Restart Resume | **PASS** | 恢复同一 `thread_id`/Task/Version checkpoint；中途失败的 resume request 以新 fence 重新取得原 run，最终 `COMPLETED` |
| Clarification Restart | **PASS** | Task `155fd207-22f2-4a77-aa75-846b3b9164aa` 从 `WAITING_USER` 跨进程恢复到 Version 2 / `COMPLETED` |
| Graceful Shutdown | **PASS** | 活跃请求在 SIGTERM 后约 3.8 秒完成；日志包含 request `200 OK`、`Application shutdown complete`、`Finished server process`；未用 SIGKILL |
| Backup Restore | **PASS** | PostgreSQL 16 custom dump，258 TOC entries；全新 DB 恢复成功；13 张关键表行数与主键摘要一致 |
| Business Artifact Restore | **PASS** | 恢复实例实际读取 Task/Lead/Evidence/Score Explain/Export，并下载 XLSX；备份内未完成任务可继续 |
| Duplicate Side Effect | **NO** | Clarification Task、Criteria、SearchPlan、ResearchRun、DeliverySnapshot、Export 均为 1；Task Version 为 1/2 各一条；Event 各一条 |

本阶段要求的核心恢复场景没有遗留 FAIL。Recovery 专项可以关闭，但该结论不自动覆盖仓库其他 Release 门禁。

## 发现与修复

1. **Execution request/lease 幂等错误。** PostgreSQL 下相同 active `request_id` 可能复用 run/fence 再执行；过期请求也无法安全重领。现在 active duplicate 返回冲突，过期/FAILED/RECOVERABLE 请求重领原 run 并分配新 fence，已完成或等待响应直接重放；PostgreSQL 增加 request 级 advisory lock。
2. **Shutdown admission control 缺失。** `/api/chat` 现在在 `accepting_work=false` 时返回 `503 SERVICE_SHUTTING_DOWN` 和 `Retry-After: 1`。
3. **Redis/LangGraph 跨 event loop 阻塞。** Research/Verification/Reexecution provider 节点原先在线程中 `asyncio.run()`，Redis client 却绑定 Uvicorn 主 loop。节点现使用双 sync/async `RunnableLambda`，API 走原生 async，保留同步 `graph.invoke()` 兼容。
4. **非 interrupt 的中途 checkpoint 无法从 API 恢复。** 当 `snapshot.next` 非空时，API 现在用 `graph.ainvoke(None, config)` 继续持久化执行，而不是把重试文本当作新输入。
5. **Research runtime 重启后缺失。** `_runtimes` 原为进程内状态；现在根据持久化 ResearchRun、Plan、ToolRun 和 Budget 懒重建，并重新绑定当前 cache/rate-limit/circuit-breaker。
6. **Shutdown cleanup 会短路。** checkpointer、Langfuse、Redis、async PostgreSQL、sync PostgreSQL 现在逐项隔离关闭，单个 closer 失败不会阻止其余资源释放。

## Restart / Clarification 证据

- Thread：`phase2-clarification-real`
- Task：`155fd207-22f2-4a77-aa75-846b3b9164aa`
- 初始 request：`phase2-clarification-initial`，结果 `WAITING_INTERRUPT`，fence `11`
- Resume request：`phase2-clarification-resume`；失败后以同一 request/run 重领，最终 fence `17`、`COMPLETED`
- 最终 Task Version：`2`；Task 行 `1`，Version 行 `2`，distinct Version `2`
- 最终 checkpoint messages：恰好 `2` 条 HumanMessage，内容分别为“帮我找集团V网客户”和“上海松江，50家”
- Side Effect：Criteria `1`、SearchPlan `1`、ResearchRun `1`、Candidate `10`、SourceRecord `30`、Score `5`、DeliverySnapshot `1`、Export `1`
- Durable Event：`CLARIFICATION_REQUIRED=1`、`FINAL=1`

第一次真实 resume 暴露 Redis event-loop 阻塞，并在 SIGTERM 后取消。应用修复后，用同一 thread/request 从非 interrupt 的中途 checkpoint 继续，未创建新 Task，最终完成全链路。

## Graceful Shutdown 证据

- Thread：`phase2-graceful-active`
- Task：`1f7fc3e5-95b4-4da8-9893-614a21d906aa`
- 在 Business Planning 阶段发送 SIGTERM。
- 活跃 HTTP 请求继续运行并约 3.8 秒后返回 `200 OK`。
- Uvicorn 随后记录 `Application shutdown complete` 和 `Finished server process`。
- 所有 execution lease 最终释放；未使用 SIGKILL。
- Admission-control 与逐资源 cleanup 另有单元测试覆盖。

修复前同场景超过 graceful timeout，并记录 Redis event-loop shutdown 错误；修复后复测通过。

## Backup / Restore 证据

最终 dump：`/tmp/phase2_recovery_20260913.dump`（PostgreSQL 容器内）
源库：`phase2_recovery_source_20260913`
恢复库：`phase2_recovery_restore_20260913`
恢复参数：`--no-owner --no-acl --no-comments --exit-on-error`

首次 restore 在 `COMMENT ON EXTENSION vector` 因扩展所有权失败。复测在全新 DB 中由管理员预创建 `vector`，业务用户恢复所有业务对象，并跳过非业务 COMMENT；restore 成功。

| 业务对象 | 源行数 | 恢复行数 | 主键集合摘要 |
|---|---:|---:|---|
| Task (`lead_tasks`) | 8 | 8 | 相同 |
| Task Version (`lead_task_versions`) | 14 | 14 | 相同 |
| Criteria (`lead_criteria_snapshots`) | 6 | 6 | 相同 |
| SearchPlan (`research_search_plans`) | 6 | 6 | 相同 |
| Candidate (`enterprise_candidates`) | 35 | 35 | 相同 |
| SourceRecord (`research_source_records`) | 139 | 139 | 相同 |
| Evidence (`enterprise_evidence`) | 616 | 616 | 相同 |
| ResolvedField (`resolved_fields`) | 286 | 286 | 相同 |
| VerifiedProfile (`verified_enterprise_profiles`) | 22 | 22 | 相同 |
| LeadScore (`lead_scores`) | 22 | 22 | 相同 |
| DeliverySnapshot (`delivery_snapshots`) | 3 | 3 | 相同 |
| Export (`exports`) | 3 | 3 | 相同 |
| Checkpoint (`checkpoints`) | 516 | 516 | 相同 |

代表对象：Task `155fd207-22f2-4a77-aa75-846b3b9164aa`、Lead `2fc4dc50-e57c-458e-8831-3562e3a9117d`、Evidence `6327550a-385d-443a-a488-630bfb387d23`、Score `3413076d-e647-4971-91f6-3f86f4732c37`、Export `08ad9413-4d09-4887-9c36-a2d5caa0839f`。

恢复实例 API 实测均为 HTTP 200。下载文件为 15,480 bytes，SHA-256 为 `901b201acf3ca24e0a6e6c099f25a2318dc50d46741656195da0241188373a35`，与 Export metadata 和源文件一致。

备份内等待任务 `47d555d8-3071-44c2-acc4-9f104ba88993` 在恢复库以同一 session 继续到 `COMPLETED`，Version 1/2 各一条。相同 resume `request_id` 再次调用后，规范化 JSON 响应 hash 相同，Task/Version/Criteria/Research/Score/Lease 数量不增加；最终 checkpoint 只有原请求和一次澄清输入两条消息。

## Fault Cases

| 故障 | 结果 | 验证方式 |
|---|---|---|
| Redis Down | **PASS** | 无 Redis 的真实 PostgreSQL 完整任务，在全新应用中恢复并完成；原历史 Task/Export 与恢复任务仍可读 |
| Langfuse Down | **PASS** | 注入 observation/flush 失败；Chat 不失败，cleanup 不阻断其他资源 |
| Provider 503 | **PASS** | 注入 retryable HTTP 503，两次失败后第三次成功，retry 次数符合配置 |
| Provider Timeout | **PASS** | 注入超时被边界化为 `PROVIDER_TIMEOUT`，达到阈值后 circuit open 并拒绝下一次调用 |

故障选择测试：`7 passed`。外部 Provider 凭据未提供，因此 503/Timeout 仅声明为确定性故障注入。

## 回归结果

- `pytest -q`：`173 passed, 19 skipped, 1 deselected`。
- `pytest -q -m 'integration or recovery or fault'`（PostgreSQL + Redis）：`24 passed, 1 skipped, 168 deselected`。
- 本次 12 个变更文件 `ruff check`：PASS。
- `git diff --check`：PASS。
- `ruff check .`：FAIL，`547` 个既有问题，主要为未改文件的 E501/I001/E702/F401；本阶段未做无关的全仓格式化。

## Release 判定

**Recovery 专项：PASS。** Restart/Resume、Clarification Restart、Graceful Shutdown、Full Backup/Restore、Business Artifact Restore 和四类故障均有真实复测证据。

**仓库整体 Release：NO-GO。** 本报告只关闭第二阶段 Recovery 门禁；既有 Final Acceptance 中的真实外部 Provider E2E、完整浏览器 UI replay、production-compose provider smoke 仍未闭环，同时当前全仓 Ruff 基线失败。满足所有 Mandatory Gates 后才能授权 tag/release。
