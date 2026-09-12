from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime, timedelta

from sqlalchemy import BigInteger, DateTime, String, bindparam, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.runtime.models import ExecutionRun, ExecutionRunStatus, RunAlreadyClaimedError

ACTIVE_STATUSES = {ExecutionRunStatus.CLAIMED, ExecutionRunStatus.RUNNING}


class InMemoryExecutionCoordinator:
    def __init__(self) -> None:
        self._runs: dict[str, ExecutionRun] = {}
        self._requests: dict[tuple[str, str], str] = {}
        self._active: dict[tuple[str, str], str] = {}
        self._fences: dict[tuple[str, str], int] = {}
        self._lock = asyncio.Lock()

    async def claim(
        self,
        *,
        request_id: str,
        thread_id: str,
        workspace_id: str,
        user_id: str,
        owner: str,
        lease_seconds: int,
        trace_id: str,
    ) -> ExecutionRun:
        key = (workspace_id, thread_id)
        async with self._lock:
            prior_id = self._requests.get((workspace_id, request_id))
            if prior_id:
                prior = self._runs[prior_id]
                if prior.status in ACTIVE_STATUSES:
                    raise RunAlreadyClaimedError(thread_id)
                return deepcopy(prior)
            now = datetime.now(UTC)
            active_id = self._active.get(key)
            active = self._runs.get(active_id or "")
            if (
                active
                and active.status in ACTIVE_STATUSES
                and active.lease_expires_at
                and active.lease_expires_at > now
            ):
                raise RunAlreadyClaimedError(thread_id)
            if active and active.status in ACTIVE_STATUSES:
                self._runs[active.run_id] = active.model_copy(update={"status": ExecutionRunStatus.RECOVERABLE})
            fence = self._fences.get(key, 0) + 1
            run = ExecutionRun(
                request_id=request_id,
                thread_id=thread_id,
                workspace_id=workspace_id,
                user_id=user_id,
                status=ExecutionRunStatus.RUNNING,
                lease_owner=owner,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                heartbeat_at=now,
                fence_token=fence,
                trace_id=trace_id,
            )
            self._runs[run.run_id] = run
            self._requests[(workspace_id, request_id)] = run.run_id
            self._active[key] = run.run_id
            self._fences[key] = fence
            return deepcopy(run)

    async def heartbeat(self, run_id: str, fence_token: int, lease_seconds: int) -> bool:
        async with self._lock:
            run = self._runs.get(run_id)
            if not run or run.fence_token != fence_token or run.status not in ACTIVE_STATUSES:
                return False
            now = datetime.now(UTC)
            self._runs[run_id] = run.model_copy(
                update={"heartbeat_at": now, "lease_expires_at": now + timedelta(seconds=lease_seconds)}
            )
            return True

    async def can_promote(self, run_id: str, fence_token: int) -> bool:
        async with self._lock:
            run = self._runs.get(run_id)
            if not run:
                return False
            active = self._active.get((run.workspace_id, run.thread_id))
            return active == run_id and run.fence_token == fence_token and run.status in ACTIVE_STATUSES

    def can_promote_cached(self, run_id: str, fence_token: int) -> bool:
        run = self._runs.get(run_id)
        return bool(
            run
            and self._active.get((run.workspace_id, run.thread_id)) == run_id
            and run.fence_token == fence_token
            and run.status in ACTIVE_STATUSES
        )

    async def finish(
        self,
        run_id: str,
        fence_token: int,
        status: ExecutionRunStatus,
        *,
        response_data: dict | None = None,
        error_code: str | None = None,
    ) -> bool:
        async with self._lock:
            run = self._runs.get(run_id)
            if not run or run.fence_token != fence_token:
                return False
            now = datetime.now(UTC)
            self._runs[run_id] = run.model_copy(
                update={
                    "status": status,
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "finished_at": now
                    if status not in {ExecutionRunStatus.WAITING_INTERRUPT, ExecutionRunStatus.RECOVERABLE}
                    else None,
                    "response_data": response_data,
                    "error_code": error_code,
                }
            )
            self._active.pop((run.workspace_id, run.thread_id), None)
            return True

    async def get(self, run_id: str) -> ExecutionRun | None:
        async with self._lock:
            value = self._runs.get(run_id)
            return deepcopy(value) if value else None


class PostgresExecutionCoordinator:
    """Atomic Postgres lease coordination using a transaction-scoped advisory lock."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self.session_factory = session_factory

    async def claim(
        self,
        *,
        request_id: str,
        thread_id: str,
        workspace_id: str,
        user_id: str,
        owner: str,
        lease_seconds: int,
        trace_id: str,
    ) -> ExecutionRun:
        async with self.session_factory() as session, session.begin():
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:scope))"), {"scope": f"{workspace_id}:{thread_id}"}
            )
            prior = (
                (
                    await session.execute(
                        text(
                            "SELECT * FROM execution_runs WHERE workspace_id=:workspace_id AND request_id=:request_id"
                        ),
                        {"workspace_id": workspace_id, "request_id": request_id},
                    )
                )
                .mappings()
                .first()
            )
            if prior:
                return self._from_row(prior)
            active = (
                (
                    await session.execute(
                        text(
                            """SELECT * FROM execution_runs
                       WHERE workspace_id=:workspace_id AND thread_id=:thread_id
                         AND status IN ('CLAIMED','RUNNING')
                       ORDER BY fence_token DESC LIMIT 1 FOR UPDATE"""
                        ),
                        {"workspace_id": workspace_id, "thread_id": thread_id},
                    )
                )
                .mappings()
                .first()
            )
            now = datetime.now(UTC)
            if active and active["lease_expires_at"] > now:
                raise RunAlreadyClaimedError(thread_id)
            if active:
                await session.execute(
                    text("UPDATE execution_runs SET status='RECOVERABLE', lease_owner=NULL WHERE run_id=:run_id"),
                    {"run_id": active["run_id"]},
                )
            row = (
                (
                    await session.execute(
                        text(
                            """INSERT INTO execution_runs
                       (run_id,request_id,thread_id,workspace_id,user_id,status,
                        lease_owner,lease_expires_at,heartbeat_at,trace_id)
                       VALUES (gen_random_uuid(),:request_id,:thread_id,:workspace_id,
                        :user_id,'RUNNING',:owner,:expires,:now,:trace_id)
                       RETURNING *"""
                        ),
                        {
                            "request_id": request_id,
                            "thread_id": thread_id,
                            "workspace_id": workspace_id,
                            "user_id": user_id,
                            "owner": owner,
                            "expires": now + timedelta(seconds=lease_seconds),
                            "now": now,
                            "trace_id": trace_id,
                        },
                    )
                )
                .mappings()
                .one()
            )
            return self._from_row(row)

    async def heartbeat(self, run_id: str, fence_token: int, lease_seconds: int) -> bool:
        async with self.session_factory() as session, session.begin():
            result = await session.execute(
                text(
                    """UPDATE execution_runs
                       SET heartbeat_at=now(),
                           lease_expires_at=now() + make_interval(secs => :seconds)
                       WHERE run_id=:run_id AND fence_token=:fence
                         AND status IN ('CLAIMED','RUNNING')"""
                ),
                {"run_id": run_id, "fence": fence_token, "seconds": lease_seconds},
            )
            return result.rowcount == 1

    async def can_promote(self, run_id: str, fence_token: int) -> bool:
        async with self.session_factory() as session:
            value = await session.scalar(
                text(
                    """SELECT EXISTS(SELECT 1 FROM execution_runs
                       WHERE run_id=:run_id AND fence_token=:fence
                         AND status IN ('CLAIMED','RUNNING')
                         AND lease_expires_at > now())"""
                ),
                {"run_id": run_id, "fence": fence_token},
            )
            return bool(value)

    async def finish(
        self,
        run_id: str,
        fence_token: int,
        status: ExecutionRunStatus,
        *,
        response_data: dict | None = None,
        error_code: str | None = None,
    ) -> bool:
        async with self.session_factory() as session, session.begin():
            statement = text(
                """UPDATE execution_runs
                   SET status=:status, lease_owner=NULL, lease_expires_at=NULL,
                       finished_at=:finished_at,
                       response_json=:response, error_code=:error
                   WHERE run_id=:run_id AND fence_token=:fence"""
            ).bindparams(
                bindparam("status", type_=String(32)),
                bindparam("finished_at", type_=DateTime(timezone=True)),
                bindparam("response", type_=JSONB),
                bindparam("error", type_=String(80)),
                bindparam("run_id", type_=UUID(as_uuid=True)),
                bindparam("fence", type_=BigInteger),
            )
            result = await session.execute(
                statement,
                {
                    "status": status.value,
                    "finished_at": datetime.now(UTC)
                    if status
                    in {
                        ExecutionRunStatus.COMPLETED,
                        ExecutionRunStatus.FAILED,
                        ExecutionRunStatus.SUPERSEDED,
                    }
                    else None,
                    "response": response_data,
                    "error": error_code,
                    "run_id": run_id,
                    "fence": fence_token,
                },
            )
            return result.rowcount == 1

    @staticmethod
    def _from_row(row) -> ExecutionRun:
        values = {key: row[key] for key in ExecutionRun.model_fields if key in row}
        values["run_id"] = str(row["run_id"])
        if row.get("task_id") is not None:
            values["task_id"] = str(row["task_id"])
        values["response_data"] = row.get("response_json")
        return ExecutionRun(**values)
