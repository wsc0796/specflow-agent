"""Two bounded process-local resource lanes, separate from workflow topology."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable, Iterable
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from threading import Event, Lock, local
from typing import Any

from specflow.policy.models import ExecutionLanePolicy, SpecFlowError

_executing = local()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class LaneAdmissionError(SpecFlowError):
    def __init__(self, lane: str, reason: str = "capacity") -> None:
        super().__init__(
            "LANE_SATURATED",
            "Execution lane capacity unavailable.",
            retryable=False,
            details={"lane": lane, "reason": reason},
        )


class LaneFuture(Future):
    """Public result plus internal physical-release acknowledgement."""

    def __init__(self) -> None:
        super().__init__()
        self._settled = Event()
        self._deadline_cancel = False


@dataclass(frozen=True)
class LaneSnapshot:
    lane: str
    submitted: int = 0
    started: int = 0
    completed: int = 0
    active: int = 0
    queued: int = 0
    rejected: int = 0
    cancelled: int = 0
    submitted_at: str = ""
    started_at: str = ""
    completed_at: str = ""


@dataclass(eq=False)
class _Job:
    future: LaneFuture
    operation: Callable[[], Any] = field(repr=False)
    deadline: float | None = None
    phase: str = "new"
    cancel_notified: bool = False


class _Lane:
    def __init__(self, name, limits, clock, wall_clock, executor_factory):
        self.name = name
        self.limits = limits
        self.clock = clock
        self.wall_clock = wall_clock
        self.lock = Lock()
        self.closed = False
        self._broken = False
        self._executor_factory = executor_factory
        self.queue: deque[_Job] = deque()
        self.active: set[_Job] = set()
        self.stats = LaneSnapshot(name)
        self.executor = executor_factory(
            max_workers=limits.max_active, thread_name_prefix=f"specflow-{name}"
        )

    def submit(self, operation, deadline):
        with self.lock:
            if self._broken and not self.active and not self.closed:
                self._renew_executor()
            if (
                self.closed
                or self._broken
                or getattr(_executing, "lane", None) is self
                or (
                    len(self.active) >= self.limits.max_active
                    and len(self.queue) >= self.limits.queue_capacity
                )
            ):
                self.stats = replace(self.stats, rejected=self.stats.rejected + 1)
                raise LaneAdmissionError(self.name)
            future = LaneFuture()
            job = _Job(future, operation, deadline)
            future.add_done_callback(
                lambda done: self._cancelled(job) if done.cancelled() else None
            )
            if len(self.active) < self.limits.max_active:
                if not self._dispatch(job):
                    self.stats = replace(self.stats, rejected=self.stats.rejected + 1)
                    raise LaneAdmissionError(self.name, "submission")
            else:
                job.phase = "queued"
                self.queue.append(job)
            self.stats = replace(
                self.stats, submitted=self.stats.submitted + 1, submitted_at=self.wall_clock()
            )
        return future

    def _dispatch(self, job):
        if self._broken:
            self._renew_executor()
            if self._broken:
                job.phase = "aborted"
                return False
        job.phase = "dispatched"
        self.active.add(job)
        try:
            self.executor.submit(self._execute, job)
        except BaseException as error:
            self.active.remove(job)
            # submit can enqueue before Thread.start raises. Revoking this
            # ticket prevents that abandoned wrapper from executing later.
            job.phase = "aborted"
            self._broken = True
            if not self.active:
                self._renew_executor()
            if not isinstance(error, Exception):
                raise
            return False
        return True

    def _renew_executor(self):
        # Never replace a pool owning accepted active work. Block new dispatch
        # until it drains, then discard abandoned native queue entries. This
        # bounds failed-submit tombstones without resubmitting rejected work.
        if self.active:
            return
        self.executor.shutdown(wait=False, cancel_futures=True)
        try:
            self.executor = self._executor_factory(
                max_workers=self.limits.max_active, thread_name_prefix=f"specflow-{self.name}"
            )
        except Exception:
            return
        self._broken = False

    def _cancelled(self, job):
        # Future.cancel invokes callbacks after releasing its condition lock.
        with self.lock:
            if job.phase == "queued":
                self.queue.remove(job)
                job.phase = "terminal"
                self.stats = replace(
                    self.stats,
                    cancelled=self.stats.cancelled + 1,
                    completed_at=self.wall_clock(),
                )
                job.future._settled.set()
            # Notify concurrent.futures wait/as_completed even when the removed
            # queued item will never be picked up by an executor worker.
            self._start_or_notify(job)

    @staticmethod
    def _start_or_notify(job):
        if job.cancel_notified:
            return False
        running = job.future.set_running_or_notify_cancel()
        if not running:
            job.cancel_notified = True
        return running

    def _execute(self, job):
        with self.lock:
            if job.phase != "dispatched":
                return
        result = None
        failure = None
        previous = getattr(_executing, "lane", None)
        try:
            if job.deadline is not None and self.clock() >= job.deadline:
                job.future._deadline_cancel = True
                job.future.cancel()
            with self.lock:
                running = self._start_or_notify(job)
                if running:
                    job.phase = "running"
                    self.stats = replace(
                        self.stats, started=self.stats.started + 1, started_at=self.wall_clock()
                    )
            if running:
                _executing.lane = self
                result = job.operation()
        except BaseException as error:
            failure = error
        finally:
            _executing.lane = previous
            self._finish(job, result, failure)

    def _finish(self, job, result, failure):
        failed_submissions = []
        with self.lock:
            self.active.remove(job)
            job.phase = "terminal"
            cancelled = job.future.cancelled()
            self.stats = replace(
                self.stats,
                cancelled=self.stats.cancelled + int(cancelled),
                completed=self.stats.completed + int(not cancelled),
                completed_at=self.wall_clock(),
            )
            if self._broken and not self.active and not self.closed:
                self._renew_executor()
            while (
                not self.closed
                and self.queue
                and len(self.active) < self.limits.max_active
                and (not self._broken or not self.active)
            ):
                queued = self.queue.popleft()
                dispatch_error = None
                try:
                    dispatched = self._dispatch(queued)
                except BaseException as error:
                    dispatched = False
                    dispatch_error = error
                if not dispatched:
                    failed = self._start_or_notify(queued)
                    self.stats = replace(
                        self.stats,
                        completed=self.stats.completed + int(failed),
                        cancelled=self.stats.cancelled + int(not failed),
                    )
                    failed_submissions.append(
                        (queued, dispatch_error or LaneAdmissionError(self.name, "submission"))
                    )
        # No user callbacks while the lane lock is held. Capacity is physically
        # released before publishing success/failure to the caller.
        job.future._settled.set()
        if not cancelled:
            if failure is None:
                job.future.set_result(result)
            else:
                job.future.set_exception(failure)
        for queued, error in failed_submissions:
            queued.future._settled.set()
            if not queued.future.cancelled():
                queued.future.set_exception(error)

    def snapshot(self):
        with self.lock:
            return replace(self.stats, active=len(self.active), queued=len(self.queue))

    def stop(self):
        with self.lock:
            self.closed = True
            return [job.future for job in self.queue] + [job.future for job in self.active]


class LaneManager:
    def __init__(
        self,
        policy: ExecutionLanePolicy = ExecutionLanePolicy(),
        *,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], str] = _utc_now,
        executor_factory=ThreadPoolExecutor,
    ):
        self.policy = policy
        self.clock = clock
        self._lanes = {
            name: _Lane(name, getattr(policy, name), clock, wall_clock, executor_factory)
            for name in ("local_tool", "provider")
        }

    def submit(self, lane: str, operation: Callable[..., Any], *args, deadline=None) -> LaneFuture:
        if lane not in self._lanes:
            raise ValueError("Unknown execution lane")
        return self._lanes[lane].submit(lambda: operation(*args), deadline)

    def snapshot(self, lane: str) -> LaneSnapshot:
        return self._lanes[lane].snapshot()

    @staticmethod
    def drain(futures: Iterable[LaneFuture]) -> None:
        for future in futures:
            future._settled.wait()

    def cancel_and_wait(self, futures: Iterable[LaneFuture]) -> None:
        futures = tuple(futures)
        for future in futures:
            future.cancel()
        self.drain(futures)

    def wait_for(self, future: LaneFuture, *, deadline=None):
        try:
            if deadline is not None and self.clock() >= deadline:
                future._deadline_cancel = True
                future.cancel()
                raise SpecFlowError("TIME_BUDGET_EXCEEDED", "Execution deadline exhausted.")
            timeout = None if deadline is None else max(0.0, deadline - self.clock())
            try:
                return future.result(timeout=timeout)
            except TimeoutError:
                if future.done():
                    raise
                future._deadline_cancel = True
                future.cancel()
                raise SpecFlowError(
                    "TIME_BUDGET_EXCEEDED", "Execution deadline exhausted."
                ) from None
            except CancelledError:
                code = "TIME_BUDGET_EXCEEDED" if future._deadline_cancel else "RUN_CANCELLED"
                raise SpecFlowError(code, "Execution work cancelled.") from None
        finally:
            self.drain([future])

    def call(self, lane: str, operation: Callable[..., Any], *args, deadline=None):
        return self.wait_for(
            self.submit(lane, operation, *args, deadline=deadline), deadline=deadline
        )

    def shutdown(self):
        pending = [future for lane in self._lanes.values() for future in lane.stop()]
        for future in pending:
            future.cancel()
        for lane in self._lanes.values():
            # Dispatched wrappers must execute their cleanup; their number is
            # bounded by max_active even when public Futures were cancelled.
            lane.executor.shutdown(wait=True, cancel_futures=False)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.shutdown()


DEFAULT_LANES = LaneManager()
