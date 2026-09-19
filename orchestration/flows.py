import httpx
from prefect import flow, task
from prefect.cache_policies import NO_CACHE

from workforcesync.config import Settings
from workforcesync.pipeline import run_pipeline


class TransientStageError(RuntimeError):
    """Sanitized retryable network failure."""


def safe_invoke(function, *args):
    try:
        return function(*args)
    except httpx.TransportError:
        raise TransientStageError("Source connection failed") from None
    except httpx.HTTPStatusError as error:
        if error.response.status_code in {429, 500, 502, 503, 504}:
            raise TransientStageError("Source temporarily unavailable") from None
        raise RuntimeError("Source rejected the request") from None
    except Exception as error:
        raise RuntimeError(f"Stage failed: {type(error).__name__}") from None


def retry_transient(task, task_run, state) -> bool:
    try:
        state.result()
    except TransientStageError:
        return True
    except Exception:
        return False
    return False


def prefect_stage(name, function, *args):
    network = name in {"snapshot", "extract"}
    wrapped = task(
        safe_invoke,
        name=name,
        persist_result=False,
        cache_policy=NO_CACHE,
        retries=2 if network else 0,
        retry_delay_seconds=[1, 3] if network else 0,
        retry_condition_fn=retry_transient if network else None,
    )
    return wrapped(function, *args)


@flow(name="workforce_daily_sync", persist_result=False, log_prints=False)
def workforce_daily_sync(full: bool = False, fail_at: str | None = None):
    return run_pipeline(Settings(), full, stage=prefect_stage, fail_at=fail_at)


if __name__ == "__main__":
    workforce_daily_sync.serve(name="workforce-daily", cron="0 6 * * *", limit=1)
